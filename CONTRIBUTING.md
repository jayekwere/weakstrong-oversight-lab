# Contributing
Use synthetic examples and explain the research hypothesis or concrete defect. Open an issue before a broad methodology change. Reproduce the saved experiment before editing evaluation logic.

```sh
uv sync --frozen --extra dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
node --test tests/dashboard.test.mjs
uv run bandit -q -r src
uv run python scripts/reproduce.py
```

Add meaningful behavioral tests for changes at trust boundaries. Keep deterministic core coverage above 85%. Add a new scenario ID for a new case; preserve grouping by attack/task mechanism across dataset splits. Never tune using held-out labels and then report that same split as untouched. Record a new benchmark version when changing labels, generators or splits.

Pull requests should describe behavior, validation and statistical limitations. No fabricated metrics, copied private datasets, unlicensed assets, embedded credentials, or real-system attack integrations are accepted. Changes are licensed under Apache-2.0. See the [code of conduct](CODE_OF_CONDUCT.md).
