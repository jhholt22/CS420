# optional 
# Research Methodology

## System Overview
The AeroMind system implements real-time hand-gesture-based control of a consumer drone (DJI Tello TLW004). Gesture recognition and decision-making are performed offboard on a laptop using a live camera feed. Drone commands are transmitted over a Wi-Fi connection using the Tello SDK.

The system is designed to prioritize safety and robustness over speed, using static gestures, confidence thresholds, and fail-safe behaviors.

## Gesture Recognition
- Input: RGB frames from a webcam
- Method: Pre-trained hand landmark detection and gesture classification
- Output: Gesture label with confidence score
- Only static gestures are considered

## Control Logic
- Gestures are mapped to discrete drone commands
- Commands are issued only if:
  - Gesture confidence exceeds a predefined threshold
  - Gesture is stable over a short time window
  - Safety rules permit the command
- An emergency stop gesture overrides all other commands

## Safety Mechanisms
- Confidence thresholding to suppress uncertain commands
- Command cooldown to prevent rapid repeated actions
- Automatic hover or no-action when no valid gesture is detected
- Emergency stop gesture with highest priority

## Experimental Procedure
- Participants perform predefined gestures under controlled conditions
- Each trial is logged with timestamps, predicted gesture, confidence, and issued command
- Experiments are repeated across lighting, background, and distance variations

## Data Collection
- All trials are logged automatically
- No personal identifying information is collected
- Data is stored in CSV format for later analysis

## Evaluation
- Gesture recognition performance is evaluated using accuracy, precision, recall, and confusion matrices
- System behavior is evaluated using latency and safety metrics
- Results are analyzed per participant and per condition
