from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from weakstrong import cli
from weakstrong.adapters import ProviderError, Usage
from weakstrong.core import Experiment
from weakstrong.dataset import load_dataset, validate_dataset
from weakstrong.engine import evaluate, registry
from weakstrong.reviews import ManualReview, apply_reviews, review_queue
from weakstrong.supervisors import (
    PROFILES,
    Assessment,
    FixtureSupervisor,
    assess,
    consensus,
    interpret,
    policy_baseline,
)
from weakstrong.web import create_app


def test_dataset_splits_unknown_evidence_and_oracle_consistency() -> None:
    cases = load_dataset()
    assert len(cases) == 144
    assert {
        split: sum(s.split == split for s in cases) for split in ("development", "calibration", "evaluation")
    } == {"development": 48, "calibration": 48, "evaluation": 48}
    for s in cases:
        judgment = interpret(s.observation, 8)
        if s.label is not None:
            assert (judgment.risk >= 0.5) == s.label
        else:
            assert judgment.risk == 0.5
    with pytest.raises(ValueError):
        validate_dataset(cases[:99])
    with pytest.raises(ValueError):
        validate_dataset(cases + [cases[0]])
    for change in ("split", "duplicate", "fact_ids", "unknown"):
        altered = [s.model_copy(deep=True) for s in cases]
        if change == "split":
            altered[0].split = "evaluation"
        elif change == "duplicate":
            altered[1].observation = altered[0].observation
        elif change == "fact_ids":
            altered[0].observation.facts.append(altered[0].observation.facts[0])
        else:
            altered[0].label = None
        with pytest.raises(ValueError):
            validate_dataset(altered)


def test_policy_budget_dependencies_and_consensus() -> None:
    cases = load_dataset()
    deep = next(s for s in cases if s.family == "distributed_risk" and s.difficulty == 4)
    assert interpret(deep.observation, 1).risk == 0.5
    assert interpret(deep.observation, 4).risk > 0.9
    altered = deep.observation.model_copy(deep=True)
    altered.facts[1].depends_on = "grant-4"
    assert interpret(altered, 4).reason == "authorization dependency edge or grant value is invalid"
    missing = next(s for s in cases if s.family == "permission_chain" and s.difficulty == 2)
    assert interpret(missing.observation, 2).risk > 0.9
    obs = cases[0].observation.model_copy(deep=True)
    obs.proposal.operation = "grant"
    obs.proposal.role = "administrator"
    assert policy_baseline(obs).risk > 0.9
    with pytest.raises(ValueError):
        consensus([])
    assert (
        consensus(
            [
                Assessment(risk=0.9, evidence=["x"], reason="a"),
                Assessment(risk=0.1, evidence=["x"], reason="b"),
            ]
        ).risk
        == 0.5
    )
    assert len(consensus([Assessment(risk=0.9, evidence=["x"], reason="a")]).evidence) == 1


class SpyModel:
    name = "mock-supervisor"

    def __init__(self, mode: str = "valid") -> None:
        self.mode = mode
        self.usage = Usage()

    def complete(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        data = json.loads(prompt)
        assert set(data) == {"policy", "observation"}
        assert '"label"' not in prompt and '"rationale"' not in prompt and '"family"' not in prompt
        if self.mode == "error":
            raise ProviderError("fixture failure")
        return {
            "risk": 0.8,
            "evidence": [data["observation"]["facts"][0]["id"] if self.mode == "valid" else "forged"],
            "reason": "mock evidence review",
        }


def test_model_schema_evidence_registry_and_error_accounting() -> None:
    obs = load_dataset()[0].observation
    model = SpyModel()
    assert assess(model, obs).risk == 0.8
    with pytest.raises(ValueError):
        assess(SpyModel("invalid"), obs)
    assert registry(17, model)["lens-1"] is model
    assert registry(17, models={"lens-2": model})["lens-2"] is model
    failed = evaluate(Experiment(trials=1), SpyModel("error"))
    assert failed.mode == "external-model"
    assert any(r["error"] for r in failed.rows)
    assert (
        next(c for c in failed.analysis["capability_calibration"] if c["profile"] == "lens-1")["errors"] == 48
    )
    with pytest.raises(ValueError):
        evaluate(Experiment(split="calibration"))


def test_calibration_repetition_unknown_labels_and_deferrals() -> None:
    a = evaluate(Experiment(trials=3))
    b = evaluate(Experiment(trials=3))

    def observations(r: Any) -> list[dict[str, Any]]:
        return [{k: v for k, v in row.items() if k != "latency_ms"} for row in r.rows]

    assert observations(a) == observations(b)
    assert a.analysis["unique_cases"] == 48
    calibration = {c["profile"]: c for c in a.analysis["capability_calibration"]}
    assert calibration["reference-8"]["accuracy"]["value"] > calibration["lens-1"]["accuracy"]["value"]
    metrics = {s["strategy"]: s for s in a.summary}
    assert metrics["selective"]["review_workload"] > 0
    assert metrics["selective"]["unknown_label_cases"] == 12
    assert metrics["single"]["accuracy"]["n"] == 36
    assert len(metrics["single"]["repeated_trial_metrics"]) == 3
    assert all(r["cost_usd"] == 0 for r in a.rows)
    all_cases = evaluate(Experiment(trials=1, split="all", context_limit=8, evidence_mode="structured"))
    assert all_cases.analysis["unique_cases"] == 96
    for profile in PROFILES:
        assert FixtureSupervisor(profile, 17).complete(
            json.dumps({"observation": load_dataset()[0].observation.model_dump()}), {}
        )


def test_manual_review_never_assumes_human_accuracy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    record = evaluate(Experiment(trials=1))
    queue = review_queue(record)
    assert queue and "label" not in queue[0]
    before = apply_reviews(record, [])
    first = queue[0]["id"]
    review = ManualReview(scenario_id=first, decision="block", note="synthetic interface test")
    after = apply_reviews(record, [review])
    assert after["remaining_unresolved"] == before["remaining_unresolved"] - 1
    assert (
        apply_reviews(record, [ManualReview(scenario_id=first, decision="insufficient")])[
            "remaining_unresolved"
        ]
        == before["remaining_unresolved"]
    )
    with pytest.raises(ValueError):
        apply_reviews(record, [review, review])
    with pytest.raises(ValueError):
        apply_reviews(record, [ManualReview(scenario_id="unrelated", decision="allow")])
    run_file = tmp_path / "run.json"
    run_file.write_text(record.model_dump_json())
    decisions = tmp_path / "decisions.json"
    decisions.write_text(json.dumps([review.model_dump()]))
    output = tmp_path / "out.json"
    monkeypatch.setattr(sys, "argv", ["lab", "review", "--run", str(run_file), "--output", str(output)])
    cli.main()
    assert json.loads(output.read_text())[0]["id"] == first
    monkeypatch.setattr(
        sys,
        "argv",
        ["lab", "review", "--run", str(run_file), "--decisions", str(decisions), "--output", str(output)],
    )
    cli.main()
    assert json.loads(output.read_text())["manual_reviews"] == 1
    decisions.write_text(json.dumps({"reviews": [review.model_dump()]}))
    cli.main()
    assert json.loads(output.read_text())["manual_reviews"] == 1


def test_manual_review_api_validates_queue_membership() -> None:
    client = TestClient(create_app())
    response = client.post("/api/runs", json={"trials": 1})
    run_id = response.json()["id"]
    queue = client.get(f"/api/runs/{run_id}/reviews").json()
    assert queue["queue"] and "label" not in queue["queue"][0]
    case_id = queue["queue"][0]["id"]
    valid = client.post(f"/api/runs/{run_id}/reviews", json={"scenario_id": case_id, "decision": "block"})
    assert valid.status_code == 200 and valid.json()["manual_reviews"] == 1
    assert (
        client.post(
            f"/api/runs/{run_id}/reviews", json={"scenario_id": "forged", "decision": "allow"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/runs/{run_id}/reviews", json={"scenario_id": case_id, "decision": "malformed"}
        ).status_code
        == 422
    )
    assert len(client.get(f"/api/runs/{run_id}/reviews").json()["reviews"]) == 1


def test_threshold_sweep_matrix(monkeypatch: pytest.MonkeyPatch) -> None:
    from weakstrong import experiments
    from weakstrong.core import RunRecord

    configs = []

    def fake(cfg: Experiment) -> RunRecord:
        configs.append(cfg)
        return RunRecord(
            project="test",
            mode="deterministic-simulation",
            dataset_sha256="x",
            config_sha256="y",
            config=cfg.model_dump(),
            providers=[],
            rows=[],
            summary=[],
            analysis={"by_difficulty": []},
        )

    monkeypatch.setattr(experiments, "evaluate", fake)
    assert len(experiments.run_suite()["experiments"]) == 5
    assert [c.threshold for c in configs] == [0.5, 0.65, 0.75, 0.85, 0.95]
    assert all(c.trials == 3 for c in configs)
