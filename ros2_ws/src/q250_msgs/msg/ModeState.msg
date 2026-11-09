# Mode State
builtin_interfaces/msg/Time stamp
string mode  # CRUISE, FPV_AGILE, DIVE_ATTACK, DECEPTION, TRANSITION
string trigger  # MANUAL, AUTO, EMERGENCY
bool transition_active
string from_mode
string to_mode