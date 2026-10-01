# Geometry-Consistency Execution Recovery

The frozen Allegro scoring adapter stopped after 167 completed scores. Two
additional raw cylinder traces had been fully recorded. Their unchanged native
outcomes were failures. The first error was a primitive-clearance reconstruction
difference of 1.172649061187414e-09 m, exceeding the frozen 1e-10 m assertion.

The scientific code and assertion are not changed. A separate, hash-registered
recovery orchestrator catches only this exact error category and records
INDETERMINATE with INVALID telemetry for every audit method. Native outcomes
are preserved separately but are not used to turn invalid instrumentation into
a verified acceptance. No scene, candidate or branch is replaced. Other errors
still stop execution.

Such candidates retain INVALID future-use evidence without being relabeled as
physical failure. This is consistent with the protocol's missing/invalid-data
denominators. The observed finite-pool oracle is only a lower bound if any
candidate future is invalid. The recovery rule is documented after exposure to
the first batch, not presented as pre-test implementation. It does not widen a
physical threshold or use future outcomes. All originally frozen hashes remain
unchanged. Final reporting must disclose the count and affected case IDs.
