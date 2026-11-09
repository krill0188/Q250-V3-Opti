# Non-GPS State
builtin_interfaces/msg/Time stamp
string device_id
string source  # VIO, OPTICAL_FLOW, LIDAR, FUSED, GPS

# Position (NED, meters)
float64 x
float64 y
float64 z

# Velocity (NED, m/s)
float64 vx
float64 vy
float64 vz

# Attitude (quaternion)
float64 qw
float64 qx
float64 qy
float64 qz

# 6x6 Covariance matrix (row-major)
float64[36] covariance

# Quality metrics
float32 position_quality  # 0.0 - 1.0
float32 velocity_quality
float32 attitude_quality
string status  # OK, DEGRADED, FAILED