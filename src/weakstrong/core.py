"""Validated experiment records, statistics and atomic local persistence."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import re
import tempfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, validate_assignment=True)


class Experiment(StrictModel):
    seed: int = Field(default=17, ge=0, le=2**31 - 1)
    trials: int = Field(default=3, ge=1, le=10)
    split: str = Field(default="evaluation", pattern="^(development|evaluation|calibration|all)$")
    context_limit: int = Field(default=128, ge=8, le=1024)
    evidence_mode: str = Field(default="full", pattern="^(full|structured)$")
    threshold: float = Field(default=0.75, ge=0.5, le=0.99)


class RunRecord(StrictModel):
    schema_version: str = "1.0"
    metadata: dict[str, Any] = Field(
        default_factory=lambda: {
            "software_version": "0.1.1",
            "python_version": platform.python_version(),
            "dataset_version": "1",
            "source_sha256": hashlib.sha256(
                b"".join(p.name.encode() + p.read_bytes() for p in sorted(Path(__file__).parent.glob("*.py")))
            ).hexdigest(),
        }
    )
    project: str
    mode: str
    dataset_sha256: str
    config_sha256: str
    config: dict[str, Any]
    providers: list[str]
    rows: list[dict[str, Any]]
    summary: list[dict[str, Any]]
    analysis: dict[str, Any] = Field(default_factory=dict)


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def stable(seed: int, key: str) -> float:
    return int(hashlib.sha256(f"{seed}:{key}".encode()).hexdigest()[:12], 16) / 16**12


def proportion(successes: int, total: int) -> dict[str, float | int | None]:
    if not 0 <= successes <= total:
        raise ValueError("invalid binomial counts")
    if total == 0:
        return {"value": None, "low": None, "high": None, "n": 0}
    p = successes / total
    z = 1.959963984540054
    den = 1 + z * z / total
    center = (p + z * z / (2 * total)) / den
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / den
    return {"value": p, "low": max(0.0, center - half), "high": min(1.0, center + half), "n": total}


def classification(rows: list[dict[str, Any]]) -> dict[str, Any]:
    decided = [r for r in rows if r["prediction"] is not None and r["label"] is not None]
    tp = sum(r["label"] and r["prediction"] for r in decided)
    tn = sum(not r["label"] and not r["prediction"] for r in decided)
    fp = sum(not r["label"] and r["prediction"] for r in decided)
    fn = sum(r["label"] and not r["prediction"] for r in decided)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    # Brier score measures probabilistic error on all labeled cases, including deferrals.
    labeled = [r for r in rows if r["label"] is not None]
    brier = sum((r["risk"] - int(r["label"])) ** 2 for r in labeled) / len(labeled) if labeled else None
    bins = []
    for i in range(5):
        group = [r for r in labeled if i / 5 <= r["risk"] < (i + 1) / 5 or i == 4 and r["risk"] == 1]
        bins.append(
            {
                "bin": i,
                "n": len(group),
                "predicted": sum(r["risk"] for r in group) / len(group) if group else None,
                "observed": sum(r["label"] for r in group) / len(group) if group else None,
            }
        )
    confidence_bins: list[dict[str, Any]] = []
    for i in range(5):
        lower = 0.5 + i * 0.1
        upper = 0.5 + (i + 1) * 0.1
        group = [
            r
            for r in labeled
            if lower <= max(r["risk"], 1 - r["risk"]) < upper
            or i == 4
            and max(r["risk"], 1 - r["risk"]) >= upper
        ]
        confidence_bins.append(
            {
                "bin": i,
                "n": len(group),
                "confidence": sum(max(r["risk"], 1 - r["risk"]) for r in group) / len(group)
                if group
                else None,
                "accuracy": sum((r["risk"] >= 0.5) == r["label"] for r in group) / len(group)
                if group
                else None,
            }
        )
    confidence_ece = (
        sum(b["n"] * abs(b["confidence"] - b["accuracy"]) for b in confidence_bins if b["n"]) / len(labeled)
        if labeled
        else None
    )
    return {
        "confidence_calibration": confidence_bins,
        "confidence_ece": confidence_ece,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "accuracy": proportion(tp + tn, len(decided)),
        "false_positive_rate": proportion(fp, fp + tn),
        "missed_violation_rate": proportion(fn, fn + tp),
        "brier": brier,
        "calibration": bins,
        "review_workload": sum(r["prediction"] is None for r in rows) / len(rows) if rows else 0.0,
        "decided": len(decided),
        "labeled": len(labeled),
        "n": len(rows),
        "cost_usd": sum(r.get("cost_usd", 0.0) for r in rows),
        "input_tokens": sum(r.get("input_tokens", 0) for r in rows),
        "output_tokens": sum(r.get("output_tokens", 0) for r in rows),
        "latency_ms": sum(r.get("latency_ms", 0.0) for r in rows) / len(rows) if rows else 0.0,
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("refusing symlink output")
    data = json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n"
    fd, name = tempfile.mkstemp(prefix=".lab-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(data)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def safe_id(value: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", value):
        raise ValueError("invalid identifier")
    return value
