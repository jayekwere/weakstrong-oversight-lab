# WeakStrong Oversight Lab v0.1.1

Fixes a low-severity availability issue in optional provider-backed CLI experiments: excessive JSON nesting now becomes a sanitized provider failure instead of aborting the run before persistence. Both JSON decoding sites and all three provider adapters are covered.

Adds ten regression tests covering malformed response representations, no-retry behavior, retained budget reservations, valid follow-up responses and saved failure results. See the [native audit and remediation record](security-audit.md) for scope and limitations.

Saved demonstration and sensitivity outputs are refreshed from actual deterministic executions with the patched source fingerprint. These are synthetic observations; no real-model evaluation or paid API call was performed. Default simulation and public interfaces retain their existing behavior.

See [verification](verification.md), [reproduction](reproduction.md), and [security policy](../SECURITY.md).
