from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from Values import DEFAULT_FRAME_DURATION_SECONDS, DIRECTIONS


_DIRECTION_ALIASES = {
    "NORTH": ("NORTH", "north", "n"),
    "EAST": ("EAST", "east", "e"),
    "SOUTH": ("SOUTH", "south", "s"),
    "WEST": ("WEST", "west", "w"),
}


@dataclass(frozen=True)
class TrafficFrame:
    counts: tuple[int, int, int, int]
    note: str = ""

    def as_counts(self) -> dict[str, int]:
        return {
            direction: self.counts[index]
            for index, direction in enumerate(DIRECTIONS)
        }

    def as_vector(self) -> tuple[int, int, int, int]:
        return self.counts


@dataclass(frozen=True)
class TrafficScenario:
    slug: str
    title: str
    description: str
    expected_behavior: str
    frames: tuple[TrafficFrame, ...]
    frame_duration_seconds: float = DEFAULT_FRAME_DURATION_SECONDS

    @property
    def frame_count(self) -> int:
        return len(self.frames)


def frame_from_input(raw_frame, *, note: str = "") -> TrafficFrame:
    if isinstance(raw_frame, TrafficFrame):
        return raw_frame

    if isinstance(raw_frame, Mapping):
        local_note = str(raw_frame.get("note", note)).strip()

        if "counts" in raw_frame:
            return frame_from_input(raw_frame["counts"], note=local_note)

        counts = [
            _validated_count(_get_mapping_value(raw_frame, direction), direction)
            for direction in DIRECTIONS
        ]
        return TrafficFrame(tuple(counts), note=local_note)

    if isinstance(raw_frame, Sequence) and not isinstance(raw_frame, (str, bytes)):
        if len(raw_frame) != len(DIRECTIONS):
            raise ValueError(
                f"Each frame vector must contain exactly {len(DIRECTIONS)} values in "
                f"{DIRECTIONS} order."
            )

        counts = [
            _validated_count(value, direction)
            for value, direction in zip(raw_frame, DIRECTIONS)
        ]
        return TrafficFrame(tuple(counts), note=note.strip())

    raise TypeError(
        "Frame input must be a 4-value vector, a direction mapping, or a TrafficFrame."
    )


def load_scenario_from_json(path: Path) -> TrafficScenario:
    raw_data = json.loads(path.read_text(encoding="utf-8"))
    raw_frames = raw_data.get("frames")
    if not raw_frames:
        raise ValueError("Custom scenario JSON must include a non-empty 'frames' list.")

    frames = tuple(frame_from_input(raw_frame) for raw_frame in raw_frames)
    frame_duration_seconds = float(
        raw_data.get("frame_duration_seconds", DEFAULT_FRAME_DURATION_SECONDS)
    )

    return TrafficScenario(
        slug=str(raw_data.get("slug") or path.stem),
        title=str(raw_data.get("title") or path.stem.replace("_", " ").title()),
        description=str(raw_data.get("description") or "Custom input scenario."),
        expected_behavior=str(
            raw_data.get("expected_behavior")
            or "Observe how the controller switches based on the supplied vectors."
        ),
        frames=frames,
        frame_duration_seconds=frame_duration_seconds,
    )


def _get_mapping_value(raw_frame: Mapping[str, object], direction: str):
    for alias in _DIRECTION_ALIASES[direction]:
        if alias in raw_frame:
            return raw_frame[alias]

    raise KeyError(f"Frame mapping is missing a value for {direction}.")


def _validated_count(value, direction: str) -> int:
    count = int(value)
    if count < 0:
        raise ValueError(f"Vehicle counts cannot be negative. Invalid value for {direction}.")
    return count
