// =============================================================================
// Q250-V3-Opti: Trajectory Kernels CUDA Test Suite
// Enables ctest execution in CI for kernel validation
// =============================================================================

#include <cuda_runtime.h>
#include <cuda_fp16.h>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <algorithm>

#include "trajectory_kernels.cuh"

// =============================================================================
// Test Utilities
// =============================================================================

#define CUDA_CHECK(call) \
    do { \
        cudaError_t err = call; \
        if (err != cudaSuccess) { \
            fprintf(stderr, "CUDA error at %s:%d - %s: %s\n", \
                    __FILE__, __LINE__, #call, cudaGetErrorString(err)); \
            return false; \
        } \
    } while(0)

#define TEST_ASSERT(condition, msg) \
    do { \
        if (!(condition)) { \
            fprintf(stderr, "TEST FAILED: %s at %s:%d\n", msg, __FILE__, __LINE__); \
            return false; \
        } \
    } while(0)

#define TEST_ASSERT_FLOAT_EQ(expected, actual, eps, msg) \
    do { \
        float diff = fabsf((expected) - (actual)); \
        if (diff > (eps)) { \
            fprintf(stderr, "TEST FAILED: %s at %s:%d - expected %.6f, got %.6f (diff=%.6f)\n", \
                    msg, __FILE__, __LINE__, (expected), (actual), diff); \
            return false; \
        } \
    } while(0)

struct TestStats {
    int passed = 0;
    int failed = 0;
    
    void record(bool result, const char* test_name) {
        if (result) {
            passed++;
            printf("[PASS] %s\n", test_name);
        } else {
            failed++;
            printf("[FAIL] %s\n", test_name);
        }
    }
    
    void print_summary() {
        printf("\n========================================\n");
        printf("Test Summary: %d passed, %d failed\n", passed, failed);
        printf("========================================\n");
    }
    
    int exit_code() const { return failed == 0 ? 0 : 1; }
};

// Helper to compare trajectory points
bool compare_points(const TrajectoryPoint& expected, const TrajectoryPoint& actual, float eps = 1e-4f) {
    return fabsf(expected.x - actual.x) <= eps &&
           fabsf(expected.y - actual.y) <= eps &&
           fabsf(expected.z - actual.z) <= eps &&
           fabsf(expected.vx - actual.vx) <= eps &&
           fabsf(expected.vy - actual.vy) <= eps &&
           fabsf(expected.vz - actual.vz) <= eps &&
           fabsf(expected.timestamp - actual.timestamp) <= eps;
}

// =============================================================================
// Test 1: Geometric Dive Trajectory
// =============================================================================

bool test_geometric_dive_basic() {
    const int num_points = 10;
    
    DiveTrajectoryParams params = {
        .start_x = 0.0f,
        .start_y = 0.0f,
        .start_z = 100.0f,
        .target_alt = 50.0f,
        .dive_angle_deg = 45.0f,
        .max_speed = 25.0f,
        .max_dive_speed = 30.0f,
        .max_dive_angle_deg = 60.0f,
        .num_points = num_points
    };
    
    TrajectoryPoint* d_output;
    CUDA_CHECK(cudaMalloc(&d_output, (num_points + 1) * sizeof(TrajectoryPoint)));
    
    cudaError_t err = launch_geometric_dive_trajectory(params, d_output, num_points);
    if (err != cudaSuccess) {
        fprintf(stderr, "launch_geometric_dive_trajectory failed: %s\n", cudaGetErrorString(err));
        cudaFree(d_output);
        return false;
    }
    
    CUDA_CHECK(cudaDeviceSynchronize());
    
    TrajectoryPoint* h_output = new TrajectoryPoint[num_points + 1];
    CUDA_CHECK(cudaMemcpy(h_output, d_output, (num_points + 1) * sizeof(TrajectoryPoint), cudaMemcpyDeviceToHost));
    
    // Verify basic properties
    // Point 0 should be at start position
    TEST_ASSERT_FLOAT_EQ(h_output[0].x, 0.0f, 1e-4f, "start x");
    TEST_ASSERT_FLOAT_EQ(h_output[0].y, 0.0f, 1e-4f, "start y");
    TEST_ASSERT_FLOAT_EQ(h_output[0].z, 100.0f, 1e-4f, "start z");
    
    // Last point should be at target altitude
    TEST_ASSERT_FLOAT_EQ(h_output[num_points].z, 50.0f, 1e-3f, "target altitude");
    
    // Velocity should be consistent (clamped to max_speed since 25 < 30)
    float expected_speed = 25.0f;
    float dive_angle_rad = 45.0f * M_PI / 180.0f;
    float expected_vx = expected_speed * cosf(dive_angle_rad);
    float expected_vz = -expected_speed * sinf(dive_angle_rad);
    
    for (int i = 0; i <= num_points; i++) {
        TEST_ASSERT_FLOAT_EQ(h_output[i].vx, expected_vx, 1e-4f, "vx constant");
        TEST_ASSERT_FLOAT_EQ(h_output[i].vy, 0.0f, 1e-4f, "vy zero");
        TEST_ASSERT_FLOAT_EQ(h_output[i].vz, expected_vz, 1e-4f, "vz constant");
        TEST_ASSERT(h_output[i].timestamp >= 0.0f, "timestamp non-negative");
    }
    
    // Timestamps should be monotonically increasing
    for (int i = 1; i <= num_points; i++) {
        TEST_ASSERT(h_output[i].timestamp > h_output[i-1].timestamp, "timestamp increasing");
    }
    
    delete[] h_output;
    cudaFree(d_output);
    return true;
}

bool test_geometric_dive_clamping() {
    const int num_points = 5;
    
    // Test speed clamping (max_speed > max_dive_speed)
    DiveTrajectoryParams params = {
        .start_x = 0.0f,
        .start_y = 0.0f,
        .start_z = 100.0f,
        .target_alt = 50.0f,
        .dive_angle_deg = 30.0f,
        .max_speed = 50.0f,       // Higher than max_dive_speed
        .max_dive_speed = 30.0f,  // Should clamp to this
        .max_dive_angle_deg = 45.0f,
        .num_points = num_points
    };
    
    TrajectoryPoint* d_output;
    CUDA_CHECK(cudaMalloc(&d_output, (num_points + 1) * sizeof(TrajectoryPoint)));
    
    cudaError_t err = launch_geometric_dive_trajectory(params, d_output, num_points);
    if (err != cudaSuccess) {
        cudaFree(d_output);
        return false;
    }
    
    CUDA_CHECK(cudaDeviceSynchronize());
    
    TrajectoryPoint* h_output = new TrajectoryPoint[num_points + 1];
    CUDA_CHECK(cudaMemcpy(h_output, d_output, (num_points + 1) * sizeof(TrajectoryPoint), cudaMemcpyDeviceToHost));
    
    // Speed should be clamped to max_dive_speed (30.0)
    float expected_speed = 30.0f;
    float dive_angle_rad = 30.0f * M_PI / 180.0f;
    float expected_vx = expected_speed * cosf(dive_angle_rad);
    float expected_vz = -expected_speed * sinf(dive_angle_rad);
    
    for (int i = 0; i <= num_points; i++) {
        TEST_ASSERT_FLOAT_EQ(h_output[i].vx, expected_vx, 1e-4f, "clamped vx");
        TEST_ASSERT_FLOAT_EQ(h_output[i].vz, expected_vz, 1e-4f, "clamped vz");
    }
    
    delete[] h_output;
    cudaFree(d_output);
    return true;
}

bool test_geometric_dive_angle_clamping() {
    const int num_points = 5;
    
    // Test angle clamping (dive_angle > max_dive_angle)
    DiveTrajectoryParams params = {
        .start_x = 0.0f,
        .start_y = 0.0f,
        .start_z = 100.0f,
        .target_alt = 50.0f,
        .dive_angle_deg = 70.0f,   // Higher than max_dive_angle
        .max_speed = 25.0f,
        .max_dive_speed = 50.0f,
        .max_dive_angle_deg = 45.0f,  // Should clamp to this
        .num_points = num_points
    };
    
    TrajectoryPoint* d_output;
    CUDA_CHECK(cudaMalloc(&d_output, (num_points + 1) * sizeof(TrajectoryPoint)));
    
    cudaError_t err = launch_geometric_dive_trajectory(params, d_output, num_points);
    if (err != cudaSuccess) {
        cudaFree(d_output);
        return false;
    }
    
    CUDA_CHECK(cudaDeviceSynchronize());
    
    TrajectoryPoint* h_output = new TrajectoryPoint[num_points + 1];
    CUDA_CHECK(cudaMemcpy(h_output, d_output, (num_points + 1) * sizeof(TrajectoryPoint), cudaMemcpyDeviceToHost));
    
    // Angle should be clamped to max_dive_angle_deg (45.0)
    float expected_angle = 45.0f * M_PI / 180.0f;
    float expected_vx = 25.0f * cosf(expected_angle);
    float expected_vz = -25.0f * sinf(expected_angle);
    
    for (int i = 0; i <= num_points; i++) {
        TEST_ASSERT_FLOAT_EQ(h_output[i].vx, expected_vx, 1e-4f, "angle clamped vx");
        TEST_ASSERT_FLOAT_EQ(h_output[i].vz, expected_vz, 1e-4f, "angle clamped vz");
    }
    
    delete[] h_output;
    cudaFree(d_output);
    return true;
}

// =============================================================================
// Test 2: Spiral Dive Trajectory
// =============================================================================

bool test_spiral_dive_basic() {
    const int num_points = 20;
    
    SpiralDiveParams params = {
        .start_x = 0.0f,
        .start_y = 0.0f,
        .start_z = 100.0f,
        .radius = 50.0f,
        .turns = 2.0f,
        .descent_rate = 10.0f,
        .duration = 10.0f,
        .num_points = num_points
    };
    
    TrajectoryPoint* d_output;
    CUDA_CHECK(cudaMalloc(&d_output, (num_points + 1) * sizeof(TrajectoryPoint)));
    
    cudaError_t err = launch_spiral_dive_trajectory(params, d_output, num_points);
    if (err != cudaSuccess) {
        cudaFree(d_output);
        return false;
    }
    
    CUDA_CHECK(cudaDeviceSynchronize());
    
    TrajectoryPoint* h_output = new TrajectoryPoint[num_points + 1];
    CUDA_CHECK(cudaMemcpy(h_output, d_output, (num_points + 1) * sizeof(TrajectoryPoint), cudaMemcpyDeviceToHost));
    
    // Point 0 should be at start (center)
    TEST_ASSERT_FLOAT_EQ(h_output[0].x, 0.0f, 1e-4f, "spiral start x");
    TEST_ASSERT_FLOAT_EQ(h_output[0].y, 0.0f, 1e-4f, "spiral start y");
    TEST_ASSERT_FLOAT_EQ(h_output[0].z, 100.0f, 1e-4f, "spiral start z");
    TEST_ASSERT_FLOAT_EQ(h_output[0].vx, 0.0f, 1e-4f, "spiral start vx");
    TEST_ASSERT_FLOAT_EQ(h_output[0].vy, 0.0f, 1e-4f, "spiral start vy");
    
    // Last point should have descended by descent_rate * duration
    float expected_final_z = 100.0f - 10.0f * 10.0f;
    TEST_ASSERT_FLOAT_EQ(h_output[num_points].z, expected_final_z, 1e-3f, "spiral final z");
    
    // Velocity z should be constant -descent_rate
    for (int i = 0; i <= num_points; i++) {
        TEST_ASSERT_FLOAT_EQ(h_output[i].vz, -10.0f, 1e-4f, "spiral vz constant");
    }
    
    // Points 1+ should be on spiral (radius from center)
    for (int i = 1; i <= num_points; i++) {
        float r = sqrtf(h_output[i].x * h_output[i].x + h_output[i].y * h_output[i].y);
        TEST_ASSERT_FLOAT_EQ(r, 50.0f, 1e-3f, "spiral radius");
    }
    
    // Timestamps should be monotonically increasing
    for (int i = 1; i <= num_points; i++) {
        TEST_ASSERT(h_output[i].timestamp > h_output[i-1].timestamp, "spiral timestamp increasing");
    }
    
    delete[] h_output;
    cudaFree(d_output);
    return true;
}

bool test_spiral_dive_velocity() {
    const int num_points = 10;
    
    SpiralDiveParams params = {
        .start_x = 0.0f,
        .start_y = 0.0f,
        .start_z = 100.0f,
        .radius = 10.0f,
        .turns = 1.0f,
        .descent_rate = 5.0f,
        .duration = 5.0f,
        .num_points = num_points
    };
    
    TrajectoryPoint* d_output;
    CUDA_CHECK(cudaMalloc(&d_output, (num_points + 1) * sizeof(TrajectoryPoint)));
    
    cudaError_t err = launch_spiral_dive_trajectory(params, d_output, num_points);
    if (err != cudaSuccess) {
        cudaFree(d_output);
        return false;
    }
    
    CUDA_CHECK(cudaDeviceSynchronize());
    
    TrajectoryPoint* h_output = new TrajectoryPoint[num_points + 1];
    CUDA_CHECK(cudaMemcpy(h_output, d_output, (num_points + 1) * sizeof(TrajectoryPoint), cudaMemcpyDeviceToHost));
    
    // Verify velocity magnitude matches omega * radius
    float omega = 2.0f * M_PI * params.turns / params.duration;
    float expected_speed = params.radius * omega;
    
    for (int i = 1; i <= num_points; i++) {
        float speed = sqrtf(h_output[i].vx * h_output[i].vx + h_output[i].vy * h_output[i].vy);
        TEST_ASSERT_FLOAT_EQ(speed, expected_speed, 1e-3f, "spiral tangential speed");
        
        // Velocity should be perpendicular to position vector
        float dot = h_output[i].x * h_output[i].vx + h_output[i].y * h_output[i].vy;
        TEST_ASSERT_FLOAT_EQ(dot, 0.0f, 1e-3f, "spiral velocity perpendicular");
    }
    
    delete[] h_output;
    cudaFree(d_output);
    return true;
}

// =============================================================================
// Test 3: Sine Dive Trajectory
// =============================================================================

bool test_sine_dive_basic() {
    const int num_points = 20;
    
    SineDiveParams params = {
        .start_x = 0.0f,
        .start_y = 0.0f,
        .start_z = 100.0f,
        .amplitude = 20.0f,
        .frequency = 0.5f,
        .descent_rate = 10.0f,
        .duration = 10.0f,
        .num_points = num_points
    };
    
    TrajectoryPoint* d_output;
    CUDA_CHECK(cudaMalloc(&d_output, (num_points + 1) * sizeof(TrajectoryPoint)));
    
    cudaError_t err = launch_sine_dive_trajectory(params, d_output, num_points);
    if (err != cudaSuccess) {
        cudaFree(d_output);
        return false;
    }
    
    CUDA_CHECK(cudaDeviceSynchronize());
    
    TrajectoryPoint* h_output = new TrajectoryPoint[num_points + 1];
    CUDA_CHECK(cudaMemcpy(h_output, d_output, (num_points + 1) * sizeof(TrajectoryPoint), cudaMemcpyDeviceToHost));
    
    // Verify start point
    TEST_ASSERT_FLOAT_EQ(h_output[0].x, 0.0f, 1e-4f, "sine start x");
    TEST_ASSERT_FLOAT_EQ(h_output[0].y, 0.0f, 1e-4f, "sine start y");
    TEST_ASSERT_FLOAT_EQ(h_output[0].z, 100.0f, 1e-4f, "sine start z");
    
    // Verify final altitude
    float expected_final_z = 100.0f - 10.0f * 10.0f;
    TEST_ASSERT_FLOAT_EQ(h_output[num_points].z, expected_final_z, 1e-3f, "sine final z");
    
    // Verify amplitude bounds
    for (int i = 0; i <= num_points; i++) {
        TEST_ASSERT(fabsf(h_output[i].x) <= 20.0f + 1e-3f, "sine amplitude bound");
        TEST_ASSERT_FLOAT_EQ(h_output[i].y, 0.0f, 1e-4f, "sine y zero");
        TEST_ASSERT_FLOAT_EQ(h_output[i].vz, -10.0f, 1e-4f, "sine vz constant");
    }
    
    // Verify velocity x follows cosine (derivative of sine)
    for (int i = 0; i <= num_points; i++) {
        float t = static_cast<float>(i) / num_points;
        float phase = 2.0f * M_PI * params.frequency * t;
        float expected_vx = params.amplitude * 2.0f * M_PI * params.frequency / params.duration * cosf(phase);
        TEST_ASSERT_FLOAT_EQ(h_output[i].vx, expected_vx, 1e-3f, "sine vx derivative");
    }
    
    delete[] h_output;
    cudaFree(d_output);
    return true;
}

// =============================================================================
// Test 4: Random Jink Trajectory
// =============================================================================

bool test_jink_trajectory_basic() {
    const int num_segments = 10;
    unsigned int seed = 0xDEADBEEF;
    
    JinkParams params = {
        .start_x = 0.0f,
        .start_y = 0.0f,
        .start_z = 100.0f,
        .speed = 20.0f,
        .descent_rate = 5.0f,
        .duration = 10.0f,
        .num_segments = num_segments,
        .seed = seed
    };
    
    TrajectoryPoint* d_output;
    CUDA_CHECK(cudaMalloc(&d_output, (num_segments + 1) * sizeof(TrajectoryPoint)));
    
    unsigned int* d_seed_state;
    CUDA_CHECK(cudaMalloc(&d_seed_state, sizeof(unsigned int)));
    CUDA_CHECK(cudaMemcpy(d_seed_state, &seed, sizeof(unsigned int), cudaMemcpyHostToDevice));
    
    cudaError_t err = launch_jink_trajectory(params, d_output, num_segments, d_seed_state);
    if (err != cudaSuccess) {
        cudaFree(d_output);
        cudaFree(d_seed_state);
        return false;
    }
    
    CUDA_CHECK(cudaDeviceSynchronize());
    
    TrajectoryPoint* h_output = new TrajectoryPoint[num_segments + 1];
    CUDA_CHECK(cudaMemcpy(h_output, d_output, (num_segments + 1) * sizeof(TrajectoryPoint), cudaMemcpyDeviceToHost));
    
    // Verify start point
    TEST_ASSERT_FLOAT_EQ(h_output[0].x, 0.0f, 1e-4f, "jink start x");
    TEST_ASSERT_FLOAT_EQ(h_output[0].y, 0.0f, 1e-4f, "jink start y");
    TEST_ASSERT_FLOAT_EQ(h_output[0].z, 100.0f, 1e-4f, "jink start z");
    TEST_ASSERT_FLOAT_EQ(h_output[0].vx, 0.0f, 1e-4f, "jink start vx");
    TEST_ASSERT_FLOAT_EQ(h_output[0].vy, 0.0f, 1e-4f, "jink start vy");
    TEST_ASSERT_FLOAT_EQ(h_output[0].vz, 0.0f, 1e-4f, "jink start vz");
    
    // Verify descent rate
    for (int i = 1; i <= num_segments; i++) {
        TEST_ASSERT_FLOAT_EQ(h_output[i].vz, -5.0f, 1e-3f, "jink vz descent");
        TEST_ASSERT(h_output[i].timestamp > h_output[i-1].timestamp, "jink timestamp increasing");
    }
    
    // Verify reproducibility - run again with same seed
    TrajectoryPoint* d_output2;
    CUDA_CHECK(cudaMalloc(&d_output2, (num_segments + 1) * sizeof(TrajectoryPoint)));
    unsigned int* d_seed_state2;
    CUDA_CHECK(cudaMalloc(&d_seed_state2, sizeof(unsigned int)));
    CUDA_CHECK(cudaMemcpy(d_seed_state2, &seed, sizeof(unsigned int), cudaMemcpyHostToDevice));
    
    err = launch_jink_trajectory(params, d_output2, num_segments, d_seed_state2);
    CUDA_CHECK(cudaDeviceSynchronize());
    
    TrajectoryPoint* h_output2 = new TrajectoryPoint[num_segments + 1];
    CUDA_CHECK(cudaMemcpy(h_output2, d_output2, (num_segments + 1) * sizeof(TrajectoryPoint), cudaMemcpyDeviceToHost));
    
    for (int i = 0; i <= num_segments; i++) {
        TEST_ASSERT(compare_points(h_output[i], h_output2[i]), "jink reproducibility");
    }
    
    delete[] h_output;
    delete[] h_output2;
    cudaFree(d_output);
    cudaFree(d_output2);
    cudaFree(d_seed_state);
    cudaFree(d_seed_state2);
    return true;
}

// =============================================================================
// Test 5: LUT Interpolation
// =============================================================================

bool test_lut_interpolate_basic() {
    const int cache_points = 10;
    const int output_points = 20;
    
    // Create a simple linear cache on host
    TrajectoryPoint* h_cache = new TrajectoryPoint[cache_points];
    for (int i = 0; i < cache_points; i++) {
        float t = static_cast<float>(i) / (cache_points - 1);
        h_cache[i].x = 10.0f * t;
        h_cache[i].y = 5.0f * t;
        h_cache[i].z = 100.0f - 50.0f * t;
        h_cache[i].vx = 10.0f;
        h_cache[i].vy = 5.0f;
        h_cache[i].vz = -50.0f;
        h_cache[i].timestamp = 10.0f * t;
    }
    
    // Copy to device
    TrajectoryPoint* d_cache_points;
    CUDA_CHECK(cudaMalloc(&d_cache_points, cache_points * sizeof(TrajectoryPoint)));
    CUDA_CHECK(cudaMemcpy(d_cache_points, h_cache, cache_points * sizeof(TrajectoryPoint), cudaMemcpyHostToDevice));
    
    CachedTrajectory d_cache;
    d_cache.num_points = cache_points;
    d_cache.points = d_cache_points;
    
    TrajectoryPoint* d_output;
    CUDA_CHECK(cudaMalloc(&d_output, output_points * sizeof(TrajectoryPoint)));
    
    cudaError_t err = launch_lut_interpolate(d_cache, 2.0f, 0.5f, d_output, output_points);
    if (err != cudaSuccess) {
        cudaFree(d_cache_points);
        cudaFree(d_output);
        delete[] h_cache;
        return false;
    }
    
    CUDA_CHECK(cudaDeviceSynchronize());
    
    TrajectoryPoint* h_output = new TrajectoryPoint[output_points];
    CUDA_CHECK(cudaMemcpy(h_output, d_output, output_points * sizeof(TrajectoryPoint), cudaMemcpyDeviceToHost));
    
    // Verify interpolation with scale_factor=2.0, altitude_scale=0.5
    for (int i = 0; i < output_points; i++) {
        // Source index calculation (nearest neighbor)
        int src_idx = (int)(i * cache_points / static_cast<float>(output_points));
        src_idx = min(src_idx, cache_points - 1);
        
        TEST_ASSERT_FLOAT_EQ(h_output[i].x, h_cache[src_idx].x * 2.0f, 1e-4f, "lut x scaled");
        TEST_ASSERT_FLOAT_EQ(h_output[i].y, h_cache[src_idx].y * 2.0f, 1e-4f, "lut y scaled");
        TEST_ASSERT_FLOAT_EQ(h_output[i].z, h_cache[src_idx].z * 0.5f, 1e-4f, "lut z scaled");
        TEST_ASSERT_FLOAT_EQ(h_output[i].vx, h_cache[src_idx].vx * 2.0f, 1e-4f, "lut vx scaled");
        TEST_ASSERT_FLOAT_EQ(h_output[i].vy, h_cache[src_idx].vy * 2.0f, 1e-4f, "lut vy scaled");
        TEST_ASSERT_FLOAT_EQ(h_output[i].vz, h_cache[src_idx].vz * 0.5f, 1e-4f, "lut vz scaled");
        TEST_ASSERT_FLOAT_EQ(h_output[i].timestamp, h_cache[src_idx].timestamp * 2.0f, 1e-4f, "lut ts scaled");
    }
    
    delete[] h_output;
    delete[] h_cache;
    cudaFree(d_cache_points);
    cudaFree(d_output);
    return true;
}

bool test_lut_interpolate_identity() {
    const int cache_points = 10;
    const int output_points = 10;
    
    TrajectoryPoint* h_cache = new TrajectoryPoint[cache_points];
    for (int i = 0; i < cache_points; i++) {
        float t = static_cast<float>(i) / (cache_points - 1);
        h_cache[i].x = 10.0f * t;
        h_cache[i].y = 5.0f * t;
        h_cache[i].z = 100.0f - 50.0f * t;
        h_cache[i].vx = 10.0f;
        h_cache[i].vy = 5.0f;
        h_cache[i].vz = -50.0f;
        h_cache[i].timestamp = 10.0f * t;
    }
    
    TrajectoryPoint* d_cache_points;
    CUDA_CHECK(cudaMalloc(&d_cache_points, cache_points * sizeof(TrajectoryPoint)));
    CUDA_CHECK(cudaMemcpy(d_cache_points, h_cache, cache_points * sizeof(TrajectoryPoint), cudaMemcpyHostToDevice));
    
    CachedTrajectory d_cache;
    d_cache.num_points = cache_points;
    d_cache.points = d_cache_points;
    
    TrajectoryPoint* d_output;
    CUDA_CHECK(cudaMalloc(&d_output, output_points * sizeof(TrajectoryPoint)));
    
    // Identity transform: scale_factor=1.0, altitude_scale=1.0
    cudaError_t err = launch_lut_interpolate(d_cache, 1.0f, 1.0f, d_output, output_points);
    CUDA_CHECK(cudaDeviceSynchronize());
    
    TrajectoryPoint* h_output = new TrajectoryPoint[output_points];
    CUDA_CHECK(cudaMemcpy(h_output, d_output, output_points * sizeof(TrajectoryPoint), cudaMemcpyDeviceToHost));
    
    for (int i = 0; i < output_points; i++) {
        TEST_ASSERT(compare_points(h_output[i], h_cache[i]), "lut identity");
    }
    
    delete[] h_output;
    delete[] h_cache;
    cudaFree(d_cache_points);
    cudaFree(d_output);
    return true;
}

// =============================================================================
// Edge Case Tests
// =============================================================================

bool test_edge_case_single_point() {
    // Test with num_points = 1 (minimum)
    DiveTrajectoryParams params = {
        .start_x = 0.0f,
        .start_y = 0.0f,
        .start_z = 100.0f,
        .target_alt = 50.0f,
        .dive_angle_deg = 45.0f,
        .max_speed = 25.0f,
        .max_dive_speed = 30.0f,
        .max_dive_angle_deg = 60.0f,
        .num_points = 1
    };
    
    TrajectoryPoint* d_output;
    CUDA_CHECK(cudaMalloc(&d_output, 2 * sizeof(TrajectoryPoint)));
    
    cudaError_t err = launch_geometric_dive_trajectory(params, d_output, 1);
    CUDA_CHECK(cudaDeviceSynchronize());
    
    TrajectoryPoint* h_output = new TrajectoryPoint[2];
    CUDA_CHECK(cudaMemcpy(h_output, d_output, 2 * sizeof(TrajectoryPoint), cudaMemcpyDeviceToHost));
    
    TEST_ASSERT_FLOAT_EQ(h_output[0].z, 100.0f, 1e-4f, "single start");
    TEST_ASSERT_FLOAT_EQ(h_output[1].z, 50.0f, 1e-3f, "single end");
    
    delete[] h_output;
    cudaFree(d_output);
    return true;
}

bool test_edge_case_zero_points() {
    // Test with num_points = 0 (edge case - should produce 1 point)
    DiveTrajectoryParams params = {
        .start_x = 0.0f,
        .start_y = 0.0f,
        .start_z = 100.0f,
        .target_alt = 50.0f,
        .dive_angle_deg = 45.0f,
        .max_speed = 25.0f,
        .max_dive_speed = 30.0f,
        .max_dive_angle_deg = 60.0f,
        .num_points = 0
    };
    
    TrajectoryPoint* d_output;
    CUDA_CHECK(cudaMalloc(&d_output, 1 * sizeof(TrajectoryPoint)));
    
    cudaError_t err = launch_geometric_dive_trajectory(params, d_output, 0);
    CUDA_CHECK(cudaDeviceSynchronize());
    
    TrajectoryPoint h_output;
    CUDA_CHECK(cudaMemcpy(&h_output, d_output, sizeof(TrajectoryPoint), cudaMemcpyDeviceToHost));
    
    TEST_ASSERT_FLOAT_EQ(h_output.z, 100.0f, 1e-4f, "zero points");
    
    cudaFree(d_output);
    return true;
}

bool test_large_num_points() {
    // Test with large number of points (stress test)
    const int num_points = 10000;
    
    DiveTrajectoryParams params = {
        .start_x = 0.0f,
        .start_y = 0.0f,
        .start_z = 1000.0f,
        .target_alt = 0.0f,
        .dive_angle_deg = 30.0f,
        .max_speed = 50.0f,
        .max_dive_speed = 60.0f,
        .max_dive_angle_deg = 45.0f,
        .num_points = num_points
    };
    
    TrajectoryPoint* d_output;
    CUDA_CHECK(cudaMalloc(&d_output, (num_points + 1) * sizeof(TrajectoryPoint)));
    
    cudaError_t err = launch_geometric_dive_trajectory(params, d_output, num_points);
    if (err != cudaSuccess) {
        cudaFree(d_output);
        return false;
    }
    
    CUDA_CHECK(cudaDeviceSynchronize());
    
    // Just verify it completes without error and check first/last
    TrajectoryPoint* h_output = new TrajectoryPoint[2];
    CUDA_CHECK(cudaMemcpy(h_output, d_output, 2 * sizeof(TrajectoryPoint), cudaMemcpyDeviceToHost));
    CUDA_CHECK(cudaMemcpy(&h_output[1], d_output + num_points, sizeof(TrajectoryPoint), cudaMemcpyDeviceToHost));
    
    TEST_ASSERT_FLOAT_EQ(h_output[0].z, 1000.0f, 1e-3f, "large start");
    TEST_ASSERT_FLOAT_EQ(h_output[1].z, 0.0f, 1e-3f, "large end");
    
    delete[] h_output;
    cudaFree(d_output);
    return true;
}

// =============================================================================
// Main Test Runner
// =============================================================================

int main(int argc, char** argv) {
    printf("========================================\n");
    printf("Q250-V3-Opti Trajectory Kernels Test Suite\n");
    printf("========================================\n\n");
    
    TestStats stats;
    
    // Run all tests
    stats.record(test_geometric_dive_basic(), "geometric_dive_basic");
    stats.record(test_geometric_dive_clamping(), "geometric_dive_speed_clamping");
    stats.record(test_geometric_dive_angle_clamping(), "geometric_dive_angle_clamping");
    stats.record(test_spiral_dive_basic(), "spiral_dive_basic");
    stats.record(test_spiral_dive_velocity(), "spiral_dive_velocity");
    stats.record(test_sine_dive_basic(), "sine_dive_basic");
    stats.record(test_jink_trajectory_basic(), "jink_trajectory_basic");
    stats.record(test_lut_interpolate_basic(), "lut_interpolate_basic");
    stats.record(test_lut_interpolate_identity(), "lut_interpolate_identity");
    stats.record(test_edge_case_single_point(), "edge_case_single_point");
    stats.record(test_edge_case_zero_points(), "edge_case_zero_points");
    stats.record(test_large_num_points(), "large_num_points_stress");
    
    stats.print_summary();
    
    return stats.exit_code();
}