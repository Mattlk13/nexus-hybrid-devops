# NEXUS resumed certification — 2026-10-16

Decision: **HOLD**. No production deployment, merge, release publication or service purchase.

## Resumed certification results

- PASS: real Terraform 1.13.5 binary, checksum verified against the official release SHA256SUMS. Isolated built-in terraform_data resource creation, duplicate reconciliation, refresh-only state verification, destroy rollback and empty-state readback pass. Seven Terraform tests pass (1 real lifecycle + 6 policy tests).
- PASS: real Podman lifecycle and injected-start-failure rollback tests on MattWorkspace (2 tests, 15.456s). The failed start creates a real fixture, removes it and queries the runtime to verify absence. Stop is bound to the inspected immutable container ID. Docker/Podman image ID formatting is normalized.
- Terraform engine create/destroy operations now use the real guarded adapter. The workspace must have .nexus-certification; production is rejected, an existing nonempty workspace is rejected, the plan must contain only allowlisted creates/deletes, and unknown/pending outcomes block blind retries. Default resource allowlist is terraform_data only; no billable cloud resources were created.
- Local suite with Terraform available: 19 pass, 2 runtime tests skip; those two runtime tests pass separately against Podman.
- STILL BLOCKED: provider-specific cloud credential/target acceptance and actual application deployment/rollback. Terraform's built-in resource fixture does not certify a cloud provider. Deployment and alert APIs remain disabled; no provider or application success is invented.
- Current-head hosted CI is queued, not passed.

## Earlier evidence (historical)

# NEXUS certification evidence — 2026-10-16

Decision: **HOLD**. Draft PR #1; no merge, production deployment, service purchase, or publication authorized by this evidence.

12 Python tests pass locally; the real-runtime acceptance test is skipped locally because no runtime/image is configured. CI includes an isolated Docker lifecycle fixture.
Docker/Podman adapters restrict fixtures to nexus.scope=certification, operator-selected immutable image IDs, deterministic request names, no network, read-only filesystem, dropped capabilities and resource limits. Create/stop success requires inspect readback. Duplicate reuse, conflicting image, timeout/error redaction and scoped cleanup have unit coverage. Terraform state discovery redacts resource values and explicitly does not assert live provider state.
Infrastructure create/destroy, production deployments, alert backends and deployment rollback remain disabled. Terraform executable and isolated provider account are absent. Terraform state discovery is not live infrastructure certification. Concurrent start/stop races, ambiguous timeout recovery, real permission failures and complete rollback readback remain blockers.

## Reproduce

`python -m unittest discover -v -p 'test_*.py'`

GitHub Actions runs on the PR branch with contents:read and a bounded job timeout. Review current-head Actions results; prior passing commits are not substitutes for current-head evidence. No tests against live Sentry/Jenkins or a production environment were executed.
