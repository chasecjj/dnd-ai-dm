"""Tests for PipelineMetrics — in-memory pipeline monitoring."""

import time
from tools.pipeline_metrics import PipelineMetrics


class TestPipelineMetrics:
    """Unit tests for the PipelineMetrics tracker."""

    def _make_metrics(self):
        return PipelineMetrics(history_size=50)

    def test_initial_state(self):
        m = self._make_metrics()
        assert m.total_requests == 0
        assert m.success_count == 0
        assert m.error_count == 0
        assert m.solo_requests == 0
        assert m.group_requests == 0
        assert m.avg_latency() == 0.0
        assert m.error_rate() == 0.0
        assert m.slowest_node() is None
        assert m.last_request_at is None

    def test_record_success_group(self):
        m = self._make_metrics()
        m.record_request(3.0, is_solo=False, success=True)
        assert m.total_requests == 1
        assert m.success_count == 1
        assert m.error_count == 0
        assert m.group_requests == 1
        assert m.solo_requests == 0
        assert m.avg_latency() == 3.0

    def test_record_success_solo(self):
        m = self._make_metrics()
        m.record_request(2.5, is_solo=True, success=True)
        assert m.solo_requests == 1
        assert m.group_requests == 0
        assert m.total_requests == 1

    def test_record_error(self):
        m = self._make_metrics()
        m.record_request(1.0, is_solo=False, success=False, error_type="pipeline_error")
        assert m.error_count == 1
        assert m.success_count == 0
        assert m.error_types["pipeline_error"] == 1

    def test_error_rate(self):
        m = self._make_metrics()
        m.record_request(1.0, is_solo=False, success=True)
        m.record_request(1.0, is_solo=False, success=True)
        m.record_request(1.0, is_solo=False, success=False, error_type="timeout")
        m.record_request(1.0, is_solo=False, success=False, error_type="timeout")
        assert m.error_rate() == 0.5  # 2/4

    def test_avg_latency(self):
        m = self._make_metrics()
        m.record_request(2.0, is_solo=False, success=True)
        m.record_request(4.0, is_solo=False, success=True)
        m.record_request(6.0, is_solo=False, success=True)
        assert m.avg_latency() == 4.0  # (2+4+6)/3

    def test_record_node(self):
        m = self._make_metrics()
        m.record_node("router", 0.5)
        m.record_node("router", 0.3)
        m.record_node("storyteller", 2.0)
        assert m.node_avg("router") == 0.4  # (0.5+0.3)/2
        assert m.node_avg("storyteller") == 2.0
        assert m.node_avg("nonexistent") == 0.0

    def test_slowest_node(self):
        m = self._make_metrics()
        m.record_node("router", 0.5)
        m.record_node("storyteller", 2.0)
        m.record_node("chronicler", 1.5)
        name, avg = m.slowest_node()
        assert name == "storyteller"
        assert avg == 2.0

    def test_deque_bounded(self):
        m = PipelineMetrics(history_size=5)
        for i in range(10):
            m.record_request(float(i), is_solo=False, success=True)
        assert len(m.recent_latencies) == 5
        # Should contain the last 5: 5.0, 6.0, 7.0, 8.0, 9.0
        assert list(m.recent_latencies) == [5.0, 6.0, 7.0, 8.0, 9.0]

    def test_node_deque_bounded(self):
        m = PipelineMetrics(history_size=3)
        for i in range(6):
            m.record_node("router", float(i))
        assert len(m.node_latencies["router"]) == 3
        assert list(m.node_latencies["router"]) == [3.0, 4.0, 5.0]

    def test_multiple_error_types(self):
        m = self._make_metrics()
        m.record_request(1.0, is_solo=False, success=False, error_type="pipeline_error")
        m.record_request(1.0, is_solo=False, success=False, error_type="pipeline_error")
        m.record_request(1.0, is_solo=False, success=False, error_type="gemini_timeout")
        assert m.error_types["pipeline_error"] == 2
        assert m.error_types["gemini_timeout"] == 1

    def test_get_summary_keys(self):
        m = self._make_metrics()
        m.record_request(3.0, is_solo=True, success=True)
        m.record_node("router", 0.5)
        summary = m.get_summary()
        expected_keys = {
            "total_requests", "success_count", "error_count",
            "solo_requests", "group_requests", "avg_latency",
            "error_rate", "slowest_node", "slowest_node_avg",
            "uptime_seconds", "seconds_since_last", "error_types",
            "node_averages",
        }
        assert set(summary.keys()) == expected_keys

    def test_get_summary_values(self):
        m = self._make_metrics()
        m.record_request(3.0, is_solo=True, success=True)
        m.record_request(5.0, is_solo=False, success=True)
        m.record_node("router", 0.5)
        summary = m.get_summary()
        assert summary["total_requests"] == 2
        assert summary["solo_requests"] == 1
        assert summary["group_requests"] == 1
        assert summary["avg_latency"] == 4.0
        assert summary["error_rate"] == 0.0
        assert "router" in summary["node_averages"]

    def test_uptime_positive(self):
        m = self._make_metrics()
        assert m.uptime_seconds() > 0

    def test_seconds_since_last_request(self):
        m = self._make_metrics()
        assert m.seconds_since_last_request() is None
        m.record_request(1.0, is_solo=False, success=True)
        elapsed = m.seconds_since_last_request()
        assert elapsed is not None
        assert elapsed >= 0.0

    def test_error_without_type(self):
        m = self._make_metrics()
        m.record_request(1.0, is_solo=False, success=False)
        assert m.error_count == 1
        assert len(m.error_types) == 0  # No type recorded

    def test_mixed_solo_and_group(self):
        m = self._make_metrics()
        m.record_request(1.0, is_solo=True, success=True)
        m.record_request(2.0, is_solo=False, success=True)
        m.record_request(3.0, is_solo=True, success=False, error_type="x")
        m.record_request(4.0, is_solo=False, success=True)
        assert m.total_requests == 4
        assert m.solo_requests == 2
        assert m.group_requests == 2
        assert m.success_count == 3
        assert m.error_count == 1
