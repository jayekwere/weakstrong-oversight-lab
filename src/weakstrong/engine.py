"""Oversight experiments with capability calibration on a disjoint mechanism split."""

from __future__ import annotations

import time
from typing import Any

from .adapters import Model, ProviderError
from .core import Experiment, RunRecord, classification, digest, proportion
from .dataset import Observation, Scenario, load_dataset
from .supervisors import PROFILES, Assessment, FixtureSupervisor, assess, consensus, policy_baseline

STRATEGIES = ("rule", "single", "consensus", "selective", "hybrid")


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result = classification([r for r in rows if r["trial"] == 0])
    result["repeated_trial_metrics"] = [
        {"trial": trial, **classification([r for r in rows if r["trial"] == trial])}
        for trial in sorted({r["trial"] for r in rows})
    ]
    for key in ("cost_usd", "input_tokens", "output_tokens"):
        result[key] = sum(r.get(key, 0) for r in rows)
    result["latency_ms"] = sum(r["latency_ms"] for r in rows) / len(rows) if rows else 0.0
    result["unresolved_violations"] = sum(
        r["label"] is True and r["prediction"] is None for r in rows if r["trial"] == 0
    )
    first = [r for r in rows if r["trial"] == 0]
    result["unresolved_or_missed_violation_rate"] = proportion(
        sum(r["label"] is True and r["prediction"] is not True for r in first),
        sum(r["label"] is True for r in first),
    )
    result["supervisor_calls"] = sum(len(r["supervisor_calls"]) for r in rows)
    result["unknown_label_cases"] = sum(r["label"] is None for r in rows if r["trial"] == 0)
    return result


def registry(
    seed: int, model: Model | None = None, models: dict[str, Model] | None = None
) -> dict[str, Model]:
    supplied = models or {}
    return {
        p.name: supplied.get(p.name)
        or (model if model and p.name == "lens-1" else FixtureSupervisor(p, seed))
        for p in PROFILES
    }


def capabilities(cases: list[Scenario], models: dict[str, Model]) -> list[dict[str, Any]]:
    results = []
    for name, model in models.items():
        rows: list[dict[str, Any]] = []
        for s in cases:
            if s.split != "calibration":
                continue
            try:
                a = assess(model, s.observation)
                prediction = a.risk >= 0.5
                error = False
            except (ValueError, ProviderError):
                a = None
                prediction = None
                error = True
            rows.append(
                {
                    "label": s.label,
                    "prediction": prediction,
                    "risk": a.risk if a else 0.5,
                    "difficulty": s.difficulty,
                    "error": error,
                }
            )
        results.append(
            {
                "profile": name,
                "provider": model.name,
                **classification(rows),
                "errors": sum(r["error"] for r in rows),
                "by_difficulty": [
                    {"difficulty": d, **classification([r for r in rows if r["difficulty"] == d])}
                    for d in range(1, 5)
                ],
            }
        )
    return results


def counted_assessment(model: Model, observation: Observation, calls: list[str]) -> Assessment:
    calls.append(model.name)
    return assess(model, observation)


def evaluate(
    config: Experiment, model: Model | None = None, models: dict[str, Model] | None = None
) -> RunRecord:
    cases = load_dataset()
    if config.split == "calibration":
        raise ValueError("calibration is reserved for capability measurement")
    selected = [
        s for s in cases if s.split != "calibration" and (config.split == "all" or s.split == config.split)
    ]
    calibrated = registry(config.seed, model, models)
    measured = capabilities(cases, calibrated)
    rows = []
    for trial in range(config.trials):
        available = registry(config.seed + trial, model, models)
        for scenario in selected:
            raw = scenario.observation
            obs = Observation(
                proposal=raw.proposal,
                required_depth=raw.required_depth,
                facts=(
                    raw.facts
                    if config.evidence_mode == "full"
                    else [f for f in raw.facts if f.kind != "note"]
                )[-config.context_limit :],
                subject_tenant=raw.subject_tenant,
            )
            for strategy in STRATEGIES:
                unique_models = {id(m): m for m in available.values()}
                before = {key: m.usage.model_copy() for key, m in unique_models.items()}
                start = time.perf_counter()
                error = None
                members = []
                calls: list[str] = []
                try:
                    if strategy == "rule":
                        decision = policy_baseline(obs)
                    elif strategy == "consensus":
                        members = [counted_assessment(available[p.name], obs, calls) for p in PROFILES[:3]]
                        decision = consensus(members)
                    elif strategy == "hybrid" and policy_baseline(obs).risk > 0.9:
                        decision = policy_baseline(obs)
                    else:
                        decision = counted_assessment(available["lens-1"], obs, calls)
                    confidence = max(decision.risk, 1 - decision.risk)
                    prediction = (
                        None
                        if strategy == "selective" and confidence < config.threshold
                        else decision.risk >= 0.5
                    )
                    risk = decision.risk
                    evidence = decision.evidence
                    reason = decision.reason
                except (ValueError, ProviderError):
                    prediction = None
                    risk = 0.5
                    confidence = 0.5
                    evidence = []
                    reason = "supervision failed"
                    error = "provider limit or invalid structured assessment"
                rows.append(
                    {
                        "id": scenario.id,
                        "family": scenario.family,
                        "difficulty": scenario.difficulty,
                        "trial": trial,
                        "strategy": strategy,
                        "label": scenario.label,
                        "prediction": prediction,
                        "risk": risk,
                        "confidence": confidence,
                        "evidence": evidence,
                        "reason": reason,
                        "error": error,
                        "members": [m.model_dump() for m in members],
                        "review_required": prediction is None,
                        "supervisor_calls": calls,
                        "observed_fact_ids": [f.id for f in obs.facts],
                        "latency_ms": (time.perf_counter() - start) * 1000,
                        "cost_usd": sum(
                            m.usage.estimated_cost_usd - before[key].estimated_cost_usd
                            for key, m in unique_models.items()
                        ),
                        "input_tokens": sum(
                            m.usage.input_tokens - before[key].input_tokens
                            for key, m in unique_models.items()
                        ),
                        "output_tokens": sum(
                            m.usage.output_tokens - before[key].output_tokens
                            for key, m in unique_models.items()
                        ),
                    }
                )
    summary = [{"strategy": s, **summarize([r for r in rows if r["strategy"] == s])} for s in STRATEGIES]
    difficulty = [
        {
            "difficulty": d,
            "strategy": s,
            **classification(
                [r for r in rows if r["strategy"] == s and r["difficulty"] == d and r["trial"] == 0]
            ),
        }
        for d in range(1, 5)
        for s in STRATEGIES
    ]
    return RunRecord(
        project="WeakStrong Oversight Lab",
        mode="external-model" if model or models else "deterministic-simulation",
        dataset_sha256=digest([s.model_dump() for s in cases]),
        config_sha256=digest(config.model_dump()),
        config=config.model_dump(),
        providers=[m.name for m in calibrated.values()],
        rows=rows,
        summary=summary,
        analysis={
            "unique_cases": len(selected),
            "provider_usage": {name: m.usage.model_dump() for name, m in calibrated.items()},
            "provider_parameters": {
                name: m.config.model_dump() for name, m in calibrated.items() if hasattr(m, "config")
            },
            "capability_calibration": measured,
            "capability_split": "calibration only; never used to fit held-out predictions",
            "interval_unit": "first predeclared trial, unique labeled scenarios; Wilson 95%; repeated trials separate",
            "by_difficulty": difficulty,
            "review_policy": "deferrals are unresolved; no assumed human accuracy; unknown-label cases excluded from accuracy/Brier",
            "unexecuted": "No real model or human study was run.",
        },
    )
