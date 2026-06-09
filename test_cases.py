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
            title="balanced_cycle",
            description=(
                "Typical daytime traffic. Demand fluctuates gradually "
                "across all four approaches."
            ),
            expected_behavior=(
                "The signal should rotate smoothly without starving any side."
            ),
            frames=tuple(
                _segment((3, 3, 2, 2), 10, "Light traffic")
                + _segment((4, 3, 2, 2), 10, "North slightly higher")
                + _segment((4, 4, 3, 2), 10, "Balanced growth")
                + _segment((5, 4, 3, 3), 10, "Moderate flow")
                + _segment((5, 5, 4, 3), 10, "Balanced")
                + _segment((5, 5, 5, 4), 10, "Wait time Exceeded North")
                + _segment((5, 5, 5, 5), 10, "Wait time Exceeded East")
                + _segment((4, 4, 5, 5), 10, "Wait time Exceeded South")
                + _segment((5, 5, 4, 5), 10, "Wait time Exceeded West")
                + _segment((4, 5, 4, 4), 10, "Return to light flow")
            ),
        ),
        TrafficScenario(
            slug="single_corridor_dominance",
            title="Single Corridor Dominance",
            description=(
                "One approach remains significantly busier than the others "
                "for an extended period."
            ),
            expected_behavior=(
                "The signal should switch back to north after min green."
            ),
            frames=tuple(
                _segment((12, 2, 2, 2), 25, "North dominant")
                + _segment((10, 3, 2, 2), 25, "North remains dominant")
                + _segment((8, 3, 3, 2), 25, "North easing")
                + _segment((6, 4, 4, 3), 25, "Traffic normalizing")
            ),
        ),
        TrafficScenario(
            slug="rotating_rush_waves",
            title="Rotating Rush Waves",
            description=(
                "Demand rotates around the intersection, simulating changing "
                "traffic patterns over time."
            ),
            expected_behavior=(
                "The signal should rotate smoothly to serve the busy lanes."
            ),
            frames=tuple(
                _segment((12, 2, 2, 2), 25, "North rush")
                + _segment((2, 12, 2, 4), 25, "East rush")
                + _segment((4, 2, 12, 2), 25, "South rush")
                + _segment((2, 2, 2, 12), 25, "West rush")
            ),
        ),
        TrafficScenario(
            slug="near_threshold_competition",
            title="Near Threshold Competition",
            description=(
                "Traffic remains competitive between approaches without "
                "creating large score advantages."
            ),
            expected_behavior=(
                "The signal should rotate smoothly without skipping."
            ),
            frames=tuple(
                _segment((7, 6, 5, 5), 25, "North slightly ahead")
                + _segment((6, 7, 5, 5), 25, "East slightly ahead")
                + _segment((5, 6, 7, 5), 25, "South slightly ahead")
                + _segment((5, 5, 6, 7), 25, "West slightly ahead")
            ),
        ),
        TrafficScenario(
            slug="starvation_prevention",
            title="Starvation Prevention",
            description=(
                "One heavily demanded approach competes against "
                "low-volume approaches to test fairness mechanisms."
            ),
            expected_behavior=(
                "The signal should ensure that one side is not starved for too long."
            ),
            frames=tuple(
                _segment((8, 2, 2, 2), 25, "North busy")
                + _segment((8, 2, 2, 2), 25, "North still busy")
                + _segment((8, 2, 2, 2), 25, "North still busy")
                + _segment((8, 2, 2, 2), 25, "North still busy")
            ),
        ),
        TrafficScenario(
            slug="detector_noise",
            title="Detector Noise",
            description=(
                "Small count fluctuations intended to "
                "emulate noisy detector measurements."
            ),
            expected_behavior=(
                "The signal should rotate smoothly without starving any side."
            ),
            frames=tuple(
                (
                    _segment((6, 5, 5, 5), 5, "Noise")
                    + _segment((5, 6, 5, 5), 5, "Noise")
                    + _segment((6, 5, 6, 5), 5, "Noise")
                    + _segment((5, 5, 6, 6), 5, "Noise")
                    + _segment((7, 5, 5, 4), 5, "Noise")
                    + _segment((5, 7, 4, 5), 5, "Noise")
                    + _segment((6, 4, 7, 5), 5, "Noise")
                    + _segment((5, 5, 4, 7), 5, "Noise")
                ) * 2
                + _segment((6, 5, 5, 5), 10, "Stabilizing")
                + _segment((5, 6, 5, 5), 10, "Stabilizing")
            ),
        ),
        TrafficScenario(
            slug="empty_intersection_recovery",
            title="Empty Intersection Recovery",
            description=(
                "Tests recovery from an idle state once vehicles begin "
                "appearing at the intersection."
            ),
            expected_behavior=(
                "The signal should recover smoothly from an idle state."
            ),
            frames=tuple(
                _segment((0, 0, 0, 0), 25, "Empty")
                + _segment((0, 0, 0, 0), 25, "Still empty")
                + _segment((4, 2, 2, 2), 25, "Traffic appears")
                + _segment((6, 3, 2, 2), 25, "North builds")
            ),
        ),
    ]


    return {scenario.slug: scenario for scenario in scenarios}


BUILTIN_SCENARIOS = _build_scenarios()
