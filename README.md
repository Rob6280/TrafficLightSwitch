# SmartTraffic - Adaptive Traffic Signal Control System

An intelligent traffic light controller that dynamically manages signal timing based on vehicle queue priorities and lane wait times.

## Screenshots

![Traffic Simulator]()

![YOLO detection]()

## Overview

SmartTraffic is a Python-based adaptive traffic signal management system that combines:

- Computer vision vehicle detection using YOLO
- Dynamic traffic signal control
- Lane-priority scheduling
- Starvation prevention mechanisms
- Interactive OpenCV simulation

The system can operate on both predefined traffic scenarios and vehicle counts obtained from real traffic video footage.

## System Architecture

**traffic.mp4**
    ↓
**YOLO Vehicle Detection**
    ↓
**Vehicle Counts Per Direction**
    ↓
**TrafficLightController**
    ↓
**Signal Decision Engine**
    ↓
**OpenCV Visualization**

## Project Structure

```text
SmartTraffic/
│
├── Lights.py        # Simulation UI and visualization
├── Switch.py        # Traffic signal controller logic
├── Values.py        # Configuration values
├── detect.py        # YOLO-based vehicle detection
├── test_cases.py    # Built-in traffic scenarios
│
├── traffic.mp4      # Input traffic video
├── requirements.txt
└── README.md
```

## Controller Logic

The controller evaluates each direction every simulation frame.
For each approach it tracks:

- Vehicle count
- Priority score
- Lane waiting time
- Current signal state

The controller then applies:

1. Minimum green time protection
2. Priority-based switching
3. Maximum green time enforcement
4. Lane starvation prevention
5. Yellow clearance handling

## Priority Scoring

Each vehicle accumulates waiting time while its lane is not being served.
Vehicle Score = Base Priority × Waiting Time
Lane Score = Sum of Vehicle Scores
A competing lane may request service once its score advantage exceeds the configurable threshold.

## Lane Starvation Prevention

Low-volume approaches can be ignored indefinitely by traditional priority systems.
To prevent this, each lane accumulates a lane wait timer whenever it is not receiving service.
If a lane exceeds:
MAX_WAIT_TIME_SECONDS
the controller activates a max-wait override and schedules that lane as the next green direction regardless of priority score.
This guarantees fairness while still favoring high-demand approaches most of the time.

## Included Test Scenarios

- balanced_cycle
- single_corridor_dominance
- rotating_rush_waves
- near_threshold_competition
- starvation_prevention
- detector_noise
- empty_intersection_recovery

## Running the Simulator

```bash
python Lights.py
```

### List Available Scenarios

```bash
python Lights.py --list-scenarios
```

### Run a Specific Scenario

```bash
python Lights.py --scenario balanced_cycle
```

### Run Headless

```bash
python Lights.py --headless
```

### Run All Scenarios

```bash
python Lights.py --run-all
```

## Future Improvements

- Multi-intersection coordination
- Emergency vehicle prioritization
- Pedestrian crossing support
- Live camera integration
- Reinforcement-learning based optimization
- Traffic analytics dashboard

## Configuration

Adjust these parameters in `Values.py`:

- `MIN_GREEN_SECONDS`: Minimum time a direction stays green
- `MAX_GREEN_SECONDS`: Maximum time a direction stays green
- `MAX_WAIT_TIME_SECONDS`: Maximum lane wait time before starvation prevention activates
- `YELLOW_SECONDS`: Duration of yellow clearance phase
- `BASELINE_PRIORITY_SCORE`: Score threshold required to switch directions
