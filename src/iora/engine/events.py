from __future__ import annotations

from iora.engine.models import Event, EventID

import pandas as pd


class EventBus:
    """
    Simple accumulator for engine events.

    Usage:
        bus = EventBus()
        bus.emit(EventID.ZONE_FIRE, ts, "H4", {"side": "supply", "top": 1.234})
        ...
        events = bus.drain()   # returns list and clears
    """

    def __init__(self) -> None:
        self._events: list[Event] = []

    def emit(
        self,
        event_id: EventID,
        timestamp: pd.Timestamp,
        timeframe: str,
        payload: dict | None = None,
    ) -> None:
        self._events.append(
            Event(
                id=event_id,
                timestamp=timestamp,
                timeframe=timeframe,
                payload=payload or {},
            )
        )

    def drain(self) -> list[Event]:
        """Return all accumulated events and clear the buffer."""
        out = list(self._events)
        self._events.clear()
        return out

    def peek(self) -> list[Event]:
        """Return events without clearing."""
        return list(self._events)

    def __len__(self) -> int:
        return len(self._events)
