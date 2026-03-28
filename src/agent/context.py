import asyncio
from collections import deque

from src.models import Observation


class SharedContext:
    def __init__(self, max_observations: int = 100):
        self._observations: deque[Observation] = deque(maxlen=max_observations)
        self._last_seen: dict[str, dict] = {}
        self._lock = asyncio.Lock()

    @property
    def recent_observations(self) -> list[Observation]:
        return list(self._observations)

    @property
    def last_seen(self) -> dict[str, dict]:
        return dict(self._last_seen)

    def add_observation(self, observation: Observation) -> None:
        self._observations.append(observation)
        for obj in observation.objects:
            self._last_seen[obj.name] = {
                "location": obj.location,
                "timestamp": observation.timestamp,
            }

    async def add_observation_async(self, observation: Observation) -> None:
        async with self._lock:
            self.add_observation(observation)

    def get_summary(self) -> str:
        lines = []
        if self._last_seen:
            lines.append("## Last Seen Items")
            for name, info in self._last_seen.items():
                lines.append(f"- {name}: {info['location']} (at {info['timestamp']})")
        if self._observations:
            lines.append("\n## Recent Observations")
            for obs in list(self._observations)[-10:]:
                for action in obs.actions:
                    lines.append(f"- [{obs.timestamp}] {action}")
                for concern in obs.safety_concerns:
                    lines.append(f"- [{obs.timestamp}] SAFETY: {concern}")
        return "\n".join(lines) if lines else "No observations yet."
