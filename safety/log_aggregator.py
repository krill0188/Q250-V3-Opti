import asyncio
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import time


@dataclass
class LogSample:
    timestamp: float
    device_id: str
    log_type: str  # BATTERY, ATTITUDE, GPS, MOTOR, FLIGHT_MODE, SENSOR
    data: Dict[str, Any]


class LogAggregator:
    def __init__(self, window_sec: float = 2.0, max_samples: int = 1000):
        self.window_sec = window_sec
        self.max_samples = max_samples
        self.buffers: Dict[str, deque] = {}
        self._lock = asyncio.Lock()

    async def ingest(self, sample: LogSample):
        async with self._lock:
            if sample.device_id not in self.buffers:
                self.buffers[sample.device_id] = deque(maxlen=self.max_samples)
            self.buffers[sample.device_id].append(sample)

    def get_window(
        self, device_id: str, window_sec: Optional[float] = None
    ) -> List[LogSample]:
        window = window_sec or self.window_sec
        cutoff = time.time() - window
        if device_id not in self.buffers:
            return []
        return [s for s in self.buffers[device_id] if s.timestamp >= cutoff]

    def get_all_windows(
        self, window_sec: Optional[float] = None
    ) -> Dict[str, List[LogSample]]:
        return {did: self.get_window(did, window_sec) for did in self.buffers}

    def clear_old(self, max_age_sec: float = 10.0):
        cutoff = time.time() - max_age_sec
        for did in list(self.buffers.keys()):
            buf = self.buffers[did]
            while buf and buf[0].timestamp < cutoff:
                buf.popleft()
            if not buf:
                del self.buffers[did]
