"""OpenTelemetry instrumentation for the agent.

Emits traces and metrics following the OTel **GenAI semantic conventions**
(`gen_ai.*`) so the data is portable to any OTel backend, plus a few `fury.*`
extensions (cost, mode, tool errors).

Everything degrades to a no-op when telemetry is disabled or the `obs` extra is
not installed — the agent runs identically either way.
"""

from __future__ import annotations

import contextlib
import logging
import os

from fury.core.history import Usage


class _NoopSpan:
    def set_attribute(self, *_a, **_k) -> None:  # pragma: no cover - trivial
        pass


class Telemetry:
    def __init__(
        self, enabled: bool = False, endpoint: str = "localhost:4317",
        service: str = "agent-fury",
    ) -> None:
        self.enabled = False
        self._tracer = None
        if not enabled:
            return
        # Quiet gRPC's noisy fork/fd warnings (we fork subprocesses for shell +
        # eval workspaces); harmless for our export-only usage.
        os.environ.setdefault("GRPC_VERBOSITY", "ERROR")
        os.environ.setdefault("GRPC_ENABLE_FORK_SUPPORT", "false")
        try:
            from opentelemetry import metrics, trace
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
                OTLPMetricExporter,
            )
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )
            from opentelemetry.sdk.metrics import MeterProvider
            from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
        except ImportError:
            logging.getLogger("fury").warning(
                "telemetry requested but the 'obs' extra is not installed; "
                "install with: pip install 'agent-fury[obs]'"
            )
            return

        resource = Resource.create({"service.name": service})
        # Short timeouts so a missing collector never hangs the CLI on shutdown.
        self._tp = TracerProvider(resource=resource)
        self._tp.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(endpoint=endpoint, insecure=True, timeout=3)
            )
        )
        trace.set_tracer_provider(self._tp)

        reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=endpoint, insecure=True, timeout=3),
            export_interval_millis=5000,
        )
        self._mp = MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(self._mp)

        self._tracer = trace.get_tracer("fury")
        meter = metrics.get_meter("fury")
        self._m_requests = meter.create_counter("fury.llm.requests")
        self._m_tokens = meter.create_histogram("fury.llm.tokens")
        self._m_cost = meter.create_counter("fury.llm.cost")
        self._m_duration = meter.create_histogram("fury.llm.duration")
        self._m_tool_calls = meter.create_counter("fury.tool.calls")
        self._m_tool_duration = meter.create_histogram("fury.tool.duration")
        self._m_eval_tasks = meter.create_counter("fury.eval.tasks")
        self._m_eval_cost = meter.create_counter("fury.eval.cost")
        self._m_eval_iters = meter.create_histogram("fury.eval.iterations")
        self._m_eval_duration = meter.create_histogram("fury.eval.duration")

        # Keep exporter connection noise out of the user's terminal.
        logging.getLogger("opentelemetry").setLevel(logging.ERROR)
        self.enabled = True

    # -- spans --------------------------------------------------------------
    @contextlib.contextmanager
    def llm_span(self, system: str, model: str, mode: str):
        if not self.enabled:
            yield _NoopSpan()
            return
        with self._tracer.start_as_current_span("chat") as span:
            span.set_attribute("gen_ai.system", system)
            span.set_attribute("gen_ai.request.model", model)
            span.set_attribute("gen_ai.operation.name", "chat")
            span.set_attribute("fury.mode", mode)
            yield span

    @contextlib.contextmanager
    def tool_span(self, name: str):
        if not self.enabled:
            yield _NoopSpan()
            return
        with self._tracer.start_as_current_span(f"tool.{name}") as span:
            span.set_attribute("fury.tool", name)
            yield span

    # -- metrics ------------------------------------------------------------
    def record_llm(self, span, system, model, mode, usage: Usage, cost, duration_s):
        span.set_attribute("gen_ai.usage.input_tokens", usage.input_tokens)
        span.set_attribute("gen_ai.usage.output_tokens", usage.output_tokens)
        span.set_attribute("fury.cost_usd", cost)
        if not self.enabled:
            return
        attrs = {"gen_ai.system": system, "gen_ai.request.model": model, "fury.mode": mode}
        self._m_requests.add(1, attrs)
        self._m_tokens.record(usage.input_tokens, {**attrs, "type": "input"})
        self._m_tokens.record(usage.output_tokens, {**attrs, "type": "output"})
        self._m_cost.add(cost, attrs)
        self._m_duration.record(duration_s, attrs)

    def record_tool(self, name: str, is_error: bool, duration_s: float):
        if not self.enabled:
            return
        self._m_tool_calls.add(1, {"tool": name, "error": str(bool(is_error)).lower()})
        self._m_tool_duration.record(duration_s, {"tool": name})

    def record_eval(self, model, passed, iterations, cost, duration_s):
        if not self.enabled:
            return
        self._m_eval_tasks.add(1, {"model": model, "result": "pass" if passed else "fail"})
        self._m_eval_cost.add(cost, {"model": model})
        self._m_eval_iters.record(iterations, {"model": model})
        self._m_eval_duration.record(duration_s, {"model": model})

    def shutdown(self) -> None:
        if not self.enabled:
            return
        with contextlib.suppress(Exception):
            self._tp.shutdown()
        with contextlib.suppress(Exception):
            self._mp.shutdown()
