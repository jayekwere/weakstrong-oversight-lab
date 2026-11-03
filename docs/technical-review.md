# Release technical review

The release was reviewed in four roles: software engineering (interfaces, typing, bounded resources and deterministic replay), security architecture (untrusted observations, external authorization, provider and browser boundaries), research methodology (labels/splits, denominators, unresolved cases and cost claims), and maintainership (installation, packaging, documentation, licenses and CI).

Release refinements included strict provider-compatible schemas, malformed response sanitization, rejection of compressed responses, conservative budget reservations, spreadsheet-formula neutralization, source fingerprints and explicit failure accounting. Dashboard source is formatted and ships without third-party runtime JavaScript. Tests exercise the corresponding boundary contracts. Repeated-trial uncertainty never uses repeated observations as independent case counts.

The optional native Codex Security scan did not start: its interface rejected the requested combined scope with “Scan scope must reference an existing directory inside the target.” No successful native scan or independent external audit is claimed. Source review, negative security tests, Bandit, credential-pattern scanning, dependency vulnerability scanning and GitHub CodeQL provide the executed checks instead. No paid service or real-model evaluation was initiated.

Residual limitations: public correlated synthetic data, simplified formal policies, finite behavioral fixtures and a single-user local application. Real-model transfer, actual human supervision, public multi-user hosting and guarantees against all prompt injection remain unverified. See methodology and threat model for practical limits.
