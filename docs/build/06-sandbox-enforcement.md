# Phase 6: Sandbox Enforcement

## Product Outcome

AutoHarness provides one real, capability-tested sandbox backend for a constrained shell and filesystem tool interface. It fails closed when the host cannot enforce the requested boundary.

## User Experience Outcome

The user sees concrete containment facts before execution: mounts, writable paths, network mode, credentials, resources, and unsupported capabilities. The word "sandboxed" means something testable.

## Scope

- `SandboxBackend` capability contract.
- Rootless Docker backend for supported Linux/Docker environments.
- Read-only source mount and dedicated writable output/tmp mounts.
- Network denied by default.
- Non-root user, dropped capabilities, `no-new-privileges`, and resource limits.
- Environment allowlist and secret denial.
- Controlled shell/filesystem tool protocol.
- Capability probe and `harness doctor` integration.
- Negative bypass and cleanup tests.

## Deliverables

- Sandbox request/result schemas
- Docker backend and image definition separate from the AutoHarness app image
- Capability report
- Generated sandbox configuration for verified fixtures
- Security test suite and platform limitation documentation

## Acceptance Gates

- Target source is not writable.
- Writes are confined to approved output and temporary mounts.
- Default verification cannot reach the network.
- Processes run as non-root with capabilities dropped.
- CPU, memory, process, and wall-time limits are exercised.
- Path traversal and symlink escape attempts fail.
- Missing enforcement capability blocks verification rather than degrading silently.
- Cancellation and failure remove containers and temporary resources.

## Out of Scope

- Claiming strong isolation on every operating system
- Browser, database, Kubernetes, or remote E2B backends
- Arbitrary host Docker socket exposure to target code
- Command-string filtering as the primary boundary

## Detailed Codex Prompt

```text
You are the lead engineer implementing AutoHarness Phase 6, its first genuine execution boundary.

Operate as:
1. A senior container security and platform engineer who distinguishes configuration from enforcement and tests every capability claim.
2. A product manager narrowing support to one backend that can be explained and maintained instead of offering several weak integrations.
3. A user safety advocate. Before execution, the user should know exactly what is isolated, what remains host-dependent, and why execution may be blocked.

Before editing:
- Read AGENTS.md and docs/architecture/security.md line by line.
- Read architecture, UX, scope, development setup, and all prior completion records.
- Run previous gates and inspect the generated tool/runtime contracts.
- Write a capability matrix for the supported Docker environment and explicit unsupported hosts.

Implement a typed SandboxBackend:
- Define SandboxCapabilities, SandboxRequest, mount/network/resource/environment policies, and SandboxResult.
- Implement a rootless/non-root Docker backend without exposing the host Docker socket to target code.
- Use a dedicated target-execution image, separate from the AutoHarness application image.
- Mount source read-only and create explicit writable output and tmp mounts.
- Deny network by default, drop all capabilities, enable no-new-privileges, set PID/memory/CPU/wall-time limits, and allowlist environment variables.
- Use an explicit constrained tool protocol for shell and filesystem operations.
- Capture stdout/stderr with size limits and redaction.

Capability honesty:
- Probe backend availability and enforceability before use.
- `harness doctor` reports supported, unsupported, and unverified capabilities with remediation.
- If a requested policy cannot be enforced on the current platform, fail closed. Do not silently use command deny lists or host execution.
- Human output must show the containment summary before a run.

Security engineering:
- Normalize paths and test absolute paths, .. traversal, symlinks, mount boundaries, race assumptions, malicious filenames, interpreters, child processes, and environment leakage.
- Treat command filtering only as defense in depth.
- Ensure target code cannot reach host credentials, .env, Docker socket, or broader filesystem.
- Clean up containers, networks, volumes, and temporary files after success, failure, timeout, and cancellation.

Testing:
- Capability conformance suite that any future backend must pass.
- Negative integration tests for host-source write, unapproved output write, network access, privilege escalation, fork/process limit, memory limit, timeout, symlink escape, and secret environment access.
- Test unsupported Docker and platform states through fakes where CI cannot reproduce them.
- End-to-end `harness doctor` and one generated fixture run.

Do not claim production-grade isolation beyond tested capabilities. Update security and setup docs with exact platform assumptions. Append the completion record with the capability matrix and negative-test results.
```

## Phase Completion Record

Not started.
