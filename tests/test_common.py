from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from weakstrong import cli
from weakstrong.adapters import BudgetError, HTTPModel, ProviderConfig, ProviderError
from weakstrong.core import Experiment, classification, digest, proportion, safe_id, stable, write_json
from weakstrong.web import create_app


def test_validation_statistics_and_atomic_outputs(tmp_path: Path) -> None:
    assert digest({"b": 1, "a": 2}) == digest({"a": 2, "b": 1})
    assert stable(17, "a") == stable(17, "a") != stable(18, "a")
    assert proportion(0, 0)["value"] is None
    assert proportion(5, 10)["low"] < 0.5 < proportion(5, 10)["high"]
    with pytest.raises(ValueError):
        proportion(2, 1)
    with pytest.raises(ValidationError):
        Experiment(trials=0)
    with pytest.raises(ValidationError):
        Experiment(seed="17")
    with pytest.raises(ValidationError):
        Experiment(unknown=True)
    assert safe_id("case_01") == "case_01"
    with pytest.raises(ValueError):
        safe_id("../outside")
    path = tmp_path / "child" / "result.json"
    write_json(path, {"ok": True})
    assert json.loads(path.read_text()) == {"ok": True}
    link = tmp_path / "link.json"
    link.symlink_to(path)
    with pytest.raises(ValueError):
        write_json(link, {})
    rows = [
        {"label": True, "prediction": True, "risk": 0.8},
        {"label": False, "prediction": True, "risk": 0.6},
        {"label": True, "prediction": False, "risk": 0.3},
        {"label": False, "prediction": False, "risk": 0.2},
        {"label": None, "prediction": None, "risk": 0.5},
    ]
    m = classification(rows)
    assert (m["tp"], m["tn"], m["fp"], m["fn"]) == (1, 1, 1, 1)
    assert m["f1"] == 0.5 and m["review_workload"] == 0.2
    assert classification([])["brier"] is None


def provider_config(kind: str = "local", **kwargs: Any) -> ProviderConfig:
    base = {"kind": kind, "enabled": True, "retries": 0}
    if kind != "local":
        base.update(
            {
                "endpoint": f"https://api.{'openai.com/v1/chat/completions' if kind == 'openai' else 'anthropic.com/v1/messages'}",
                "max_spend_usd": 5.0,
            }
        )
    return ProviderConfig.model_validate({**base, **kwargs})


def response(kind: str = "local", answer: Any = None) -> dict[str, Any]:
    if answer is None:
        answer = {"risk": 0.2}
    return {
        "usage": {"input_tokens": 10, "output_tokens": 5},
        **(
            {"content": [{"type": "tool_use", "name": "decision", "input": answer}]}
            if kind == "anthropic"
            else {"choices": [{"message": {"content": json.dumps(answer)}}]}
        ),
    }


@pytest.mark.parametrize("kind", ["local", "openai", "anthropic"])
def test_adapter_structured_outputs_and_no_oracle(kind: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-not-a-credential")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-not-a-credential")
    seen = []

    def transport(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=response(kind))

    model = HTTPModel(provider_config(kind), httpx.MockTransport(transport))
    assert model.complete("observable facts only", {"type": "object"}) == {"risk": 0.2}
    assert model.usage.requests == 1 and model.usage.input_tokens == 10
    assert "label" not in json.dumps(seen)
    with pytest.raises(BudgetError):
        HTTPModel(provider_config(kind, enabled=False), httpx.MockTransport(transport)).complete("x", {})


@pytest.mark.parametrize(
    "url",
    [
        "http://example.org",
        "https://localhost",
        "http://127.0.0.1@evil.invalid",
        "http://localhost/?secret=x",
        "http://localhost/#x",
    ],
)
def test_adapter_endpoint_restrictions(url: str) -> None:
    with pytest.raises(ProviderError):
        HTTPModel(provider_config(endpoint=url))


@pytest.mark.parametrize("field,value", [("max_requests", 1), ("max_tokens", 1), ("max_spend_usd", 0.0)])
def test_adapter_preflight_budgets(field: str, value: int | float, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-not-a-credential")
    count = 0

    def transport(request: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        return httpx.Response(200, json=response())

    model = HTTPModel(provider_config("openai", **{field: value}), httpx.MockTransport(transport))
    if field == "max_requests":
        model.complete("x", {})
    with pytest.raises(BudgetError):
        model.complete("x", {})
    assert count == (1 if field == "max_requests" else 0)


def test_adapter_retries_errors_limits_and_redaction(monkeypatch: pytest.MonkeyPatch) -> None:
    def status(code: int, body: Any) -> httpx.MockTransport:
        return httpx.MockTransport(lambda request: httpx.Response(code, json=body))

    with pytest.raises(ProviderError, match="credential"):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        HTTPModel(provider_config("openai")).complete("x", {})
    for code, body in [
        (400, {"secret": "must not echo"}),  # pragma: allowlist secret - synthetic redaction sentinel
        (200, {}),
        (200, None),
        (200, []),
        (200, {"usage": []}),
        (200, response(answer=[])),
        (200, {"usage": {"input_tokens": -1}}),
        (200, {"usage": {"input_tokens": "x"}}),
    ]:
        with pytest.raises(ProviderError) as error:
            HTTPModel(provider_config(), status(code, body)).complete("x", {})
        assert "must not echo" not in str(error.value)
    model = HTTPModel(provider_config(retries=2), status(503, {}))
    with pytest.raises(ProviderError, match="bounded retries"):
        model.complete("x", {})
    assert model.usage.requests == 3
    with pytest.raises(ProviderError, match="input exceeds"):
        HTTPModel(provider_config()).complete("x" * 1048577, {})
    model = HTTPModel(
        provider_config(), httpx.MockTransport(lambda request: httpx.Response(200, content=b"x" * 262145))
    )
    with pytest.raises(ProviderError, match="response limit"):
        model.complete("x", {})
    model = HTTPModel(
        provider_config(),
        httpx.MockTransport(lambda request: (_ for _ in ()).throw(httpx.ConnectError("private"))),
    )
    with pytest.raises(ProviderError, match="unavailable"):
        model.complete("x", {})


def test_api_boundaries_runs_exports_and_empty_state(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(create_app())
    assert client.get("/api/health").json()["mode"] == "synthetic-local"
    assert client.get("/").status_code == 200
    assert client.get("/assets/app.js").headers["content-type"].startswith("text/javascript")
    assert client.get("/api/scenarios").status_code == 200
    assert client.get("/api/runs/missing").status_code == 404
    assert client.get("/", headers={"host": "attacker.invalid"}).status_code == 400
    assert client.delete("/api/runs").status_code == 405
    assert client.post("/api/runs", json={}, headers={"origin": "https://evil.invalid"}).status_code == 403
    assert client.post("/api/runs", content=b"x" * 17000).status_code == 413
    monkeypatch.setenv("LAB_API_TOKEN", "synthetic-test-access")
    assert client.post("/api/runs", json={}).status_code == 401
    monkeypatch.delenv("LAB_API_TOKEN")
    response = client.post("/api/runs", json={"trials": 1})
    assert response.status_code == 200
    run_id = response.json()["id"]
    assert run_id in client.get("/api/runs").json()
    result = client.get(f"/api/runs/{run_id}").json()
    assert result["mode"] == "deterministic-simulation" and len(result["rows"]) > 0
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert client.get(f"/api/runs/{run_id}/export").json() == result
    csv = client.get(f"/api/runs/{run_id}/export?format=csv")
    assert "strategy" in csv.text.splitlines()[0] and len(csv.text.splitlines()) > 1
    assert client.get(f"/api/runs/{run_id}/export?format=bad").status_code == 422
    assert client.post("/api/runs", json={"trials": 100}).status_code == 422
    for _ in range(4):
        client.post("/api/runs", json={"trials": 1})
    assert client.post("/api/runs", json={}).status_code == 429
    assert len(client.get("/api/runs").json()) <= 4


def test_cli_dataset_run_validation_and_serve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "data.json"
    monkeypatch.setattr(sys, "argv", ["lab", "dataset", "--output", str(target)])
    cli.main()
    assert len(json.loads(target.read_text())) >= 100
    cfg = tmp_path / "config.json"
    cfg.write_text('{"trials":1}')
    monkeypatch.setattr(sys, "argv", ["lab", "run", "--config", str(cfg), "--output", str(target)])
    cli.main()
    assert json.loads(target.read_text())["mode"] == "deterministic-simulation"
    cfg.write_text('{"trials":0}')
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
    monkeypatch.setattr(sys, "argv", ["lab", "serve", "--port", "10"])
    with pytest.raises(SystemExit):
        cli.main()
    import uvicorn

    calls = []
    monkeypatch.setattr(uvicorn, "run", lambda *a, **kw: calls.append(kw))
    monkeypatch.setattr(sys, "argv", ["lab", "serve"])
    cli.main()
    assert calls[0]["host"] == "127.0.0.1"
    assert "invalid configuration" in capsys.readouterr().err


def test_export_neutralizes_spreadsheet_formulas(monkeypatch: pytest.MonkeyPatch) -> None:
    from weakstrong import web
    from weakstrong.core import RunRecord

    record = RunRecord(
        project="test",
        mode="deterministic-simulation",
        dataset_sha256="x",
        config_sha256="y",
        config={},
        providers=[],
        rows=[{"id": "synthetic", "reason": "  =1+1"}],
        summary=[],
    )
    monkeypatch.setattr(web, "evaluate", lambda cfg: record)
    client = TestClient(web.create_app())
    run_id = client.post("/api/runs", json={}).json()["id"]
    exported = client.get(f"/api/runs/{run_id}/export?format=csv")
    assert "'  =1+1" in exported.text
