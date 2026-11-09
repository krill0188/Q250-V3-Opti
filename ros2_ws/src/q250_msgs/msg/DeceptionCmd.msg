# Deception Command
builtin_interfaces/msg/Time stamp
string pattern  # SPIRAL_DIVE, SINE_DIVE, RANDOM_JINK, FAKE_CRASH, MULTI_PULSE
float32 duration
float32 intensity  # 0.0 - 1.0
float32[] params  # pattern-specific: radius, turns, descent_rate, etc.
bool auto_select  # true if auto-selected by threat assessor