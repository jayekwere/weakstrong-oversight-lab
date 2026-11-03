"""Documented command line entry points."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .adapters import HTTPModel, Model, ProviderConfig
from .core import Experiment, write_json
from .dataset import load_dataset
from .engine import evaluate


def main() -> None:
    parser = argparse.ArgumentParser(description="WeakStrong Oversight Lab: synthetic AI safety experiments")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="execute a bounded experiment")
    run.add_argument("--config", type=Path)
    run.add_argument(
        "--provider-config", type=Path, help="explicit opt-in provider config; never used by dashboard"
    )
    run.add_argument("--model-map", type=Path, help="profile-to-provider configuration map")
    run.add_argument("--output", type=Path, default=Path("runs/experiment.json"))
    suite = sub.add_parser("suite", help="run confidence/workload sensitivity experiments")
    suite.add_argument("--output", type=Path, default=Path("runs/threshold-sweep.json"))
    review = sub.add_parser("review", help="export a review queue or score supplied manual decisions")
    review.add_argument("--run", type=Path, required=True)
    review.add_argument("--decisions", type=Path)
    review.add_argument("--output", type=Path, default=Path("runs/reviews.json"))
    data = sub.add_parser("dataset", help="validate and export the labeled synthetic dataset")
    data.add_argument("--output", type=Path, default=Path("runs/dataset.json"))
    serve = sub.add_parser("serve", help="serve the local dashboard")
    serve.add_argument("--port", type=int, default=8080)

    args = parser.parse_args()
    try:
        if args.command == "run":
            config = Experiment.model_validate_json(args.config.read_text()) if args.config else Experiment()
            model = (
                HTTPModel(ProviderConfig.model_validate_json(args.provider_config.read_text()))
                if args.provider_config
                else None
            )
            if args.model_map and args.provider_config:
                raise ValueError("choose a provider config or a model map")
            models: dict[str, Model] | None = None
            if args.model_map:
                from .supervisors import PROFILES

                mapping = json.loads(args.model_map.read_text())
                if not isinstance(mapping, dict) or not set(mapping) <= {p.name for p in PROFILES}:
                    raise ValueError("unknown supervisor profile")
                models = {
                    name: HTTPModel(ProviderConfig.model_validate(value)) for name, value in mapping.items()
                }
            result = evaluate(config, model, models)
            write_json(args.output, result.model_dump())
            print(
                json.dumps(
                    {
                        "output": str(args.output),
                        "mode": result.mode,
                        "rows": len(result.rows),
                        "summary": result.summary,
                    }
                )
            )
        elif args.command == "suite":
            from .experiments import run_suite

            write_json(args.output, run_suite())
            print(json.dumps({"output": str(args.output), "experiments": 5}))
        elif args.command == "review":
            from .core import RunRecord
            from .reviews import ManualReview, apply_reviews, review_queue

            record = RunRecord.model_validate_json(args.run.read_text())
            result_review: dict[str, object] | list[dict[str, object]]
            if args.decisions:
                from pydantic import TypeAdapter

                raw_reviews = json.loads(args.decisions.read_text())
                payload = (
                    raw_reviews.get("reviews", raw_reviews) if isinstance(raw_reviews, dict) else raw_reviews
                )
                supplied = TypeAdapter(list[ManualReview]).validate_python(payload)
                result_review = apply_reviews(record, supplied)
            else:
                result_review = review_queue(record)
            write_json(args.output, result_review)
            print(json.dumps({"output": str(args.output)}))
        elif args.command == "dataset":
            cases = load_dataset()
            write_json(args.output, [s.model_dump() for s in cases])
            print(json.dumps({"cases": len(cases), "output": str(args.output)}))
        elif args.command == "serve":
            import uvicorn

            if not 1024 <= args.port <= 65535:
                raise ValueError("port must be between 1024 and 65535")
            uvicorn.run(
                "weakstrong.web:app",
                host="127.0.0.1",
                port=args.port,
                log_level="warning",
                limit_concurrency=32,
                timeout_keep_alive=5,
            )
    except (ValueError, OSError) as exc:
        print(
            json.dumps(
                {"error": type(exc).__name__, "detail": "invalid configuration or inaccessible local path"}
            ),
            file=sys.stderr,
        )
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
