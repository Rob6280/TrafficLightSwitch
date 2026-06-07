from __future__ import annotations

from detect import TrafficScenario, frame_from_input
from Values import DEFAULT_FRAME_DURATION_SECONDS, MAX_WAIT_TIME_SECONDS


def _segment(vector: tuple[int, int, int, int], frames: int, note: str) -> list:
    return [
        frame_from_input({"counts": vector, "note": note})
        for _ in range(frames)
    ]


def _build_scenarios() -> dict[str, TrafficScenario]:
    scenarios = [
        TrafficScenario(
            slug="balanced_cycle",
            title="Balanced Cycle",
            description=(
                "Traffic stays moderate on every side, with each direction becoming "
                "slightly busier in turn."
            ),
            expected_behavior=(
                "The signal should rotate smoothly without starving any side."
            ),
            frames=tuple(
                _segment((4, 4, 4, 4), 2, "Balanced opening")
                + _segment((6, 4, 3, 2), 3, "North takes a small lead")
                + _segment((3, 7, 4, 3), 3, "East becomes the busiest approach")
                + _segment((3, 3, 8, 4), 3, "South builds up late")
                + _segment((4, 3, 3, 9), 3, "West sees a strong surge")
                + _segment((4, 4, 4, 4), 2, "Queues normalize again")
            ),
            frame_duration_seconds=DEFAULT_FRAME_DURATION_SECONDS,
        ),
        TrafficScenario(
            slug="north_peak_then_east",
            title="North Peak Then East Recovery",
            description=(
                "North starts with a large queue, then East gradually overtakes it."
            ),
            expected_behavior=(
                "North should get the initial green, then the controller should move "
                "to East after the minimum hold is satisfied."
            ),
            frames=tuple(
                _segment((11, 2, 1, 2), 4, "North is heavily backed up")
                + _segment((9, 5, 2, 2), 3, "East begins building while North clears")
                + _segment((5, 10, 2, 2), 4, "East overtakes North")
                + _segment((3, 8, 4, 3), 3, "East remains dominant")
                + _segment((2, 4, 5, 3), 2, "Traffic settles across the junction")
            ),
            frame_duration_seconds=DEFAULT_FRAME_DURATION_SECONDS,
        ),
        TrafficScenario(
            slug="min_hold_protection",
            title="Minimum Hold Protection",
            description=(
                "The largest queue changes every frame to test whether the controller "
                "avoids flickering between directions."
            ),
            expected_behavior=(
                "The light should not thrash every second because minimum green time "
                "must be honored first."
            ),
            frames=tuple(
                frame_from_input({"counts": (9, 1, 1, 1), "note": "North spikes first"})
                for _ in range(1)
            )
            + tuple(
                frame_from_input(raw_frame)
                for raw_frame in (
                    {"counts": (1, 9, 1, 1), "note": "East suddenly becomes busiest"},
                    {"counts": (1, 1, 9, 1), "note": "South takes over next"},
                    {"counts": (1, 1, 1, 9), "note": "West spikes after South"},
                    {"counts": (9, 1, 1, 1), "note": "North returns to the lead"},
                    {"counts": (1, 9, 1, 1), "note": "East jumps again"},
                    {"counts": (1, 1, 9, 1), "note": "South rises again"},
                    {"counts": (1, 1, 1, 9), "note": "West rises again"},
                    {"counts": (9, 1, 1, 1), "note": "North spikes once more"},
                    {"counts": (1, 9, 1, 1), "note": "East spikes once more"},
                    {"counts": (1, 1, 9, 1), "note": "South spikes once more"},
                    {"counts": (1, 1, 1, 9), "note": "West spikes once more"},
                )
            ),
            frame_duration_seconds=DEFAULT_FRAME_DURATION_SECONDS,
        ),
        TrafficScenario(
            slug="max_green_rotation",
            title="Maximum Green Rotation",
            description=(
                "North stays dominant for a long time to confirm the signal does not "
                "stay green forever on one side."
            ),
            expected_behavior=(
                "Even with North remaining busy, the controller should rotate after "
                "maximum green time is reached."
            ),
            frames=tuple(
                _segment((15, 2, 2, 2), 8, "North remains clearly dominant")
                + _segment((14, 3, 2, 2), 5, "North still dominates past max hold")
                + _segment((10, 6, 2, 2), 5, "East grows while North remains busy")
            ),
            frame_duration_seconds=DEFAULT_FRAME_DURATION_SECONDS,
        ),
        TrafficScenario(
            slug="rush_hour_wave",
            title="Rush Hour Wave",
            description=(
                "Demand moves around the junction in a wave, similar to directional "
                "bursts during rush hour."
            ),
            expected_behavior=(
                "The controller should follow the moving wave and keep switching to "
                "the side that becomes dominant next."
            ),
            frames=tuple(
                _segment((3, 2, 1, 1), 3, "Light traffic before the rush")
                + _segment((2, 7, 2, 1), 3, "East receives the first wave")
                + _segment((1, 3, 9, 2), 3, "South becomes dominant next")
                + _segment((2, 2, 4, 10), 3, "West gets the strongest burst")
                + _segment((5, 4, 3, 2), 3, "North begins to recover")
                + _segment((2, 2, 2, 2), 3, "Rush hour fades out")
            ),
            frame_duration_seconds=DEFAULT_FRAME_DURATION_SECONDS,
        ),
        TrafficScenario(
            slug="empty_then_recovery",
            title="Empty Then Recovery",
            description=(
                "The junction starts empty, then isolated queues appear and compete."
            ),
            expected_behavior=(
                "The controller should react cleanly once real queues show up instead "
                "of remaining stuck in an idle state."
            ),
            frames=tuple(
                _segment((0, 0, 0, 0), 3, "No cars are waiting anywhere")
                + _segment((0, 0, 9, 0), 3, "A South queue appears suddenly")
                + _segment((0, 5, 6, 0), 3, "East begins competing with South")
                + _segment((0, 8, 2, 7), 3, "East and West are both heavily loaded")
            ),
            frame_duration_seconds=DEFAULT_FRAME_DURATION_SECONDS,
        ),
        TrafficScenario(
            slug="baseline_score_cycle_skip",
            title="Baseline Score Cycle Skip",
            description=(
                "West waits while North and East are served, then its normal "
                "priority score becomes large enough to skip South in the cycle."
            ),
            expected_behavior=(
                "The controller should move North to East by cycle first, then skip "
                "South and serve West once West clears the baseline score without "
                "using any wait-time multipliers."
            ),
            frames=tuple(
                _segment((8, 1, 1, 4), 18, "North is busy while West starts waiting")
                + _segment((5, 1, 1, 4), 8, "East is next in cycle; West keeps aging")
                + _segment((2, 1, 1, 4), 8, "West should now justify skipping South")
                + _segment((1, 1, 1, 0), 4, "West clears after receiving service")
            ),
            frame_duration_seconds=DEFAULT_FRAME_DURATION_SECONDS,
        ),
        TrafficScenario(
            slug="max_wait_force_service",
            title="Maximum Wait Force Service",
            description=(
                "A single West car waits beyond the configured maximum wait time "
                "while North has the larger queue."
            ),
            expected_behavior=(
                "West should become the forced next green once its wait exceeds "
                f"{MAX_WAIT_TIME_SECONDS:.0f} seconds, ignoring normal lane scores."
            ),
            frames=tuple(
                _segment((10, 0, 0, 1), 1, "North starts higher; West begins waiting")
                + _segment((10, 0, 0, 1), 1, "West crosses the maximum wait limit")
                + _segment((10, 0, 0, 1), 1, "Yellow completes before forced West green")
            ),
            frame_duration_seconds=61.0,
        ),
    ]

    return {scenario.slug: scenario for scenario in scenarios}


BUILTIN_SCENARIOS = _build_scenarios()
