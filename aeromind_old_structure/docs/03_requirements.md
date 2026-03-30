# System and Research Requirements

## Functional Requirements
- The system shall detect predefined static hand gestures from a live camera feed.
- The system shall map recognized gestures to drone control commands.
- The system shall display a live camera feed.
- The system shall provide a simulated drone visualization prior to real drone deployment.
- The system shall include a high-priority emergency stop gesture.
- The system shall log all predictions, commands, and timestamps.

## Non-Functional Requirements
- Gesture recognition latency shall not exceed 300 ms on average.
- Gesture recognition accuracy shall be at least 85%.
- The system shall fail safely when no valid gesture is detected.
- The system shall suppress commands below a confidence threshold.
- The system shall be modular and testable.

## Research Requirements
- The system shall support evaluation across multiple participants.
- The system shall operate under varying lighting, background, and distance conditions.
- The system shall collect sufficient data to compute defined metrics.
- The system shall enable reproducible experiments.
