# Native security audit and v0.1.1 remediation

A separate repository-wide native Codex Security Standard audit completed on 2026-11-03 against `9029495a03aafbc489c18321d7170599dcfe5f3e` (v0.1.0 source). It included an independent source reviewer, parent trust-boundary analysis, candidate validation and attack-path calibration. This is an automated source audit, not an independent third-party certification.

## Confirmed finding

**Low — CWE-248: excessive provider JSON nesting could abort an opted-in CLI experiment.** The raw-response and decision-content JSON decoders could raise `RecursionError` outside the existing sanitized provider-error boundary. Evaluators recover from `ProviderError` and validation failures, so this exception stopped evaluation before the CLI saved its result. WeakStrong capability calibration used the same affected boundary.

The isolated reproduction used only `httpx.MockTransport`: three adapters, three response representations and valid follow-up controls. At depth 128000, responses of 256001–256061 bytes fit the 262144-byte ceiling and raised uncaught `RecursionError` on Python 3.12.16. Depths 1500 and 8000 did not reproduce that exception on this runtime. No real model, API service or credential was used. Cloud schema/output enforcement may prevent such responses; the demonstrated impact concerns a configured provider permitting malformed output. Default deterministic simulation and dashboard runs are unaffected.

## Remediation

Version 0.1.1 includes `RecursionError` in the existing malformed-response handler covering both decoders. The adapter returns the same sanitized `ProviderError` without a retry, keeps the request reservation charged, and permits a subsequent valid response. Ten regression tests per repository cover all adapter/representation combinations and CLI result persistence, including capability-calibration failure accounting where applicable. These tests failed against the original implementation and passed with the change.

Run the focused regression tests with:

```sh
uv run pytest tests/test_provider_security.py --no-cov
```

## Scope and limitations

All executable application, frontend, test and supporting script source was reviewed, together with small configuration, workflow, policy and documentation files. Large generated JSON, dependency locks and images received targeted content/credential checks rather than exhaustive manual semantic review. Dependency vulnerability checks run separately in CI. No source audit guarantees the absence of further defects.

Raw request-body buffering, slow-upload behavior and HTTP transport deadline semantics were considered. No reportable exploit was established against the supported local single-user browser/model-text attacker boundary; reverse-proxy deployments still require upstream authentication, TLS and request limits. A hostile native client is outside this deployment model. Stdio peers already control their own child session. No additional authorization bypass, secret disclosure, host-code execution or stored script injection was validated.

Full native reports remain in the local Codex Security workbench for the audited revisions. They preserve the original finding; this document describes the subsequent patch. Published research observations remain synthetic and do not establish real-model safety.
