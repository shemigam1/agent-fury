import json
from pathlib import Path

import pytest

import fury.obs
from fury.core.history import Usage
from fury.obs.pricing import price_for
from fury.obs.telemetry import Telemetry


def test_pricing_lookup():
    assert price_for("gemini-flash-latest")[0] > 0
    assert price_for("some-local-model") == (0.0, 0.0)


def test_telemetry_disabled_is_noop():
    t = Telemetry(enabled=False)
    assert t.enabled is False
    with t.llm_span("gemini", "flash", "code") as span:
        t.record_llm(span, "gemini", "flash", "code", Usage(10, 5), 0.001, 0.2)
    with t.tool_span("read_file") as span:
        span.set_attribute("x", 1)
    t.record_tool("read_file", False, 0.01)
    t.shutdown()  # must not raise


def test_telemetry_enabled_no_collector_does_not_crash():
    pytest.importorskip("opentelemetry")
    # Point at a dead endpoint; export failures must stay silent, never raise.
    t = Telemetry(enabled=True, endpoint="localhost:4317")
    assert t.enabled is True
    with t.llm_span("gemini", "flash", "code") as span:
        t.record_llm(span, "gemini", "flash", "code", Usage(100, 20), 0.01, 0.5)
    with t.tool_span("grep") as span:
        span.set_attribute("fury.tool.error", False)
    t.record_tool("grep", False, 0.02)
    t.shutdown()


def test_dashboard_json_is_valid():
    p = Path(fury.obs.__file__).parent / "deploy" / "grafana" / "dashboards" / "agent-overview.json"
    data = json.loads(p.read_text())
    assert data["title"] == "agent-fury · Overview"
    assert len(data["panels"]) >= 6


def test_deploy_files_present():
    base = Path(fury.obs.__file__).parent / "deploy"
    for name in ["docker-compose.yml", "otel-collector.yaml", "prometheus.yml", "tempo.yaml"]:
        assert (base / name).is_file(), name
