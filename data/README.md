# Synthetic oversight dataset v1

144 cases across 12 mechanism families, four dependency depths and three resource variants. Development, capability calibration and held-out evaluation contain 48 cases each, grouped by mechanism. The canonical source is src/weakstrong/dataset.py; scenarios.json is an exported artifact.

Each case contains a proposed action, trusted tenant, required grant depth and evidence facts with IDs/dependencies. An explicit oracle label is true (violation), false (authorized) or null (insufficient evidence). Held-out labels are 24/12/12 respectively. No missing label is guessed. Every source observation is unique; the schema, uniqueness, family splits, chronology-independent graph fields and labels are checked by tests.

Supervisors receive policy plus the observation only. They never receive case identifiers, splits, family, rationale or truth labels. Public data can still be memorized, and related variants share grammar. No training or private held-out claim is made. Facts, resources and decisions are invented and contain no real records. Apache-2.0.
