// =============================================================================
// Q250-V3-Opti: Trajectory Computation CUDA Kernels
// 기하학적 다이브/기만 궤적 계산을 GPU로 오프로드
// 기존 CPU 구현 대비 10~20배 가속 목표
// =============================================================================

#include <cuda_runtime.h>
#include <cuda_fp16.h>
#include <cmath>
#include <cstdint>

#ifndef M_PI
#define M_PI 3.14159265358979323846f
#endif

// =============================================================================
// Device Functions: 수학 유틸리티
// =============================================================================

__device__ __forceinline__ float deg2rad(float deg) {
    return deg * (M_PI / 180.0f);
}

__device__ __forceinline__ float rad2deg(float rad) {
    return rad * (180.0f / M_PI);
}

__device__ __forceinline__ float clamp_f(float val, float min_val, float max_val) {
    return fmaxf(fminf(val, max_val), min_val);
}

// =============================================================================
// Data Structures (Host/Device 공유)
// =============================================================================

struct TrajectoryPoint {
    float x, y, z;        // 위치 (NED 프레임, 미터)
    float vx, vy, vz;     // 속도 (m/s)
    float timestamp;      // 시작 후 경과 시간 (초)
};

struct DiveTrajectoryParams {
    float start_x, start_y, start_z;  // 시작 위치
    float target_alt;                  // 목표 고도 (z, 미터)
    float dive_angle_deg;              // 다이브 각도 (도)
    float max_speed;                   // 최대 속도 (m/s)
    float max_dive_speed;              // 기체 스펙 최대 다이브 속도
    float max_dive_angle_deg;          // 기체 스펙 최대 다이브 각도
    int num_points;                    // 웨이포인트 수
};

struct SpiralDiveParams {
    float start_x, start_y, start_z;
    float radius;              // 나선 반경 (미터)
    float turns;               // 회전 수
    float descent_rate;        // 하강 속도 (m/s)
    float duration;            // 총 지속 시간 (초)
    int num_points;
};

struct SineDiveParams {
    float start_x, start_y, start_z;
    float amplitude;           // 사인파 진폭 (미터)
    float frequency;           // 주파수 (Hz)
    float descent_rate;        // 하강 속도 (m/s)
    float duration;            // 총 지속 시간 (초)
    int num_points;
};

struct JinkParams {
    float start_x, start_y, start_z;
    float speed;               // 세그먼트 속도 (m/s)
    float descent_rate;        // 하강 속도 (m/s)
    float duration;            // 총 지속 시간 (초)
    int num_segments;          // 진크 세그먼트 수
    unsigned int seed;         // 재현 가능한 난수 시드
};

// =============================================================================
// Kernel 1: Geometric Dive Trajectory (기하학적 다이브 궤적)
// 가장 기본적이고 자주 사용되는 커널
// =============================================================================

__global__ void geometric_dive_trajectory_kernel(
    const DiveTrajectoryParams* params,
    TrajectoryPoint* output  // 크기: params->num_points + 1
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= params->num_points + 1) return;

    // 파라미터 로드 (레지스터에 캐싱)
    const float start_x = params->start_x;
    const float start_y = params->start_y;
    const float start_z = params->start_z;
    const float target_alt = params->target_alt;
    const float dive_angle_deg = params->dive_angle_deg;
    const float max_speed = params->max_speed;
    const float max_dive_speed = params->max_dive_speed;
    const float max_dive_angle_deg = params->max_dive_angle_deg;
    const int num_points = params->num_points;

    // 제약 조건 적용 (클램핑)
    const float clamped_speed = fminf(max_speed, max_dive_speed);
    const float clamped_angle = fminf(dive_angle_deg, max_dive_angle_deg);
    
    const float dive_angle_rad = deg2rad(clamped_angle);
    const float altitude_change = start_z - target_alt;
    const float horizontal_dist = altitude_change / tanf(dive_angle_rad);

    float t = (num_points > 0) ? (static_cast<float>(idx) / static_cast<float>(num_points)) : 0.0f;

    // 선형 보간
    float z = start_z - altitude_change * t;
    float horiz_dist = horizontal_dist * t;
    
    // 진행 방향: 북쪽 가정 (y+ 방향)
    float x = start_x + horiz_dist;
    float y = start_y;
    
    // 속도 벡터 (다이브 방향)
    float vx = clamped_speed * cosf(dive_angle_rad);
    float vz = -clamped_speed * sinf(dive_angle_rad);
    
    output[idx].x = x;
    output[idx].y = y;
    output[idx].z = z;
    output[idx].vx = vx;
    output[idx].vy = 0.0f;
    output[idx].vz = vz;
    output[idx].timestamp = t * (altitude_change / clamped_speed);
}

// =============================================================================
// Kernel 2: Spiral Dive Trajectory (나선형 다이브)
// =============================================================================

__global__ void spiral_dive_trajectory_kernel(
    const SpiralDiveParams* params,
    TrajectoryPoint* output
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= params->num_points + 1) return;

    const float start_x = params->start_x;
    const float start_y = params->start_y;
    const float start_z = params->start_z;
    const float radius = params->radius;
    const float turns = params->turns;
    const float descent_rate = params->descent_rate;
    const float duration = params->duration;
    const int num_points = params->num_points;

    float t = (num_points > 0) ? (static_cast<float>(idx) / static_cast<float>(num_points)) : 0.0f;
    float angle = 2.0f * M_PI * turns * t;
    float z = start_z - descent_rate * duration * t;

    float x, y, vx, vy, vz;

    if (idx == 0) {
        // 첫 포인트: 시작점 (중심)
        x = start_x;
        y = start_y;
        vx = 0.0f;
        vy = 0.0f;
    } else {
        x = start_x + radius * cosf(angle);
        y = start_y + radius * sinf(angle);
        // 원운동 속도: v = r * omega, omega = 2*pi*turns / duration
        float omega = 2.0f * M_PI * turns / duration;
        vx = -radius * omega * sinf(angle);
        vy = radius * omega * cosf(angle);
    }
    vz = -descent_rate;

    output[idx].x = x;
    output[idx].y = y;
    output[idx].z = z;
    output[idx].vx = vx;
    output[idx].vy = vy;
    output[idx].vz = vz;
    output[idx].timestamp = t * duration;
}

// =============================================================================
// Kernel 3: Sine Dive Trajectory (사인파 다이브)
// =============================================================================

__global__ void sine_dive_trajectory_kernel(
    const SineDiveParams* params,
    TrajectoryPoint* output
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= params->num_points + 1) return;

    const float start_x = params->start_x;
    const float start_y = params->start_y;
    const float start_z = params->start_z;
    const float amplitude = params->amplitude;
    const float frequency = params->frequency;
    const float descent_rate = params->descent_rate;
    const float duration = params->duration;
    const int num_points = params->num_points;

    float t = (num_points > 0) ? (static_cast<float>(idx) / static_cast<float>(num_points)) : 0.0f;
    float phase = 2.0f * M_PI * frequency * t;

    float x = start_x + amplitude * sinf(phase);
    float y = start_y;
    float z = start_z - descent_rate * duration * t;

    // 속도: x는 사인파 미분, z는 일정 하강
    float vx = amplitude * 2.0f * M_PI * frequency / duration * cosf(phase);
    float vy = 0.0f;
    float vz = -descent_rate;

    output[idx].x = x;
    output[idx].y = y;
    output[idx].z = z;
    output[idx].vx = vx;
    output[idx].vy = vy;
    output[idx].vz = vz;
    output[idx].timestamp = t * duration;
}

// =============================================================================
// Kernel 4: Random Jink Trajectory (랜덤 진크)
// curand 커널로 재현 가능한 난수 생성
// =============================================================================

__global__ void random_jink_trajectory_kernel(
    const JinkParams* params,
    TrajectoryPoint* output,
    unsigned int* seed_state  // 1개 요소 배열 (전역 시드 상태)
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= params->num_segments + 1) return;

    const float start_x = params->start_x;
    const float start_y = params->start_y;
    const float start_z = params->start_z;
    const float speed = params->speed;
    const float descent_rate = params->descent_rate;
    const float duration = params->duration;
    const int num_segments = params->num_segments;

    float segment_duration = duration / static_cast<float>(num_segments);
    float t = static_cast<float>(idx) * segment_duration;

    // 재현 가능한 난수 생성을 위한 Philox RNG (단순화: seed + idx 해시)
    unsigned int seed = params->seed + static_cast<unsigned int>(idx * 1664525u + 1013904223u);
    // 간단한 XORShift로 방향 각도 생성
    seed ^= seed << 13;
    seed ^= seed >> 17;
    seed ^= seed << 5;
    float angle = 2.0f * M_PI * (static_cast<float>(seed) / 4294967296.0f);

    // 누적 위치를 위한 prefix sum 방식 (실제론 별도 커널 필요, 여기선 단순화)
    // 실제 구현 시: exclusive scan으로 누적 위치 계산
    // 여기서는 마지막 세그먼트만 계산하는 것으로 근사
    float x = start_x, y = start_y, z = start_z;
    float vx = 0.0f, vy = 0.0f, vz = -descent_rate;

    if (idx == 0) {
        x = start_x;
        y = start_y;
        z = start_z;
        vx = 0.0f;
        vy = 0.0f;
        vz = 0.0f;
    } else {
        // 이전 세그먼트 끝점 추정 (실제론 prefix sum 필요)
        // 여기서는 단순화: 각 세그먼트 독립적
        vx = speed * cosf(angle);
        vy = speed * sinf(angle);
        vz = -descent_rate;
        x = start_x + vx * t;
        y = start_y + vy * t;
        z = start_z + vz * t;
    }

    output[idx].x = x;
    output[idx].y = y;
    output[idx].z = z;
    output[idx].vx = vx;
    output[idx].vy = vy;
    output[idx].vz = vz;
    output[idx].timestamp = t;
}

// =============================================================================
// Kernel 5: LUT Lookup Acceleration (캐시된 궤적 보간)
// =============================================================================

struct CachedTrajectory {
    int num_points;
    TrajectoryPoint* points;  // device pointer
};

__global__ void lut_interpolate_kernel(
    const CachedTrajectory* cache,
    float scale_factor,  // 시간/거리 스케일링
    float altitude_scale,
    TrajectoryPoint* output,
    int output_points
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= output_points) return;

    int src_idx = min(static_cast<int>(idx * cache->num_points / static_cast<float>(output_points)), 
                      cache->num_points - 1);
    
    TrajectoryPoint src = cache->points[src_idx];
    output[idx].x = src.x * scale_factor;
    output[idx].y = src.y * scale_factor;
    output[idx].z = src.z * altitude_scale;
    output[idx].vx = src.vx * scale_factor;
    output[idx].vy = src.vy * scale_factor;
    output[idx].vz = src.vz * altitude_scale;
    output[idx].timestamp = src.timestamp * scale_factor;
}

// =============================================================================
// Host Helper Functions
// =============================================================================

inline int div_up(int a, int b) {
    return (a + b - 1) / b;
}

// 기하학적 다이브 궤적 실행
cudaError_t launch_geometric_dive_trajectory(
    const DiveTrajectoryParams& h_params,
    TrajectoryPoint* d_output,
    int num_points
) {
    DiveTrajectoryParams* d_params;
    cudaMalloc(&d_params, sizeof(DiveTrajectoryParams));
    cudaMemcpy(d_params, &h_params, sizeof(DiveTrajectoryParams), cudaMemcpyHostToDevice);

    dim3 block(256);
    dim3 grid(div_up(num_points + 1, 256));
    
    geometric_dive_trajectory_kernel<<<grid, block>>>(d_params, d_output);
    
    cudaError_t err = cudaGetLastError();
    cudaFree(d_params);
    return err;
}

// 나선형 다이브 실행
cudaError_t launch_spiral_dive_trajectory(
    const SpiralDiveParams& h_params,
    TrajectoryPoint* d_output,
    int num_points
) {
    SpiralDiveParams* d_params;
    cudaMalloc(&d_params, sizeof(SpiralDiveParams));
    cudaMemcpy(d_params, &h_params, sizeof(SpiralDiveParams), cudaMemcpyHostToDevice);

    dim3 block(256);
    dim3 grid(div_up(num_points + 1, 256));
    
    spiral_dive_trajectory_kernel<<<grid, block>>>(d_params, d_output);
    
    cudaError_t err = cudaGetLastError();
    cudaFree(d_params);
    return err;
}

// 사인파 다이브 실행
cudaError_t launch_sine_dive_trajectory(
    const SineDiveParams& h_params,
    TrajectoryPoint* d_output,
    int num_points
) {
    SineDiveParams* d_params;
    cudaMalloc(&d_params, sizeof(SineDiveParams));
    cudaMemcpy(d_params, &h_params, sizeof(SineDiveParams), cudaMemcpyHostToDevice);

    dim3 block(256);
    dim3 grid(div_up(num_points + 1, 256));
    
    sine_dive_trajectory_kernel<<<grid, block>>>(d_params, d_output);
    
    cudaError_t err = cudaGetLastError();
    cudaFree(d_params);
    return err;
}

// 진크 궤적 실행 (씨드 상태 관리)
cudaError_t launch_jink_trajectory(
    const JinkParams& h_params,
    TrajectoryPoint* d_output,
    int num_segments,
    unsigned int* d_seed_state
) {
    JinkParams* d_params;
    cudaMalloc(&d_params, sizeof(JinkParams));
    cudaMemcpy(d_params, &h_params, sizeof(JinkParams), cudaMemcpyHostToDevice);

    dim3 block(256);
    dim3 grid(div_up(num_segments + 1, 256));
    
    random_jink_trajectory_kernel<<<grid, block>>>(d_params, d_output, d_seed_state);
    
    cudaError_t err = cudaGetLastError();
    cudaFree(d_params);
    return err;
}

// LUT 보간 실행
cudaError_t launch_lut_interpolate(
    const CachedTrajectory& d_cache,
    float scale_factor,
    float altitude_scale,
    TrajectoryPoint* d_output,
    int output_points
) {
    dim3 block(256);
    dim3 grid(div_up(output_points, 256));
    
    lut_interpolate_kernel<<<grid, block>>>(&d_cache, scale_factor, altitude_scale, d_output, output_points);
    
    return cudaGetLastError();
}