#Purpose: Thread-safe event queue/router. Sensors publish events; main consumes them.
#Inputs: Event objects published by sensors/active discovery.
#Outputs: Events returned to the consumer loop; supports publish(event) and get() semantics.

from __future__ import annotations

import threading
from dataclasses import dataclass
from queue import Queue, Empty, Full
from typing import Any, Optional


_sentinel = object()


@dataclass
class bus_stats:
    published: int = 0
    dropped: int = 0  # drops due to full queues
    subscribers: int = 0


class subscription:
    """
    A subscriber handle for consuming events from the bus.
    """

    def __init__(self, name: str, queue: Queue[Any], closed_event: threading.Event) -> None:
        self._name = name
        self._queue = queue
        self._closed_event = closed_event

    @property
    def name(self) -> str:
        return self._name

    def get(self, timeout: float = 0.0) -> Optional[Any]:
        """
        Returns:
          - event object, if available
          - None, if timeout expires OR bus closed and drained
        """
        if self._closed_event.is_set() and self._queue.empty():
            return None

        try:
            item = self._queue.get(timeout=timeout) if timeout else self._queue.get_nowait()
        except Empty:
            return None

        if item is _sentinel:
            # bus is closed; drain complete signal
            return None

        return item

    def size(self) -> int:
        return self._queue.qsize()


class event_bus:
    """
    Thread-safe publish/subscribe event bus.

    Key guarantees:
      - publish() broadcasts to all current subscribers
      - slow subscribers cannot block publishers (drop-if-full by default)
      - close() cleanly stops subscribers
    """

    def __init__(self, per_subscriber_max_size: int = 10000, drop_if_full: bool = True) -> None:
        self._lock = threading.Lock()
        self._subscribers: dict[str, Queue[Any]] = {}
        self._closed_event = threading.Event()

        self._per_subscriber_max_size = per_subscriber_max_size
        self._drop_if_full = drop_if_full

        self._published_count = 0
        self._dropped_count = 0

    def subscribe(self, name: str) -> subscription:
        """
        Register (or replace) a subscriber queue.
        Each subscriber gets its own queue to avoid cross-consumer interference.
        """
        with self._lock:
            q: Queue[Any] = Queue(maxsize=self._per_subscriber_max_size)
            self._subscribers[name] = q
            return subscription(name=name, queue=q, closed_event=self._closed_event)

    def unsubscribe(self, name: str) -> None:
        """
        Remove a subscriber from the bus. Safe to call multiple times.
        """
        with self._lock:
            self._subscribers.pop(name, None)

    def publish(self, event: Any) -> None:
        """
        Broadcast an event to all subscribers.

        If drop_if_full is True, slow subscribers may miss events instead of blocking publishers.
        If drop_if_full is False, publish will block when any subscriber queue is full.
        """
        if self._closed_event.is_set():
            return

        with self._lock:
            self._published_count += 1
            subscriber_queues = list(self._subscribers.values())

        for q in subscriber_queues:
            if self._drop_if_full:
                try:
                    q.put_nowait(event)
                except Full:
                    self._dropped_count += 1
            else:
                q.put(event)

    def close(self) -> None:
        """
        Close the bus and wake any subscribers waiting on get().
        After close(), publish() becomes a no-op.
        """
        if self._closed_event.is_set():
            return

        self._closed_event.set()

        with self._lock:
            subscriber_queues = list(self._subscribers.values())

        # Push sentinel so blocking consumers can wake and exit cleanly.
        for q in subscriber_queues:
            try:
                q.put_nowait(_sentinel)
            except Full:
                # If it's full, consumers are already behind; they will eventually
                # drain and then observe closed_event + empty => None.
                pass

    def is_closed(self) -> bool:
        return self._closed_event.is_set()

    def stats(self) -> bus_stats:
        with self._lock:
            subs = len(self._subscribers)
        return bus_stats(
            published=self._published_count,
            dropped=self._dropped_count,
            subscribers=subs,
        )