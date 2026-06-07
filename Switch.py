from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from Values import (
    BASELINE_PRIORITY_SCORE,
    DEFAULT_CAR_PRIORITY,
    DIRECTIONS,
    MAX_GREEN_SECONDS,
    MAX_WAIT_TIME_SECONDS,
    MIN_GREEN_SECONDS,
    YELLOW_SECONDS,
)


SIGNAL_GREEN = "GREEN"
SIGNAL_YELLOW = "YELLOW"


@dataclass
class CarState:
    waiting_seconds: float = 0.0
    base_priority: float = DEFAULT_CAR_PRIORITY

    def priority_score(self) -> float:
        return self.base_priority * self.waiting_seconds


@dataclass(frozen=True)
class DirectionPriority:
    car_count: int
    score: float
    longest_wait_seconds: float
    has_over_max_wait: bool


@dataclass(frozen=True)
class SwitchDecision:
    direction: str
    phase: str
    changed: bool
    reason: str
    pending_direction: str | None
    forced_direction: str | None
    priority_scores: dict[str, float]
    longest_waits: dict[str, float]


@dataclass
class VehiclePriorityTracker:
    cars_by_direction: dict[str, list[CarState]] = field(
        default_factory=lambda: {direction: [] for direction in DIRECTIONS}
    )

    def update_from_counts(
        self,
        counts: Mapping[str, int],
        elapsed_seconds: float,
        *,
        green_direction: str | None,
        signal_phase: str,
    ) -> None:
        normalized_counts = _normalized_counts(counts)

        for direction in DIRECTIONS:
            cars = self.cars_by_direction[direction]
            target_count = normalized_counts[direction]

            if len(cars) > target_count:
                del cars[: len(cars) - target_count]
            elif len(cars) < target_count:
                cars.extend(
                    CarState()
                    for _ in range(target_count - len(cars))
                )

        for direction, cars in self.cars_by_direction.items():
            is_green_direction = (
                signal_phase == SIGNAL_GREEN and direction == green_direction
            )

            for car in cars:
                if is_green_direction:
                    car.waiting_seconds = 0.0
                else:
                    car.waiting_seconds += elapsed_seconds

    def reset_waits(self, direction: str) -> None:
        for car in self.cars_by_direction[direction]:
            car.waiting_seconds = 0.0

    def direction_priorities(
        self,
        max_wait_time_seconds: float = MAX_WAIT_TIME_SECONDS,
    ) -> dict[str, DirectionPriority]:
        priorities: dict[str, DirectionPriority] = {}

        for direction, cars in self.cars_by_direction.items():
            longest_wait = max(
                (car.waiting_seconds for car in cars),
                default=0.0,
            )
            priorities[direction] = DirectionPriority(
                car_count=len(cars),
                score=sum(car.priority_score() for car in cars),
                longest_wait_seconds=longest_wait,
                has_over_max_wait=any(
                    car.waiting_seconds > max_wait_time_seconds
                    for car in cars
                ),
            )

        return priorities


@dataclass
class TrafficLightController:
    current_direction: str | None = None
    signal_phase: str = SIGNAL_GREEN
    green_elapsed_seconds: float = 0.0
    yellow_elapsed_seconds: float = 0.0
    pending_direction: str | None = None
    min_green_seconds: float = MIN_GREEN_SECONDS
    max_green_seconds: float = MAX_GREEN_SECONDS
    yellow_seconds: float = YELLOW_SECONDS
    baseline_priority_score: float = BASELINE_PRIORITY_SCORE
    max_wait_time_seconds: float = MAX_WAIT_TIME_SECONDS
    forced_direction: str | None = None
    tracker: VehiclePriorityTracker = field(default_factory=VehiclePriorityTracker)

    def update(
        self,
        counts: Mapping[str, int],
        elapsed_seconds: float,
    ) -> SwitchDecision:
        normalized_counts = _normalized_counts(counts)
        self.tracker.update_from_counts(
            normalized_counts,
            elapsed_seconds,
            green_direction=self.current_direction,
            signal_phase=self.signal_phase,
        )

        if self.current_direction not in DIRECTIONS:
            return self._activate_initial_green()

        priorities = self.tracker.direction_priorities(self.max_wait_time_seconds)

        if self.signal_phase == SIGNAL_YELLOW:
            forced_target = self._max_wait_direction(priorities, include_current=True)
            redirected_by_force = False
            if forced_target is not None:
                self.forced_direction = forced_target
                if forced_target != self.pending_direction:
                    self.pending_direction = forced_target
                    redirected_by_force = True

            self.yellow_elapsed_seconds += elapsed_seconds
            if self.yellow_elapsed_seconds >= self.yellow_seconds:
                return self._finish_yellow()

            if redirected_by_force:
                forced_priority = priorities[forced_target]
                return self._decision(
                    changed=True,
                    reason=(
                        f"Max-wait override redirected the pending green to "
                        f"{self._direction_label(forced_target)} after a vehicle "
                        f"waited {forced_priority.longest_wait_seconds:.0f}s. "
                        f"Continuing yellow clearance first."
                    ),
                )

            return self._decision(
                changed=False,
                reason=(
                    f"Yellow clearance is active before switching to "
                    f"{self._direction_label(self.pending_direction)}."
                ),
            )

        self.green_elapsed_seconds += elapsed_seconds
        current_count = normalized_counts[self.current_direction]

        if self.forced_direction == self.current_direction:
            current_priority = priorities[self.current_direction]
            if current_priority.has_over_max_wait:
                return self._decision(
                    changed=False,
                    reason=(
                        f"Max-wait override keeps "
                        f"{self._direction_label(self.current_direction)} green "
                        f"until every vehicle there is below "
                        f"{self.max_wait_time_seconds:.0f}s."
                    ),
                )

            self.forced_direction = None

        forced_target = self._max_wait_direction(priorities)
        if forced_target is not None:
            forced_priority = priorities[forced_target]

            if forced_target == self.current_direction:
                self.forced_direction = forced_target
                return self._decision(
                    changed=False,
                    reason=(
                        f"{self._direction_label(forced_target)} has a vehicle "
                        f"waiting {forced_priority.longest_wait_seconds:.0f}s, "
                        f"above the {self.max_wait_time_seconds:.0f}s max. "
                        f"It stays green under max-wait override."
                    ),
                )

            self.forced_direction = forced_target
            return self._start_yellow(
                forced_target,
                (
                    f"{self._direction_label(forced_target)} has a vehicle waiting "
                    f"{forced_priority.longest_wait_seconds:.0f}s, above the "
                    f"{self.max_wait_time_seconds:.0f}s max. Max-wait override "
                    f"ignores lane scores and forces it as the next green."
                ),
            )

        if current_count == 0 and _has_waiting_traffic(normalized_counts, self.current_direction):
            target_direction, target_reason = self._select_next_target(priorities)
            return self._start_yellow(
                target_direction,
                (
                    f"{self._direction_label(self.current_direction)} has no cars "
                    f"left to serve. {target_reason}"
                ),
            )

        if self.green_elapsed_seconds < self.min_green_seconds:
            return self._decision(
                changed=False,
                reason="Holding green until the minimum green time is reached.",
            )

        target_direction, target_score = self._highest_priority_direction(priorities)
        if (
            target_direction is not None
            and target_direction != self.current_direction
            and target_score >= self.baseline_priority_score
        ):
            return self._start_yellow(
                target_direction,
                (
                    f"{self._direction_label(target_direction)} reached priority "
                    f"{target_score:.1f}, which clears the baseline "
                    f"{self.baseline_priority_score:.1f}."
                ),
            )

        if self.green_elapsed_seconds >= self.max_green_seconds:
            target_direction, target_reason = self._select_next_target(priorities)
            return self._start_yellow(
                target_direction,
                f"Maximum green time reached. {target_reason}",
            )

        return self._decision(
            changed=False,
            reason="Current green continues; no priority score clears the baseline.",
        )

    def _activate_initial_green(self) -> SwitchDecision:
        priorities = self.tracker.direction_priorities(self.max_wait_time_seconds)
        forced_target = self._max_wait_direction(priorities, include_current=True)

        if forced_target is not None:
            target_direction = forced_target
            target_score = priorities[target_direction].score
            longest_wait = priorities[target_direction].longest_wait_seconds
            self.forced_direction = target_direction
            reason = (
                f"Initial green forced to {self._direction_label(target_direction)} "
                f"because a vehicle waited {longest_wait:.0f}s, above the "
                f"{self.max_wait_time_seconds:.0f}s max."
            )
        else:
            target_direction, target_score = self._highest_priority_direction(
                priorities,
                include_current=True,
            )
            target_direction = target_direction or DIRECTIONS[0]
            self.forced_direction = None
            reason = (
                f"Initial green chosen from the highest priority score "
                f"({target_score:.1f})."
            )

        self.current_direction = target_direction
        self.signal_phase = SIGNAL_GREEN
        self.pending_direction = None
        self.green_elapsed_seconds = 0.0
        self.yellow_elapsed_seconds = 0.0
        self.tracker.reset_waits(self.current_direction)

        return self._decision(
            changed=True,
            reason=reason,
        )

    def _start_yellow(self, target_direction: str, reason: str) -> SwitchDecision:
        if target_direction == self.current_direction:
            return self._decision(
                changed=False,
                reason="Selected target is already active, so green continues.",
            )

        self.signal_phase = SIGNAL_YELLOW
        self.pending_direction = target_direction
        self.yellow_elapsed_seconds = 0.0

        return self._decision(
            changed=True,
            reason=f"{reason} Starting {self.yellow_seconds:.0f}s yellow clearance.",
        )

    def _finish_yellow(self) -> SwitchDecision:
        self.current_direction = self.pending_direction or _next_direction_in_cycle(
            self.current_direction
        )
        self.signal_phase = SIGNAL_GREEN
        self.pending_direction = None
        self.green_elapsed_seconds = 0.0
        self.yellow_elapsed_seconds = 0.0
        self.tracker.reset_waits(self.current_direction)

        if self.forced_direction != self.current_direction:
            self.forced_direction = None

        reason = (
            f"Yellow clearance complete. "
            f"{self._direction_label(self.current_direction)} is now green."
        )
        if self.forced_direction == self.current_direction:
            reason += " Max-wait forced service is active for this lane."

        return self._decision(
            changed=True,
            reason=reason,
        )

    def _select_next_target(
        self,
        priorities: Mapping[str, DirectionPriority],
    ) -> tuple[str, str]:
        cycle_direction = _next_direction_in_cycle(self.current_direction)
        best_direction, best_score = self._highest_priority_direction(priorities)

        if (
            best_direction is not None
            and best_direction != cycle_direction
            and best_score >= self.baseline_priority_score
        ):
            return (
                best_direction,
                (
                    f"Priority baseline allows skipping the cycle to "
                    f"{self._direction_label(best_direction)}."
                ),
            )

        return (
            cycle_direction,
            (
                f"Priority baseline was not met, so the next cycle direction is "
                f"{self._direction_label(cycle_direction)}."
            ),
        )

    def _highest_priority_direction(
        self,
        priorities: Mapping[str, DirectionPriority],
        *,
        include_current: bool = False,
    ) -> tuple[str | None, float]:
        best_direction: str | None = None
        best_score = -1.0

        for direction in DIRECTIONS:
            if not include_current and direction == self.current_direction:
                continue

            score = priorities[direction].score
            if score > best_score:
                best_direction = direction
                best_score = score

        return best_direction, max(best_score, 0.0)

    def _max_wait_direction(
        self,
        priorities: Mapping[str, DirectionPriority],
        *,
        include_current: bool = False,
    ) -> str | None:
        best_direction: str | None = None
        best_wait = self.max_wait_time_seconds
        best_score = -1.0

        for direction in DIRECTIONS:
            if not include_current and direction == self.current_direction:
                continue

            priority = priorities[direction]
            if not priority.has_over_max_wait:
                continue

            if (
                priority.longest_wait_seconds > best_wait
                or (
                    priority.longest_wait_seconds == best_wait
                    and priority.score > best_score
                )
            ):
                best_direction = direction
                best_wait = priority.longest_wait_seconds
                best_score = priority.score

        return best_direction

    def _decision(self, *, changed: bool, reason: str) -> SwitchDecision:
        priorities = self.tracker.direction_priorities(self.max_wait_time_seconds)

        return SwitchDecision(
            direction=self.current_direction or DIRECTIONS[0],
            phase=self.signal_phase,
            changed=changed,
            reason=reason,
            pending_direction=self.pending_direction,
            forced_direction=self.forced_direction,
            priority_scores={
                direction: priorities[direction].score
                for direction in DIRECTIONS
            },
            longest_waits={
                direction: priorities[direction].longest_wait_seconds
                for direction in DIRECTIONS
            },
        )

    def _direction_label(self, direction: str | None) -> str:
        if direction is None:
            return "the pending direction"

        return direction.title()


def choose_green_direction(
    current_direction: str | None,
    counts: Mapping[str, int],
    green_elapsed_seconds: float,
    *,
    min_green_seconds: float = MIN_GREEN_SECONDS,
    max_green_seconds: float = MAX_GREEN_SECONDS,
    baseline_priority_score: float = BASELINE_PRIORITY_SCORE,
    max_wait_time_seconds: float = MAX_WAIT_TIME_SECONDS,
) -> SwitchDecision:
    controller = TrafficLightController(
        current_direction=current_direction,
        green_elapsed_seconds=green_elapsed_seconds,
        min_green_seconds=min_green_seconds,
        max_green_seconds=max_green_seconds,
        baseline_priority_score=baseline_priority_score,
        max_wait_time_seconds=max_wait_time_seconds,
    )

    return controller.update(counts, elapsed_seconds=1.0)


def _normalized_counts(counts: Mapping[str, int]) -> dict[str, int]:
    return {direction: int(counts.get(direction, 0)) for direction in DIRECTIONS}


def _next_direction_in_cycle(current_direction: str | None) -> str:
    if current_direction not in DIRECTIONS:
        return DIRECTIONS[0]

    current_index = DIRECTIONS.index(current_direction)
    next_index = (current_index + 1) % len(DIRECTIONS)
    return DIRECTIONS[next_index]


def _has_waiting_traffic(counts: Mapping[str, int], current_direction: str) -> bool:
    return any(
        counts.get(direction, 0) > 0
        for direction in DIRECTIONS
        if direction != current_direction
    )
