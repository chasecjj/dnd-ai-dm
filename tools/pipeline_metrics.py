"""
PipelineMetrics — Lightweight in-memory metrics for the LangGraph pipeline.

Tracks request counts, per-node latency, and error rates. Resets on bot
restart (no persistence needed — this is session-level visibility).

Pure Python. No Discord imports.

Usage:
    from tools.pipeline_metrics import pipeline_metrics

    pipeline_metrics.record_request(duration=3.2, is_solo=False, success=True)
    pipeline_metrics.record_node("storyteller", 1.8)
    summary = pipeline_metrics.get_summary()
"""

import time
from collections import Counter, deque
from typing import Dict, Optional


class PipelineMetrics:
    """In-memory metrics tracker for pipeline health monitoring."""

    def __init__(self, history_size: int = 50):
        self._history_size = history_size
        self.uptime_start: float = time.monotonic()

        # Request counters
        self.total_requests: int = 0
        self.success_count: int = 0
        self.error_count: int = 0
        self.solo_requests: int = 0
        self.group_requests: int = 0

        # Latency tracking (bounded deques)
        self.recent_latencies: deque = deque(maxlen=history_size)
        self.node_latencies: Dict[str, deque] = {}

        # Error classification
        self.error_types: Counter = Counter()

        # Timing
        self.last_request_at: Optional[float] = None

    def record_request(
        self,
        duration: float,
        is_solo: bool,
        success: bool,
        error_type: Optional[str] = None,
    ):
        """Record a completed pipeline request.

        Args:
            duration: Wall-clock seconds for the full pipeline.
            is_solo: True if this was a solo adventure request.
            success: True if the pipeline completed without error.
            error_type: Classification string if success is False.
        """
        self.total_requests += 1
        self.recent_latencies.append(duration)
        self.last_request_at = time.monotonic()

        if is_solo:
            self.solo_requests += 1
        else:
            self.group_requests += 1

        if success:
            self.success_count += 1
        else:
            self.error_count += 1
            if error_type:
                self.error_types[error_type] += 1

    def record_node(self, node_name: str, duration: float):
        """Record per-node execution time.

        Args:
            node_name: Node identifier (e.g., "router", "storyteller").
            duration: Wall-clock seconds for this node.
        """
        if node_name not in self.node_latencies:
            self.node_latencies[node_name] = deque(maxlen=self._history_size)
        self.node_latencies[node_name].append(duration)

    def avg_latency(self) -> float:
        """Average pipeline latency across recent requests."""
        if not self.recent_latencies:
            return 0.0
        return sum(self.recent_latencies) / len(self.recent_latencies)

    def error_rate(self) -> float:
        """Error rate as a fraction (0.0 to 1.0)."""
        if self.total_requests == 0:
            return 0.0
        return self.error_count / self.total_requests

    def slowest_node(self) -> Optional[tuple]:
        """Return (node_name, avg_seconds) for the slowest node, or None."""
        if not self.node_latencies:
            return None
        slowest_name = None
        slowest_avg = 0.0
        for name, times in self.node_latencies.items():
            if times:
                avg = sum(times) / len(times)
                if avg > slowest_avg:
                    slowest_avg = avg
                    slowest_name = name
        if slowest_name is None:
            return None
        return (slowest_name, slowest_avg)

    def node_avg(self, node_name: str) -> float:
        """Average latency for a specific node."""
        times = self.node_latencies.get(node_name)
        if not times:
            return 0.0
        return sum(times) / len(times)

    def uptime_seconds(self) -> float:
        """Seconds since the metrics tracker was initialized."""
        return time.monotonic() - self.uptime_start

    def seconds_since_last_request(self) -> Optional[float]:
        """Seconds since the last recorded request, or None if no requests."""
        if self.last_request_at is None:
            return None
        return time.monotonic() - self.last_request_at

    def get_summary(self) -> dict:
        """Return a dict summarizing all metrics (for the status embed)."""
        slowest = self.slowest_node()
        return {
            "total_requests": self.total_requests,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "solo_requests": self.solo_requests,
            "group_requests": self.group_requests,
            "avg_latency": round(self.avg_latency(), 1),
            "error_rate": round(self.error_rate() * 100, 1),
            "slowest_node": slowest[0] if slowest else None,
            "slowest_node_avg": round(slowest[1], 1) if slowest else None,
            "uptime_seconds": round(self.uptime_seconds()),
            "seconds_since_last": (
                round(self.seconds_since_last_request())
                if self.seconds_since_last_request() is not None
                else None
            ),
            "error_types": dict(self.error_types),
            "node_averages": {
                name: round(self.node_avg(name), 2)
                for name in self.node_latencies
            },
        }


# Module-level singleton — import this everywhere
pipeline_metrics = PipelineMetrics()
