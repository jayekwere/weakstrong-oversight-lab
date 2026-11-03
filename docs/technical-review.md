# Release technical review

The release was reviewed in four roles: software engineering (interfaces, typing, bounded resources and deterministic replay), security architecture (untrusted observations, external authorization, provider and browser boundaries), research methodology (labels/splits, denominators, unresolved cases and cost claims), and maintainership (installation, packaging, documentation, licenses and CI).

Release refinements included strict provider-compatible schemas, malformed response sanitization, rejection of compressed responses, conservative budget reservations, spreadsheet-formula neutralization, source fingerprints and explicit failure accounting. Dashboard source is formatted and ships without third-party runtime JavaScript. Tests exercise the corresponding boundary contracts. Repeated-trial uncertainty never uses repeated observations as independent case counts.

Separate native Codex Security Standard audits subsequently completed for each repository. This repository had one validated low-severity provider JSON exception finding, addressed in v0.1.1. See the [audit and remediation record](security-audit.md) for the actual reproduction, scope and limitations. Source review, negative security tests, Bandit, credential-pattern scanning, dependency checks and GitHub CodeQL remain complementary controls. No paid service or real-model evaluation was initiated.

Residual limitations: public correlated synthetic data, simplified formal policies, finite behavioral fixtures and a single-user local application. Real-model transfer, actual human supervision, public multi-user hosting and guarantees against all prompt injection remain unverified. See methodology and threat model for practical limits.
