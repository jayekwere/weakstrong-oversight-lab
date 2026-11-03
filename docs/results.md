# Observed simulation results

The run executed 720 supervision records: 48 held-out cases × three trials × five strategies. No language model or human study was evaluated. All figures below are observed fixture results, not estimates of frontier-model safety.

## Operational capability calibration

48 separate calibration cases per fixture.

| Profile | Calibration accuracy | Wilson 95% CI |
|---|---:|---:|
| lens-1 | 0.604 | 0.463–0.730 |
| lens-2 | 0.750 | 0.612–0.851 |
| lens-4 | 0.938 | 0.832–0.979 |
| reference-8 | 1.000 | 0.926–1.000 |

Lens-1 is empirically less accurate than the reference fixture on this calibration task distribution. This does not imply any ordering of real models or general intelligence.

## Held-out oversight (first predeclared trial)

| Strategy | Conditional accuracy | Decided labeled n | Miss rate among decided violations | Review workload | Deferred true violations |
|---|---:|---:|---:|---:|---:|
| rule | 0.667 | 36 | 0.500 | 0.000 | 0 |
| single | 0.694 | 36 | 0.083 | 0.000 | 0 |
| consensus | 0.972 | 36 | 0.000 | 0.000 | 0 |
| selective | 0.889 | 18 | 0.133 | 0.625 | 9 |
| hybrid | 0.750 | 36 | 0.000 | 0.000 | 0 |

Twelve cases have unknown truth and are excluded from binary metrics. The selective strategy decides only 18 known-label cases: its 88.9% conditional accuracy is not directly comparable to strategies deciding all 36 known-label cases. It leaves nine true violations unresolved, in addition to other deferrals. No perfect human reviewer is assumed.

## Threshold sensitivity

| Confidence threshold | Selective workload | Automatic accuracy | Deferred true violations |
|---|---:|---:|---:|
| 0.50 | 0.000 | 0.694 | 0 |
| 0.65 | 0.583 | 0.800 | 9 |
| 0.75 | 0.625 | 0.889 | 9 |
| 0.85 | 0.625 | 0.889 | 9 |
| 0.95 | 0.688 | 0.867 | 9 |

The ensemble improves fixture accuracy in this experiment. Selective deferral raises conditional accuracy while transferring workload and unresolved risk; high confidence still permits mistakes. These are synthetic outcomes under a known formal policy. All inference costs and model token counts are zero. Monetary cost-effectiveness and human workload duration remain unmeasured.

Artifacts: [default run](../results/demo.json), [threshold sweep](../results/threshold-sweep.json), [unresolved review queue](../results/review-queue.json). See [methodology](methodology.md) for denominators, uncertainty and limitations.

## Review effort and unresolved-risk accounting

| Strategy | Supervisor calls across three trials | Missed or unresolved true violations (first trial) | Confidence ECE |
|---|---:|---:|---:|
| rule | 0 | 0.500 | 0.107 |
| single | 144 | 0.083 | 0.107 |
| consensus | 432 | 0.000 | 0.176 |
| selective | 144 | 0.458 | 0.107 |
| hybrid | 108 | 0.000 | 0.082 |

Supervisor calls count actual fixture invocations, not paid API requests. Confidence reliability includes raw deferred judgments on known labels. Selective deferral alone does not resolve the queued risk; additional review quality must be measured before claiming a safety improvement.
