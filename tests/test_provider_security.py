"""Regression checks for untrusted provider JSON, using no network or model service."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

from weakstrong import cli, engine
from weakstrong.adapters import HTTPModel, ProviderConfig, ProviderError


def nested_response(kind: str, form: str) -> bytes:
    # Fits the adapter byte ceiling but exceeds CPython's JSON nesting ceiling.
    nested = "[" * 128000 + "0" + "]" * 128000
    if form == "outer_array":
        return nested.encode()
    if form == "outer_object":
        return ('{"payload":' + nested + "}").encode()
    if kind == "anthropic":
        return ('{"content":[{"type":"tool_use","name":"decision","input":' + nested + "}]}").encode()
    return json.dumps({"choices": [{"message": {"content": nested}}]}).encode()


@pytest.mark.parametrize("kind", ["local", "openai", "anthropic"])
@pytest.mark.parametrize("form", ["outer_array", "outer_object", "decision"])
def test_nested_provider_response_is_sanitized_without_retry(
    kind: str, form: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-not-a-credential")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-not-a-credential")
    bad = nested_response(kind, form)
    assert len(bad) <= 262144
    calls = 0

    def transport(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, content=bad)
        body = (
            {"content": [{"type": "tool_use", "name": "decision", "input": {"ok": True}}]}
            if kind == "anthropic"
            else {"choices": [{"message": {"content": '{"ok":true}'}}]}
        )
        return httpx.Response(200, json=body)

    endpoint = {
        "local": "http://127.0.0.1:11434/v1/chat/completions",
        "openai": "https://api.openai.com/v1/chat/completions",
        "anthropic": "https://api.anthropic.com/v1/messages",
    }[kind]
    config = ProviderConfig.model_validate(
        {"kind": kind, "endpoint": endpoint, "enabled": True, "retries": 2, "max_spend_usd": 5.0}
    )
    model = HTTPModel(config, httpx.MockTransport(transport))
    with pytest.raises(ProviderError, match="invalid structured provider response") as error:
        model.complete("synthetic observation", {"type": "object"})
    assert error.value.__suppress_context__
    assert calls == model.usage.requests == 1
    reserved = model.usage.reserved_tokens
    assert reserved > 0
    assert model.complete("synthetic observation", {"type": "object"}) == {"ok": True}
    assert calls == model.usage.requests == 2
    assert model.usage.reserved_tokens == 2 * reserved


def test_cli_persists_provider_failures_instead_of_aborting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cases = engine.load_dataset()
    selected = [next(s for s in cases if s.split == "evaluation")]
    if any(s.split == "calibration" for s in cases):
        selected.append(next(s for s in cases if s.split == "calibration"))
    monkeypatch.setattr(engine, "load_dataset", lambda: selected)
    config = ProviderConfig(enabled=True, max_requests=20, max_tokens=1000000, retries=2)
    model = HTTPModel(
        config,
        httpx.MockTransport(
            lambda request: httpx.Response(200, content=nested_response("local", "decision"))
        ),
    )
    monkeypatch.setattr(cli, "HTTPModel", lambda config: model)
    provider = tmp_path / "provider.json"
    provider.write_text(config.model_dump_json())
    experiment = tmp_path / "experiment.json"
    experiment.write_text('{"trials":1}')
    output = tmp_path / "result.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "lab",
            "run",
            "--config",
            str(experiment),
            "--provider-config",
            str(provider),
            "--output",
            str(output),
        ],
    )
    cli.main()
    saved = json.loads(output.read_text())
    assert saved["mode"] == "external-model"
    assert saved["rows"] and any(row["error"] for row in saved["rows"])
    assert 0 < model.usage.requests <= config.max_requests
    if "capability_calibration" in saved["metadata"]:
        calibration = next(c for c in saved["metadata"]["capability_calibration"] if c["profile"] == "lens-1")
        assert calibration["errors"] == 1
