# NEXUS resumed certification — 2026-10-16

Decision: **HOLD**. No production deployment, merge, release publication or service purchase.

## Live Cloudflare acceptance — 2026-10-17 UTC

PASS: Nexus2 staging-only Actions run [38991358325](https://github.com/Mattlk13/Nexus2/actions/runs/38991358325) tested adapter code adad837. Existing staging version deployment, provider deployment/version readback, changed public app.js hash, duplicate without a new deployment, exact prior-version rollback, repeated rollback and original asset-hash restoration all passed. Invalid credentials were denied live. Raw receipt: verification/cloudflare-staging-20261017.json. No new resources, production deployment or purchases.

Initial runs 38990973509/38991113735 failed before mutation because Python urllib public-asset retrieval received 403. The harness now uses standard credential-free curl, like the existing staging verification. HTTP and exact content-hash assertions remain enabled. No security policy was changed or bypassed.

Adapter code adad837 passed both hosted regression runs 38991357146 and 38991354617, including Docker and Terraform acceptance. This document/evidence follow-up requires its own current-head CI. Live restricted-permission credentials, timeouts, distributed concurrency and rollback failure remain uncertified; mocked tests do not substitute for those gates.

## Cloudflare staging deployment adapter — 2026-10-17 UTC

- Implemented deploy_service, rollback_deployment and provider current-deployment readback through the Cloudflare deployments API. Only an explicitly configured existing *-staging Worker, environment=staging, existing version UUID and all_at_once strategy are supported. This does not provision resources or upload new application versions.
- Requires scoped token/account/worker and a private operator-created receipt directory with .nexus-cloudflare-staging marker. Local exclusive lock, durable pending receipt, operation annotations and provider deployment-ID ownership checks guard writes/rollback. Duplicate target version does not mutate. Lost acknowledgements remain pending; rollback may reconcile only the exact persisted operation annotation, target version and provider ID. Other actors' deployments are never intentionally rolled back.
- PASS locally: 8 Cloudflare tests cover success/duplicate/restore, lost-ack reconciliation, timeout with no blind write retry, concurrent local lock, missing ownership, external deployment interference, production/worker scope, auth/permission redaction and gradual deployment rejection. Live acceptance is recorded above; the full live failure matrix is still open.
- HTTP timeouts and a 403 remain unconfirmed/ambiguous; a 403 is not falsely classified as a proven permission-only failure. No service token or API response error body is logged. No production endpoint exists in this adapter.
- Acceptance harness ci/test_cloudflare_staging.py requires explicit live opt-in, the exact nexus2-staging Worker, a known existing test version and expected staging app.js. It verifies provider version/deployment IDs, a changed public asset hash, duplicate without new deployment, original-version rollback and the restored exact asset hash. It is intended for the existing serialized staging-only GitHub workflow using its existing secrets. No new cloud resources or purchases.
- Cloud-provider Terraform provisioning/destruction and its full live permission/timeout/concurrency matrix remain uncertified. Locking here is local; independent distributed actors can race the API, which has no compare-and-swap in this implementation. Use an exclusively controlled staging target.

Prior current-code baseline 54e6f91 passed Actions 38963933815, including real Docker and Terraform. This adapter change requires fresh CI and live acceptance.

## Prior evidence (historical)

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
