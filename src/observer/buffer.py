from collections import deque
from datetime import datetime, timezone


class FrameBuffer:
    def __init__(self, window_seconds: int = 5, sample_rate: int = 2):
        self._window_seconds = window_seconds
        self._sample_rate = sample_rate
        self._frames: deque[tuple[str, bytes]] = deque()
        self._window_start: float | None = None

    @property
    def expected_frame_count(self) -> int:
        return self._window_seconds * self._sample_rate

    def add_frame(self, frame_data: bytes) -> None:
        now = datetime.now(timezone.utc)
        if self._window_start is None:
            self._window_start = now.timestamp()
        self._frames.append((now.isoformat(), frame_data))

    def should_dispatch(self) -> bool:
        if not self._frames or self._window_start is None:
            return False
        elapsed = datetime.now(timezone.utc).timestamp() - self._window_start
        return elapsed >= self._window_seconds

    def snapshot(self) -> list[tuple[str, bytes]]:
        frames = list(self._frames)
        self._frames.clear()
        self._window_start = None
        return frames
