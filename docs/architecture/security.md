# Security Model

## Security Position

AutoHarness inspects and may later execute repositories that are buggy, compromised, or intentionally hostile. Its own model output is also untrusted.

Security claims are capability-specific. AutoHarness must never report "sandboxed" or "verified" when only a configuration file exists.

## Trust Boundaries

- Target repository files and metadata
- Repository documentation and agent-instruction files
- Model-provider requests and responses
- Provider-route configuration, health state, and cross-provider evidence transfer
- Tavily queries and external web evidence
- Generated source and configuration
- Tool and subprocess output
- Container or remote sandbox runtime
- Host filesystem, credentials, and network

## Scan Boundary

`harness scan` must not:

- Import target modules
- Execute setup scripts, plugins, hooks, notebooks, or tests
- Resolve code by running package managers
- Follow symlinks outside the repository root
- Read ignored secret files by default
- Make a provider call unless the user explicitly enables model assistance

The repository view normalizes paths, applies limits, records exclusions, and opens files as data.

## Documentation Prompt Injection

README files, `AGENTS.md`, docstrings, and test text may contain instructions aimed at the planner. Retrieved content is quoted and delimited as repository evidence. It cannot:

- Change AutoHarness system policy
- Enable a provider or network
- Request secret access
- Alter allowed output paths
- Approve a finding or generation action

Security fixtures include common prompt-injection patterns.

The same rule applies to web pages returned by Tavily. Search ranking and official-looking domains do not make retrieved content trusted.

## External Evidence Privacy

Tavily requests may contain public package names, versions, API symbols, official-domain filters, and narrowly phrased technical questions. They must not contain private repository names, source snippets, prompts, credentials, internal URLs, customer data, or secret-derived values without a separate explicit policy and preview.

Web enrichment is off by default for private repositories, disabled during verification, and bounded by a per-command credit budget. Responses are cached with URL, domain, retrieval time, query hash, content hash, and expiration. Redirects and final domains are validated against policy.

External-evidence cache files live in the AutoHarness user cache directory, never in the target
repository. Cache reads are untrusted inputs: the cache key, query hash, content hash, canonical
domain, and final domain are revalidated before evidence is reused. Invalid entries are treated as
cache misses.

Tavily content is delimited as untrusted external evidence. It cannot create permissions, approve generation, change sandbox policy, select a remote model, or override local structural evidence.

## Secret Handling

- Exclude `.env`, private keys, credential stores, and configured patterns from retrieval.
- Scan values for secret-like tokens before logging or provider requests.
- Redact headers, environment values, connection strings, and provider error bodies.
- Keep raw prompt and output logging disabled by default.
- Ensure debug mode uses the same redaction path.

## Provider Fallback Safety

Fallback is permission-preserving, not an escape from an unavailable provider. Every route
entry declares its locality and must be explicitly configured before repository evidence is
built. `local_only` filters all remote destinations, including otherwise healthy fallbacks.
Capability reduction cannot relax secret filtering, evidence bounds, output-path policy, or
schema validation.

All provider attempts for one logical request reference the same redacted evidence-manifest
hash. Destination-specific context limits may remove evidence but cannot add unpreviewed
content. Health and circuit-breaker records contain normalized failures and timing only, not
prompts, outputs, credentials, or provider error bodies. Parallel hedged requests are not
used because they unnecessarily disclose the same evidence to multiple services.
Synchronous provider SDK methods run outside the async event loop, and configured SDK timeouts
match the router attempt deadline. Router cancellation bounds caller waiting; the SDK timeout bounds
the underlying synchronous request.

## Side-Effect Classification

Every operation considered for retry is one of:

- `read_only`
- `idempotent` with a stable idempotency key
- `transactional` with known commit or rollback
- `non_idempotent`
- `unknown`

Automatic retry is allowed only for proven read-only operations or idempotent operations with a supported guarantee. If a timeout occurs after an unknown side effect may have committed, return `commit_status_unknown` and stop.

Maintain an attempt ledger with operation ID, attempt, start, completion, normalized result, and provider idempotency key when applicable.
The Phase 5 runtime core records a start and finish ledger entry around each attempted operation.
Unknown and non-idempotent operations receive one attempt only, idempotent operations require a
stable key before retry is allowed, and logger failures must not change target-operation behavior
or print unredacted fallback content.
Malformed-output correction packets are allowed only before an external side effect. They carry a
bounded, redacted user-goal summary and normalized failure metadata rather than raw prompts,
outputs, headers, environment values, or provider error bodies.

## Sandbox Enforcement

The MVP sandbox uses a dedicated rootless Docker execution backend with:

- Non-root user
- Read-only repository mount
- Dedicated writable output and temporary mounts
- Network denied by default
- Dropped Linux capabilities
- `no-new-privileges`
- CPU, memory, process, and wall-clock limits
- Explicit environment allowlist
- Controlled executable interface

Command-name deny lists are only defense in depth. They do not prevent interpreter, child-process, alias, encoding, or path-based bypasses.

Phase 6 currently implements the first Docker backend contract in `src/autoharness/sandbox.py` and
a separate `Dockerfile.sandbox` target-execution image. `harness doctor` reports the Docker daemon,
the local sandbox image, mount policy, network denial, non-root user, dropped capabilities,
`no-new-privileges`, resource limits, and environment allowlisting. The backend fails closed when
the daemon or image is unavailable, when writable mounts are inside the source tree, or when
secret-like environment variables are requested. Capability evidence must remain tied to observed
backend behavior or explicit Docker flags; do not broaden the claim to arbitrary host isolation.

Path tests must cover traversal, absolute paths, symlinks, mount boundaries, case behavior, and time-of-check/time-of-use assumptions. If Docker cannot enforce a declared capability on the host platform, verification fails closed.

The AutoHarness application container in the root `Dockerfile` is not the target-code sandbox.

## Generation Safety

- Generate into staging, never directly into arbitrary target paths.
- Restrict output paths to the approved plan.
- Reject absolute paths, traversal, symlink escapes, and unexpected file types.
- Validate templates and schema before staging.
- Show the diff before applying.
- Record provenance and use three-way comparison on reapplication.
- Never silently replace developer-edited generated files.
- Before replacing an existing generated target or generated-base snapshot, persist a
  transaction-scoped backup and restore both layers if any later transaction step fails.

## Verification Safety

Verification uses a disposable worktree or sandbox, fixture credentials, mocked providers, and denied network. Importing or executing target code occurs only within this boundary.

Host-side verification rejects repository symlinks before hashing or copying the tree so an
untrusted link cannot cause reads outside the declared repository root.

Live calls, package installation, network access, browser automation, database access, and destructive tools require separate explicit approval. Results identify anything not exercised.

## Logging Safety

Structured events pass through redaction before serialization. A logger failure must not crash a target operation or fall back to unredacted console output. Logs have bounded field sizes and prevent terminal-control injection in human rendering.

## Required Negative Tests

- Symlink and `..` repository escape
- Secret in source, docs, exception, and provider response
- Prompt injection in every indexed document type
- Malicious filename and terminal-control sequence
- Retry after a committed fake side effect
- Unsupported sandbox capability
- Stale plan and user-modified generated file
- Network call during default verification
- Private repository detail included in a Tavily query
- Redirect from an allowed documentation domain to an unapproved domain
- Container process and resource-limit escape attempts appropriate to the supported backend

## Threat-Model Maintenance

Every new adapter or execution capability updates this document and adds negative fixtures. Security review is required when a phase introduces target-code execution, new remote data flow, broader filesystem access, or a new sandbox backend.
