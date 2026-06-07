# SmartTraffic Instructions

## What Changed

The project now runs as a **simulation** based on frame-by-frame traffic vectors instead of reading `traffic.mp4`.

Each frame passes the number of cars in this fixed order:

```text
[North, East, South, West]
```

Example:

```text
[8, 3, 1, 5]
```

That means:

- `North = 8`
- `East = 3`
- `South = 1`
- `West = 5`

`traffic.mp4` and `intersection_points.json` are no longer used by the main simulation flow.

## Switching Logic

Each car is tracked separately inside the simulator. Since the input is still a count vector, the simulator infers individual cars like this:

- When a direction count increases, new cars are appended to that direction with `0` waiting seconds.
- When a direction count decreases, the oldest cars are treated as the cars that crossed or left.
- Cars on a green road have their wait reset because they are being served.
- Cars on red or yellow keep accumulating waiting time.

Each car starts with a priority of `1`.

```text
car score = car priority * waiting time
direction score = sum of all car scores in that direction
```

There are no wait-time multipliers in the normal score calculation.

Max-wait override:

- `MAX_WAIT_TIME_SECONDS` in `Values.py` starts at `120` seconds.
- If any vehicle waits longer than that limit, that lane becomes the forced next green.
- Forced service ignores normal lane scores and the cycle order.
- The forced lane remains protected until all vehicles on that lane are below the max-wait limit.

Switching behavior:

- A direction can skip the normal cycle only when its score clears the baseline priority score in `Values.py`.
- If no direction clears that baseline, the light continues in the normal `North -> East -> South -> West` cycle.
- The max-wait override is checked before normal score and cycle decisions.
- If the current green road has no cars left and another road has cars waiting, the controller starts switching early.
- Every switch goes through a `5` second yellow phase before the next road turns green.

## Main Files

- `Lights.py`: main simulator and visual runner
- `Switch.py`: light switching logic
- `Values.py`: configurable values such as minimum green, maximum green, yellow time, baseline score, and maximum wait time
- `detect.py`: vector parsing and custom scenario loading
- `test_cases.py`: built-in simulation test cases

## Setup Commands

Run these from the `SmartTraffic` folder:

```powershell
cd C:\Users\LM10\projects\SmartTraffic
.\setup_venv.ps1
.\.venv\Scripts\Activate.ps1
```

If the virtual environment already exists, you can just activate it:

```powershell
cd C:\Users\LM10\projects\SmartTraffic
.\.venv\Scripts\Activate.ps1
```

## Run Commands

Run the default visual simulation:

```powershell
python Lights.py
```

List all built-in test scenarios:

```powershell
python Lights.py --list-scenarios
```

Run a specific visual scenario:

```powershell
python Lights.py --scenario north_peak_then_east
```

Run a specific scenario without opening the window:

```powershell
python Lights.py --scenario max_green_rotation --headless
```

Run every built-in test case in sequence and print summaries:

```powershell
python Lights.py --run-all
```

Change the visual playback speed by adjusting the frame delay:

```powershell
python Lights.py --scenario rush_hour_wave --frame-delay-ms 700
```

## Runtime Keys

These keys work while the visual simulator window is open:

- `Space`: pause or resume the simulation
- `N`: load the next scenario
- `P`: load the previous scenario
- `R`: restart the current scenario from frame 1
- `S`: advance one frame while paused
- `Q`: quit the simulator
- `Esc`: quit the simulator

## Built-In Test Cases

These are defined in `test_cases.py`.

### `balanced_cycle`

- Purpose: balanced traffic where the busiest side changes gradually
- Expected result: the controller should rotate cleanly without starving any direction

### `north_peak_then_east`

- Purpose: North starts heavily loaded, then East becomes dominant
- Expected result: North should get the first green, then East should take over after the minimum hold

### `min_hold_protection`

- Purpose: the busiest side changes every frame
- Expected result: the light should not flicker every frame because minimum green time must be respected

### `max_green_rotation`

- Purpose: one side remains dominant for a long time
- Expected result: the controller should still rotate after reaching maximum green time

### `rush_hour_wave`

- Purpose: traffic demand moves around the intersection in waves
- Expected result: the green light should follow the moving heavy queue

### `empty_then_recovery`

- Purpose: the junction begins empty, then isolated queues appear later
- Expected result: the controller should recover from idle conditions and switch once real traffic appears

### `baseline_score_cycle_skip`

- Purpose: West waits long enough for its normal score to justify skipping South in the normal cycle
- Expected result: the controller should use the baseline priority score to skip directly to West without multipliers

### `max_wait_force_service`

- Purpose: one West car waits beyond the configured maximum wait time while North has the larger queue
- Expected result: West should become the forced next green once its wait exceeds 120 seconds, ignoring normal lane scores

## Custom Vector Input

You can also load your own scenario from a JSON file:

```powershell
python Lights.py --input .\my_scenario.json
```

Example JSON:

```json
{
  "slug": "custom_demo",
  "title": "Custom Demo",
  "description": "Simple custom test using frame vectors.",
  "expected_behavior": "Watch how the controller reacts to changing queues.",
  "frame_duration_seconds": 1.0,
  "frames": [
    [6, 2, 1, 0],
    [7, 2, 1, 0],
    [4, 8, 2, 1],
    {
      "counts": [2, 9, 3, 1],
      "note": "East becomes dominant"
    }
  ]
}
```

Each entry in `frames` can be:

- a 4-value array in `[North, East, South, West]` order
- or an object with a `counts` array and an optional `note`
