#ifndef TRAJECTORY_KERNELS_H
#define TRAJECTORY_KERNELS_H

#include <cuda_runtime.h>
#include <cstdint>

#ifndef M_PI
#define M_PI 3.14159265358979323846f
#endif

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

struct CachedTrajectory {
    int num_points;
    TrajectoryPoint* points;  // device pointer
};

// =============================================================================
// Kernel Launch Functions (Host 호출용)
// =============================================================================

#ifdef __cplusplus
extern "C" {
#endif

// 기하학적 다이브 궤적
cudaError_t launch_geometric_dive_trajectory(
    const DiveTrajectoryParams* params,
    TrajectoryPoint* output,
    int num_points
);

// 나선형 다이브 궤적
cudaError_t launch_spiral_dive_trajectory(
    const SpiralDiveParams* params,
    TrajectoryPoint* output,
    int num_points
);

// 사인파 다이브 궤적
cudaError_t launch_sine_dive_trajectory(
    const SineDiveParams* params,
    TrajectoryPoint* output,
    int num_points
);

// 랜덤 진크 궤적
cudaError_t launch_jink_trajectory(
    const JinkParams* params,
    TrajectoryPoint* output,
    int num_segments,
    unsigned int* seed_state
);

// LUT 보간
cudaError_t launch_lut_interpolate(
    const CachedTrajectory* cache,
    float scale_factor,
    float altitude_scale,
    TrajectoryPoint* output,
    int output_points
);

#ifdef __cplusplus
}
#endif

#endif // TRAJECTORY_KERNELS_H