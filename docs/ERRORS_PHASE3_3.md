# ERRORS_PHASE3_3.md

E3_3_DETECTOR_JSON_INVALID
- When TextBlockDetector returns invalid JSON
- Action: mark page as processed, emit structured error, do not crash whole job

E3_3_DETECTOR_TIMEOUT
- When detector call times out
- Action: same as above

E3_3_AMBIGUOUS_LABEL
- When a 2 to 4 digit token conflicts with door neighborhood evidence
- Action: return ambiguity true with ambiguity_reason, do not emit a confident room_number
