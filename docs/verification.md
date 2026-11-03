# Verification evidence

The local Python 3.12.16 suite passed 22 pytest tests with 96.50% branch-inclusive deterministic coverage on 2026-11-03. Release changes are checked again by CI. Tests cover oracle consistency across all cases, three-way split integrity, unknown evidence, operational calibration, capability budgets, ensemble aggregation, deferrals, fake evidence, provider failures, budget limits, manual-review membership/scoring, reproducibility, API/CLI/export behavior and threshold configuration.

All 720 saved supervision observations reproduce exactly excluding latency. Five predeclared threshold settings executed. No real model or human study was run, and no cost or performance of a named external model is claimed. Optional HTTP protocols are tested with mock transports.

The actual dashboard was inspected at desktop/mobile breakpoints, including capability results, error analysis and a synthetic manual-review form submission. The submission explicitly retained insufficient evidence and was an automated interface check, not a human adjudication. Screenshots: [dashboard](images/dashboard.jpg), [review queue](images/review.jpg). Ruff, strict mypy, Bandit, Node utility tests, credential scanning, dependency auditing and clean distribution/container checks are release gates. See GitHub Actions for immutable-commit evidence.

## Final local release gate

Python 3.12.16: 23 pytest tests passed; 95.38% branch-inclusive core coverage. Three Node dashboard tests passed. Ruff, strict mypy and Bandit passed. Saved observations and source fingerprints reproduced. The single TestClient deprecation warning is retained; it does not affect the passing assertions. GitHub Actions verifies the final published commit separately.

Fresh wheel installation verified hashed runtime dependencies, exact experiment observations and source fingerprints, plus the installed dashboard/API. See [installation evidence](../results/installation-verification.json). Mobile layout checks observed a 375 px content viewport with no horizontal page overflow; desktop checks used the 1440×1000 breakpoint. Long scenario JSON loads on demand to keep filtering responsive.

## v0.1.1 security patch verification

Python 3.12.16: 33 pytest tests passed with 96.17% branch-inclusive coverage. All ten new provider JSON regression tests passed; the excessive-nesting test failed against the original implementation. Three Node dashboard tests, Ruff lint/format, strict mypy and Bandit passed. A fresh read-only reviewer found no concrete surviving bypass or regression in the patch. The existing TestClient deprecation warning remains visible. See [audit scope and remediation](security-audit.md).
