# Dive Trajectory
builtin_interfaces/msg/Time stamp
string method  # MPC, LUT, GEOMETRIC

# Waypoints (NED, meters)
float64[] waypoints_x
float64[] waypoints_y
float64[] waypoints_z

# Velocities (NED, m/s)
float64[] vel_x
float64[] vel_y
float64[] vel_z

# Timestamps (seconds from start)
float64[] timestamps

# Constraints
bool constraints_satisfied
float32 max_speed_used
float32 max_angle_used
float32 min_pullup_alt_used