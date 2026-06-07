from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from Switch import SIGNAL_GREEN, SIGNAL_YELLOW, TrafficLightController
from Values import (
    ACTIVE_QUEUE_COLOR,
    BACKGROUND_COLOR,
    CAR_OUTLINE_COLOR,
    DEFAULT_FRAME_DELAY_MS,
    DEFAULT_SCENARIO,
    DIRECTIONS,
    DIRECTION_LABELS,
    FONT,
    FONT_SCALE,
    GREEN_LIGHT_COLOR,
    INTERSECTION_CENTER,
    INTERSECTION_COLOR,
    LANE_MARKING_COLOR,
    MAX_RENDERED_CARS_PER_SIDE,
    PANEL_BORDER_COLOR,
    PANEL_COLOR,
    QUEUE_STEP,
    RED_LIGHT_COLOR,
    ROAD_COLOR,
    ROAD_HALF_WIDTH,
    RUNTIME_KEY_HELP,
    SCENARIO_NOTE_COLOR,
    SUBTEXT_COLOR,
    TEXT_COLOR,
    TEXT_THICKNESS,
    VECTOR_ORDER_TEXT,
    WAITING_QUEUE_COLOR,
    WINDOW_HEIGHT,
    WINDOW_NAME,
    WINDOW_WIDTH,
    YELLOW_LIGHT_COLOR,
    YELLOW_QUEUE_COLOR,
)
from detect import TrafficScenario, load_scenario_from_json
from test_cases import BUILTIN_SCENARIOS


@dataclass
class SimulationState:
    frame_index: int = 0
    current_green: str | None = None
    signal_phase: str = SIGNAL_GREEN
    pending_direction: str | None = None
    forced_direction: str | None = None
    green_elapsed_seconds: float = 0.0
    yellow_elapsed_seconds: float = 0.0
    latest_counts: dict[str, int] = field(
        default_factory=lambda: {direction: 0 for direction in DIRECTIONS}
    )
    latest_vector: tuple[int, int, int, int] = (0, 0, 0, 0)
    latest_priority_scores: dict[str, float] = field(
        default_factory=lambda: {direction: 0.0 for direction in DIRECTIONS}
    )
    latest_longest_waits: dict[str, float] = field(
        default_factory=lambda: {direction: 0.0 for direction in DIRECTIONS}
    )
    latest_note: str = ""
    latest_reason: str = ""
    latest_time_seconds: float = 0.0
    switch_events: list[str] = field(default_factory=list)
    controller: TrafficLightController = field(default_factory=TrafficLightController)
    completed: bool = False


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the SmartTraffic queue simulator using frame vectors instead of video."
    )
    parser.add_argument(
        "--scenario",
        help="Built-in scenario slug to start with.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Optional path to a custom scenario JSON file.",
    )
    parser.add_argument(
        "--list-scenarios",
        action="store_true",
        help="Print the available built-in scenarios and exit.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run the scenario without opening the OpenCV window.",
    )
    parser.add_argument(
        "--run-all",
        action="store_true",
        help="Run all available scenarios sequentially in headless mode and print summaries.",
    )
    parser.add_argument(
        "--frame-delay-ms",
        type=int,
        default=DEFAULT_FRAME_DELAY_MS,
        help="Delay between frames in the visual simulator.",
    )
    return parser


def list_scenarios() -> None:
    print("Available built-in scenarios:\n")
    for scenario in BUILTIN_SCENARIOS.values():
        print(f"- {scenario.slug}")
        print(f"  Title: {scenario.title}")
        print(f"  Description: {scenario.description}")
        print(f"  Expected: {scenario.expected_behavior}")
        print(f"  Frames: {scenario.frame_count}")
        print()


def load_available_scenarios(args) -> tuple[list[TrafficScenario], int]:
    scenarios = list(BUILTIN_SCENARIOS.values())
    custom_scenario: TrafficScenario | None = None

    if args.input:
        custom_scenario = load_scenario_from_json(args.input)
        scenarios.append(custom_scenario)

    requested_slug = args.scenario
    if requested_slug is None:
        requested_slug = custom_scenario.slug if custom_scenario else DEFAULT_SCENARIO

    for index, scenario in enumerate(scenarios):
        if scenario.slug == requested_slug:
            return scenarios, index

    available_slugs = ", ".join(scenario.slug for scenario in scenarios)
    raise ValueError(
        f"Unknown scenario '{requested_slug}'. Available scenarios: {available_slugs}"
    )


def reset_state(scenario: TrafficScenario) -> SimulationState:
    state = SimulationState()
    apply_frame(state, scenario, 0)
    return state


def apply_frame(state: SimulationState, scenario: TrafficScenario, frame_index: int) -> None:
    frame = scenario.frames[frame_index]
    counts = frame.as_counts()
    decision = state.controller.update(
        counts,
        scenario.frame_duration_seconds,
    )

    state.frame_index = frame_index
    state.current_green = decision.direction
    state.signal_phase = decision.phase
    state.pending_direction = decision.pending_direction
    state.forced_direction = decision.forced_direction
    state.green_elapsed_seconds = state.controller.green_elapsed_seconds
    state.yellow_elapsed_seconds = state.controller.yellow_elapsed_seconds
    state.latest_counts = counts
    state.latest_vector = frame.as_vector()
    state.latest_priority_scores = decision.priority_scores
    state.latest_longest_waits = decision.longest_waits
    state.latest_note = frame.note
    state.latest_reason = decision.reason
    state.latest_time_seconds = (frame_index + 1) * scenario.frame_duration_seconds
    state.completed = frame_index >= scenario.frame_count - 1

    if decision.changed:
        event = (
            f"{state.latest_time_seconds:5.1f}s -> {format_signal(state)} | "
            f"{format_counts(counts)} | scores {format_scores(decision.priority_scores)}"
        )
        state.switch_events.append(event)
        print(f"[{scenario.slug}] {event}")


def format_counts(counts: dict[str, int]) -> str:
    return ", ".join(
        f"{DIRECTION_LABELS[direction]}={counts.get(direction, 0)}"
        for direction in DIRECTIONS
    )


def format_scores(scores: dict[str, float]) -> str:
    return ", ".join(
        f"{DIRECTION_LABELS[direction]}={scores.get(direction, 0.0):.1f}"
        for direction in DIRECTIONS
    )


def format_signal(state: SimulationState) -> str:
    label = DIRECTION_LABELS[state.current_green]
    if state.signal_phase == SIGNAL_YELLOW and state.pending_direction:
        signal_text = (
            f"{label} YELLOW -> "
            f"{DIRECTION_LABELS[state.pending_direction]} GREEN pending"
        )
    else:
        signal_text = f"{label} {state.signal_phase}"

    if state.forced_direction:
        signal_text += f" (forced {DIRECTION_LABELS[state.forced_direction]})"

    return signal_text


def wrap_text(text: str, max_chars: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]

    lines: list[str] = []
    current_line = words[0]

    for word in words[1:]:
        candidate = f"{current_line} {word}"
        if len(candidate) <= max_chars:
            current_line = candidate
        else:
            lines.append(current_line)
            current_line = word

    lines.append(current_line)
    return lines


def create_canvas():
    return np.full((WINDOW_HEIGHT, WINDOW_WIDTH, 3), BACKGROUND_COLOR, dtype=np.uint8)


def draw_intersection(canvas, signal_direction: str, signal_phase: str) -> None:
    center_x, center_y = INTERSECTION_CENTER

    cv2.rectangle(
        canvas,
        (center_x - ROAD_HALF_WIDTH, 0),
        (center_x + ROAD_HALF_WIDTH, WINDOW_HEIGHT),
        ROAD_COLOR,
        -1,
    )
    cv2.rectangle(
        canvas,
        (0, center_y - ROAD_HALF_WIDTH),
        (WINDOW_WIDTH, center_y + ROAD_HALF_WIDTH),
        ROAD_COLOR,
        -1,
    )
    cv2.rectangle(
        canvas,
        (center_x - ROAD_HALF_WIDTH, center_y - ROAD_HALF_WIDTH),
        (center_x + ROAD_HALF_WIDTH, center_y + ROAD_HALF_WIDTH),
        INTERSECTION_COLOR,
        -1,
    )

    _draw_lane_markings(canvas, center_x, center_y)
    _draw_signals(canvas, center_x, center_y, signal_direction, signal_phase)


def _draw_lane_markings(canvas, center_x: int, center_y: int) -> None:
    for y in range(20, center_y - ROAD_HALF_WIDTH - 10, 45):
        cv2.line(
            canvas,
            (center_x, y),
            (center_x, min(y + 20, center_y - ROAD_HALF_WIDTH - 10)),
            LANE_MARKING_COLOR,
            3,
        )

    for y in range(center_y + ROAD_HALF_WIDTH + 10, WINDOW_HEIGHT - 20, 45):
        cv2.line(
            canvas,
            (center_x, y),
            (center_x, min(y + 20, WINDOW_HEIGHT - 20)),
            LANE_MARKING_COLOR,
            3,
        )

    for x in range(20, center_x - ROAD_HALF_WIDTH - 10, 45):
        cv2.line(
            canvas,
            (x, center_y),
            (min(x + 20, center_x - ROAD_HALF_WIDTH - 10), center_y),
            LANE_MARKING_COLOR,
            3,
        )

    for x in range(center_x + ROAD_HALF_WIDTH + 10, WINDOW_WIDTH - 20, 45):
        cv2.line(
            canvas,
            (x, center_y),
            (min(x + 20, WINDOW_WIDTH - 20), center_y),
            LANE_MARKING_COLOR,
            3,
        )


def _draw_signals(
    canvas,
    center_x: int,
    center_y: int,
    signal_direction: str,
    signal_phase: str,
) -> None:
    signal_positions = {
        "NORTH": (center_x - 35, center_y - ROAD_HALF_WIDTH - 25),
        "EAST": (center_x + ROAD_HALF_WIDTH + 25, center_y - 35),
        "SOUTH": (center_x + 35, center_y + ROAD_HALF_WIDTH + 25),
        "WEST": (center_x - ROAD_HALF_WIDTH - 25, center_y + 35),
    }

    for direction, position in signal_positions.items():
        if direction == signal_direction and signal_phase == SIGNAL_GREEN:
            color = GREEN_LIGHT_COLOR
        elif direction == signal_direction and signal_phase == SIGNAL_YELLOW:
            color = YELLOW_LIGHT_COLOR
        else:
            color = RED_LIGHT_COLOR

        cv2.circle(canvas, position, 13, color, -1)
        cv2.circle(canvas, position, 13, CAR_OUTLINE_COLOR, 2)


def draw_queues(
    canvas,
    counts: dict[str, int],
    signal_direction: str,
    signal_phase: str,
) -> None:
    center_x, center_y = INTERSECTION_CENTER
    queue_positions = {
        "NORTH": ((center_x, center_y - ROAD_HALF_WIDTH - 40), (0, -QUEUE_STEP)),
        "EAST": ((center_x + ROAD_HALF_WIDTH + 45, center_y), (QUEUE_STEP, 0)),
        "SOUTH": ((center_x, center_y + ROAD_HALF_WIDTH + 40), (0, QUEUE_STEP)),
        "WEST": ((center_x - ROAD_HALF_WIDTH - 45, center_y), (-QUEUE_STEP, 0)),
    }

    for direction in DIRECTIONS:
        count = counts.get(direction, 0)
        if direction == signal_direction and signal_phase == SIGNAL_GREEN:
            color = ACTIVE_QUEUE_COLOR
        elif direction == signal_direction and signal_phase == SIGNAL_YELLOW:
            color = YELLOW_QUEUE_COLOR
        else:
            color = WAITING_QUEUE_COLOR

        start_position, step = queue_positions[direction]
        drawn_count = min(count, MAX_RENDERED_CARS_PER_SIDE)

        for index in range(drawn_count):
            car_center = (
                start_position[0] + step[0] * index,
                start_position[1] + step[1] * index,
            )
            _draw_car(canvas, car_center, color)

        if count > MAX_RENDERED_CARS_PER_SIDE:
            extra_label_position = (
                start_position[0] + step[0] * MAX_RENDERED_CARS_PER_SIDE,
                start_position[1] + step[1] * MAX_RENDERED_CARS_PER_SIDE,
            )
            cv2.putText(
                canvas,
                f"+{count - MAX_RENDERED_CARS_PER_SIDE}",
                (extra_label_position[0] - 15, extra_label_position[1] + 5),
                FONT,
                FONT_SCALE,
                TEXT_COLOR,
                TEXT_THICKNESS,
            )


def _draw_car(canvas, center: tuple[int, int], color: tuple[int, int, int]) -> None:
    car_half_width = 18
    car_half_height = 11
    top_left = (center[0] - car_half_width, center[1] - car_half_height)
    bottom_right = (center[0] + car_half_width, center[1] + car_half_height)
    cv2.rectangle(canvas, top_left, bottom_right, color, -1)
    cv2.rectangle(canvas, top_left, bottom_right, CAR_OUTLINE_COLOR, 2)


def draw_information_panels(
    canvas,
    scenario: TrafficScenario,
    state: SimulationState,
    paused: bool,
) -> None:
    _draw_panel(canvas, (20, 20), (420, 320))
    _draw_panel(canvas, (760, 20), (1165, 350))
    _draw_panel(canvas, (20, 610), (1165, 790))

    cv2.putText(canvas, scenario.title, (35, 55), FONT, 0.82, TEXT_COLOR, 2)
    cv2.putText(
        canvas,
        f"Scenario slug: {scenario.slug}",
        (35, 85),
        FONT,
        FONT_SCALE,
        SUBTEXT_COLOR,
        1,
    )
    cv2.putText(
        canvas,
        f"Frame: {state.frame_index + 1}/{scenario.frame_count}",
        (35, 120),
        FONT,
        FONT_SCALE,
        TEXT_COLOR,
        TEXT_THICKNESS,
    )
    cv2.putText(
        canvas,
        f"Simulated time: {state.latest_time_seconds:4.1f}s",
        (35, 150),
        FONT,
        FONT_SCALE,
        TEXT_COLOR,
        TEXT_THICKNESS,
    )
    cv2.putText(
        canvas,
        f"Signal: {format_signal(state)}",
        (35, 180),
        FONT,
        FONT_SCALE,
        YELLOW_LIGHT_COLOR if state.signal_phase == SIGNAL_YELLOW else GREEN_LIGHT_COLOR,
        TEXT_THICKNESS,
    )
    cv2.putText(
        canvas,
        f"Green held: {state.green_elapsed_seconds:4.1f}s",
        (35, 210),
        FONT,
        FONT_SCALE,
        TEXT_COLOR,
        TEXT_THICKNESS,
    )
    cv2.putText(
        canvas,
        f"Yellow held: {state.yellow_elapsed_seconds:4.1f}s",
        (35, 240),
        FONT,
        FONT_SCALE,
        TEXT_COLOR,
        TEXT_THICKNESS,
    )
    cv2.putText(
        canvas,
        f"Vector {VECTOR_ORDER_TEXT}: {list(state.latest_vector)}",
        (35, 270),
        FONT,
        FONT_SCALE,
        TEXT_COLOR,
        TEXT_THICKNESS,
    )

    status_text = "Paused" if paused else "Running"
    if state.completed:
        status_text = "Completed"
    cv2.putText(
        canvas,
        f"Status: {status_text}",
        (35, 300),
        FONT,
        FONT_SCALE,
        SCENARIO_NOTE_COLOR,
        TEXT_THICKNESS,
    )

    _draw_multiline_text(
        canvas,
        "Description: " + scenario.description,
        (775, 55),
        max_chars=42,
        color=TEXT_COLOR,
    )
    _draw_multiline_text(
        canvas,
        "Expected: " + scenario.expected_behavior,
        (775, 145),
        max_chars=42,
        color=TEXT_COLOR,
    )
    _draw_multiline_text(
        canvas,
        "Controller reason: " + state.latest_reason,
        (775, 235),
        max_chars=42,
        color=SCENARIO_NOTE_COLOR,
    )

    row_y = 645
    for direction in DIRECTIONS:
        if direction == state.current_green and state.signal_phase == SIGNAL_GREEN:
            color = GREEN_LIGHT_COLOR
        elif direction == state.current_green and state.signal_phase == SIGNAL_YELLOW:
            color = YELLOW_LIGHT_COLOR
        else:
            color = TEXT_COLOR

        text = (
            f"{DIRECTION_LABELS[direction]}: "
            f"cars {state.latest_counts.get(direction, 0)}, "
            f"score {state.latest_priority_scores.get(direction, 0.0):.1f}, "
            f"wait {state.latest_longest_waits.get(direction, 0.0):.0f}s"
        )
        cv2.putText(canvas, text, (35, row_y), FONT, FONT_SCALE, color, TEXT_THICKNESS)
        row_y += 30

    cv2.putText(canvas, "Keys", (420, 645), FONT, 0.72, TEXT_COLOR, 2)
    row_y = 680
    for key_label, key_help in RUNTIME_KEY_HELP:
        cv2.putText(
            canvas,
            f"{key_label}: {key_help}",
            (420, row_y),
            FONT,
            FONT_SCALE,
            TEXT_COLOR,
            TEXT_THICKNESS,
        )
        row_y += 27

    note_text = state.latest_note or "No frame note for this step."
    _draw_multiline_text(
        canvas,
        "Frame note: " + note_text,
        (760, 645),
        max_chars=48,
        color=SCENARIO_NOTE_COLOR,
    )


def _draw_panel(canvas, top_left: tuple[int, int], bottom_right: tuple[int, int]) -> None:
    cv2.rectangle(canvas, top_left, bottom_right, PANEL_COLOR, -1)
    cv2.rectangle(canvas, top_left, bottom_right, PANEL_BORDER_COLOR, 2)


def _draw_multiline_text(
    canvas,
    text: str,
    origin: tuple[int, int],
    *,
    max_chars: int,
    color: tuple[int, int, int],
) -> None:
    row_y = origin[1]
    for line in wrap_text(text, max_chars):
        cv2.putText(
            canvas,
            line,
            (origin[0], row_y),
            FONT,
            FONT_SCALE,
            color,
            TEXT_THICKNESS,
        )
        row_y += 28


def render_frame(scenario: TrafficScenario, state: SimulationState, paused: bool):
    canvas = create_canvas()
    draw_intersection(canvas, state.current_green, state.signal_phase)
    draw_queues(canvas, state.latest_counts, state.current_green, state.signal_phase)
    draw_information_panels(canvas, scenario, state, paused)
    return canvas


def run_headless_scenario(scenario: TrafficScenario) -> None:
    state = reset_state(scenario)
    while state.frame_index < scenario.frame_count - 1:
        apply_frame(state, scenario, state.frame_index + 1)
    print_headless_summary(scenario, state)


def print_headless_summary(scenario: TrafficScenario, state: SimulationState) -> None:
    print()
    print(f"Scenario: {scenario.title} ({scenario.slug})")
    print(f"Description: {scenario.description}")
    print(f"Expected behavior: {scenario.expected_behavior}")
    print(f"Frames simulated: {scenario.frame_count}")
    print(f"Final queues: {format_counts(state.latest_counts)}")
    print(f"Final scores: {format_scores(state.latest_priority_scores)}")
    print(f"Final signal: {format_signal(state)}")
    print("Switch events:")
    if not state.switch_events:
        print("  No switch events recorded.")
    else:
        for event in state.switch_events:
            print(f"  {event}")


def run_interactive(scenarios: list[TrafficScenario], start_index: int, frame_delay_ms: int) -> None:
    scenario_index = start_index
    scenario = scenarios[scenario_index]
    state = reset_state(scenario)
    paused = False

    while True:
        scenario = scenarios[scenario_index]
        frame_image = render_frame(scenario, state, paused)
        cv2.imshow(WINDOW_NAME, frame_image)

        delay = 80 if paused else max(1, frame_delay_ms)
        key = cv2.waitKey(delay) & 0xFF

        if key in (ord("q"), ord("Q"), 27):
            break

        if key == ord(" "):
            paused = not paused
            continue

        if key in (ord("r"), ord("R")):
            state = reset_state(scenario)
            paused = False
            continue

        if key in (ord("n"), ord("N")):
            scenario_index = (scenario_index + 1) % len(scenarios)
            scenario = scenarios[scenario_index]
            state = reset_state(scenario)
            paused = False
            continue

        if key in (ord("p"), ord("P")):
            scenario_index = (scenario_index - 1) % len(scenarios)
            scenario = scenarios[scenario_index]
            state = reset_state(scenario)
            paused = False
            continue

        if key in (ord("s"), ord("S")) and paused:
            if state.frame_index < scenario.frame_count - 1:
                apply_frame(state, scenario, state.frame_index + 1)
            else:
                state.completed = True
            continue

        if paused:
            continue

        if state.frame_index < scenario.frame_count - 1:
            apply_frame(state, scenario, state.frame_index + 1)
        else:
            paused = True
            state.completed = True

    cv2.destroyAllWindows()


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    if args.list_scenarios:
        list_scenarios()
        return

    scenarios, start_index = load_available_scenarios(args)

    if args.run_all:
        for scenario in scenarios:
            run_headless_scenario(scenario)
        return

    if args.headless:
        run_headless_scenario(scenarios[start_index])
        return

    run_interactive(scenarios, start_index, args.frame_delay_ms)


if __name__ == "__main__":
    main()
