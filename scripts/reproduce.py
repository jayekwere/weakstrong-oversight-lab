"""Verify saved observations against a fresh deterministic run, excluding clock measurements."""

import json
from pathlib import Path

from weakstrong.core import Experiment, write_json
from weakstrong.engine import evaluate

saved = json.loads(Path("results/demo.json").read_text())
fresh = evaluate(Experiment.model_validate(saved["config"])).model_dump()


def observations(value: dict) -> list:
    return [{k: v for k, v in row.items() if k != "latency_ms"} for row in value["rows"]]


assert observations(saved) == observations(fresh), "deterministic observations drifted"
assert fresh["dataset_sha256"] == saved["dataset_sha256"], "dataset drifted"
assert fresh["metadata"]["source_sha256"] == saved["metadata"]["source_sha256"], "source drifted"
write_json(Path("runs/reproduced.json"), fresh)
print(json.dumps({"reproduced": True, "rows": len(fresh["rows"]), "dataset_sha256": fresh["dataset_sha256"]}))
