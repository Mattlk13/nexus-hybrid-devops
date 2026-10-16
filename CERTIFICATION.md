# NEXUS certification evidence — 2026-10-16

Decision: **HOLD**. Draft PR #1; no merge, production deployment, service purchase, or publication authorized by this evidence.

12 Python tests pass locally; the real-runtime acceptance test is skipped locally because no runtime/image is configured. CI includes an isolated Docker lifecycle fixture.
Docker/Podman adapters restrict fixtures to nexus.scope=certification, operator-selected immutable image IDs, deterministic request names, no network, read-only filesystem, dropped capabilities and resource limits. Create/stop success requires inspect readback. Duplicate reuse, conflicting image, timeout/error redaction and scoped cleanup have unit coverage. Terraform state discovery redacts resource values and explicitly does not assert live provider state.
Infrastructure create/destroy, production deployments, alert backends and deployment rollback remain disabled. Terraform executable and isolated provider account are absent. Terraform state discovery is not live infrastructure certification. Concurrent start/stop races, ambiguous timeout recovery, real permission failures and complete rollback readback remain blockers.

## Reproduce

`python -m unittest discover -v -p 'test_*.py'`

GitHub Actions runs on the PR branch with contents:read and a bounded job timeout. Review current-head Actions results; prior passing commits are not substitutes for current-head evidence. No tests against live Sentry/Jenkins or a production environment were executed.
