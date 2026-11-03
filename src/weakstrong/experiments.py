"""Predeclared threshold/workload sensitivity experiments with free deterministic fixtures."""

from __future__ import annotations

from typing import Any

from .core import Experiment
from .engine import evaluate


def run_suite() -> dict[str, Any]:
    experiments = []
    for threshold in (0.5, 0.65, 0.75, 0.85, 0.95):
        result = evaluate(Experiment(seed=17, trials=3, threshold=threshold))
        experiments.append(
            {
                "config": result.config,
                "dataset_sha256": result.dataset_sha256,
                "summary": result.summary,
                "by_difficulty": result.analysis["by_difficulty"],
            }
        )
    return {
        "mode": "deterministic-simulation",
        "protocol": "five predeclared confidence thresholds; three trials; no human decisions simulated or assumed correct",
        "experiments": experiments,
    }
