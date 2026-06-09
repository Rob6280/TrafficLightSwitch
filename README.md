# SmartTraffic - Adaptive Traffic Signal Control System

An intelligent traffic light controller that dynamically manages signal timing based on vehicle queue priorities and lane wait times.

## Overview

This project implements an adaptive traffic light control system that:

- **Prioritizes traffic lanes** by tracking cumulative lane wait times and vehicle queues
- **Prevents lane starvation** with a max-wait override that forces service to lanes exceeding the wait threshold
- **Balances traffic flow** using priority scoring across multiple directions
- **Manages signal phases** with green, yellow clearance, and smooth transitions

## Key Features

- **Dynamic Priority Scoring**: Combines vehicle count and cumulative wait time to determine the next green direction
- **Lane Starvation Prevention**: Forces the light to the direction whose lane has exceeded the maximum wait time
- **Yellow Clearance**: Implements a configurable yellow phase between direction changes
- **Configurable Thresholds**: Adjust minimum/maximum green times, baseline priority scores, and lane wait time limits

## How It Works

The `TrafficLightController` class monitors vehicle counts and lane wait times in each direction, updating every second:

1. Tracks vehicles in each lane and their cumulative wait times
2. Calculates lane wait times and priority scores for each direction
3. Checks for lane wait violations and forces service if the max-wait threshold is exceeded
4. Transitions between green and yellow phases based on traffic conditions
5. Returns detailed decision information including reasons for light changes

## Usage

```python
from Switch import TrafficLightController

controller = TrafficLightController()
decision = controller.update(
    counts={'north': 3, 'south': 1, 'east': 0, 'west': 2},
    elapsed_seconds=1.0
)

print(decision.direction)  # Current green direction
print(decision.reason)      # Explanation for this decision
```

## Configuration

Adjust these parameters in `Values.py`:

- `MIN_GREEN_SECONDS`: Minimum time a direction stays green
- `MAX_GREEN_SECONDS`: Maximum time a direction stays green
- `MAX_WAIT_TIME_SECONDS`: Maximum lane wait time before starvation prevention activates
- `YELLOW_SECONDS`: Duration of yellow clearance phase
- `BASELINE_PRIORITY_SCORE`: Score threshold required to switch directions
