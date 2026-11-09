# Risk Assessment
builtin_interfaces/msg/Time stamp
string risk_level  # CRITICAL, HIGH, MEDIUM, LOW
string[] risk_categories  # BATTERY_CRITICAL, MOTOR_OVERHEAT, etc.
float32 confidence
string reasoning
string[] recommended_actions  # JSON array of {action, priority, reason}
string[] auto_execute  # RTL, ESTOP, HOLD, etc.
float32 inference_ms