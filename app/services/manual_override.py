from __future__ import annotations

_manual_override_channels: set[int] = set()


def mark_override(channel_index: int) -> None:
    _manual_override_channels.add(int(channel_index))


def clear_override(channel_index: int) -> None:
    _manual_override_channels.discard(int(channel_index))


def is_overridden(channel_index: int) -> bool:
    return int(channel_index) in _manual_override_channels


def active_overrides() -> set[int]:
    return set(_manual_override_channels)
