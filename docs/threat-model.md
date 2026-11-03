# Threat model
## Assets and trust boundaries
Protect local credentials, the host filesystem, synthetic labels, run integrity and research cost ceilings. Trusted inputs are the researcher's CLI configuration, package source and fixed generator. Treat model outputs, retrieved content and trace prose as untrusted data. A model may request a tool operation; only deterministic code can authorize it. No model output becomes shell commands, Python code or file paths.

The local browser is another boundary: JSON data is rendered through HTML escaping; no external scripts/fonts/assets are loaded. CSP, host checks, same-origin write checks, a 16 KiB body ceiling, six writes/minute and a nonblocking experiment lock constrain the API. Runs are bounded to ten trials, finite datasets and four retained results. The API exposes synthetic results publicly to anyone who can reach it; bind to loopback. Optional bearer authentication protects writes only.

## Adversaries
Simulated adversaries can insert misleading prose, cross-tenant resource identifiers, authorization claims and benign lookalikes. They cannot change trusted labels, experiment configuration, provider endpoints, evaluator source or local files. HTTP model output is bounded, parsed and Pydantic-validated. Provider endpoints are restricted to official HTTPS hosts or explicitly configured loopback HTTP local servers; redirects and environment proxies are disabled. Transport retries share one deadline and consume reservations before every attempt.

## Controls and limits
Adapter request/token/spending ceilings reject a call before transmission. Cost is an estimate using an operator-supplied conservative tariff; a client cannot guarantee an external provider's billing behavior. Full serialized input byte length plus the configured maximum output bounds each reservation; failed attempts retain reservations. No live provider request runs in the web API. Offline fixtures report zero API tokens and cost, not invented tokenizer measurements.

Containers run as UID/GID 10001. Use read-only filesystems, dropped capabilities, no-new-privileges, PID/memory limits and network isolation for experiments. The default container dashboard binds loopback; use the CLI for isolated container evaluation. No container escape or hostile multi-user deployment is claimed. Locks and rate limits are per process; do not use multiple workers as a security boundary.

## Residual risk
Public synthetic labels allow deliberate benchmark overfitting. Separating observation construction from oracles reduces accidental leakage; it cannot prevent a remote model from memorizing a public dataset. Synthetic policies simplify messy authorization. An authorized researcher can intentionally set a high spend ceiling or modify code. Vulnerability scans are point-in-time evidence, not a guarantee.
