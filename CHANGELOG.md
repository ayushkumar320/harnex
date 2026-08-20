# Changelog

## 0.1.0a4

- Added the side-effect half of the harness: the `tool` decorator. It declares what re-running a
  function would do and enforces it. Read-only and idempotent tools retry on transient failures;
  an idempotent tool must supply an idempotency key, and a key that already committed in this
  process returns its recorded result instead of running the tool again, which closes the
  "the retry wrote the file twice" failure the README opens with. Non-idempotent and undeclared
  tools are never retried: they raise `CommitStatusUnknown`, because whether the effect committed
  is not observable from outside and a guess in either direction is a data bug. `AGENTHARNESS_DRY_RUN=1`
  blocks every mutating tool and records the intent it would have performed.
- `AH-S101` now treats a side effect inside a declared `@tool` as having its enforceable boundary,
  so the rule closes the same way `AH-R101` does: audit names the gap, one decorator closes it,
  audit confirms. `StructuralFact` gained an explicit `guarded` flag that both rules read.

- Added the runtime harness as a library front door: `wrap(client)` and the `@guard` decorator.
  The runtime primitives — bounded retry executor, normalized failure classification, redacted
  JSONL events — already existed, but the only way to reach them was a five-step audit workflow
  that generated a wrapper file into `.agentharness/generated/` for the user to wire up by hand.
  `wrap` is a transparent proxy: it guards the provider calls it recognizes, using the same
  method-chain table the static scanner uses, and passes every other attribute through untouched.
- Closed the audit loop. `AH-R101` now treats a wrapped client as instrumentation, so the finding
  it reports has a one-line fix and the next scan confirms it: audit names the gap, `wrap` closes
  it, audit goes quiet. Its remediation text names the fix instead of describing a category.

- Widened provider-call detection beyond OpenAI. `is_model_call` matched six substrings, so
  Anthropic, Bedrock, Gemini, Mistral, Cohere, LiteLLM, Ollama, and Vertex calls were invisible:
  on a 537-file agent repository the scan reported 2 model calls and missed a live
  `bedrock.converse` loop. Detection now matches provider-only method chains through any receiver
  name, plus module-level generation functions whose root is actually imported in the file.
- Fixed the `AH-R101` false positive on locals that share a provider's name. Detection used
  `symbol.startswith("groq.")`, so `groq = Path.home() / "groq_keys.env"` followed by
  `groq.is_file()` was reported as an uninstrumented model call at high severity. Module-level
  provider functions now require the root name to be bound by an import in that file. Both
  `AH-R101` findings on the measured repository were this false positive.
- Stopped reporting instrumented model calls as uninstrumented. `AH-R101` fired identically on a
  `while True` / `except Exception: pass` retry and on a call with `timeout=`, `max_retries=`,
  a bounded loop, a typed handler, and a terminal raise, which made the rule's own title false.
  A call with a bounding keyword argument or a retry decorator in scope is no longer a finding;
  it is still counted as a `model_call_candidate` fact so the summary stays honest.
- Added `AH-R103`, unbounded retry loop: a `while True` wrapping an exception handler that
  neither breaks, returns, nor re-raises. This is the failure that burns a token budget overnight,
  and no rule covered it. It matched 3 real sites in 537 files.
- Stopped excluding secret-bearing Python files from structural analysis. A credential-shaped
  literal excluded the whole file, so the file most worth auditing was the one least audited: a
  fixture with six planted gaps reported two findings until its fake API key was deleted, then
  eight. Such files are now parsed for facts, which record symbols and line numbers but never
  source text, while `AH-S201` still reports the secret.
- Extended the alpha benchmark corpus from 10 to 15 labeled cases, covering an Anthropic call, an
  instrumented call that must stay silent, an unbounded retry loop, a local variable named after a
  provider, and a secret-bearing module with a real gap in it.

## 0.1.0a3

- Widened `requires-python` from `>=3.12,<3.14` to `>=3.12,<3.15`. Python 3.14 is already the
  default interpreter on current macOS and Homebrew installs, so the old cap made
  `pip install agentgap` fail with "Could not find a version that satisfies the requirement" for
  users whose Python was perfectly capable of running it. The full test suite passes on 3.14. The
  npm wrapper's independent interpreter gate, its candidate list, and its test were widened to
  match, and CI now runs the checks on 3.12, 3.13, and 3.14 so the declared range stays true.

## 0.1.0a2

- Renamed the PyPI and npm distribution from `agentharness` to `agentgap`. PyPI rejects
  `agentharness` as too similar to the existing `agent-harness` project, which strips separators
  when comparing names. The import package stays `agentharness`, as does the `.agentharness/`
  artifact directory, the `AGENTHARNESS_` environment prefix, the sandbox image name, and the
  `harness` command; `agent-harness` installs a module named `agent_harness`, so there is no import
  collision to resolve.
- Excluded vendored dependencies from the scan. `DEFAULT_EXCLUDED_DIRS` covered `.venv` and
  `node_modules` but not `vendor`, `venv`, `env`, `site-packages`, `third_party`,
  `bower_components`, or `.eggs`, so third-party code was audited as if it were first-party. On one
  measured repository 15,725 of 16,505 findings came from `vendor/`.
- Fixed `AH-S201` false positives on documentation. Secret detection matched credential names
  rather than credential values, so any README or `.env.example` documenting
  `GROQ_API_KEY=your_groq_api_key` was flagged and silently excluded from analysis.
  `_looks_secret_content` now requires a credential name followed by a credential-shaped value on
  the same line and rejects placeholder values. Restricting the value to its own line matters:
  `\s` would let `KEY=\nNEXT_VAR` capture the following variable name. The PEM check is now one
  contiguous pattern, so a secret scanner carrying `-----BEGIN ` and `PRIVATE KEY-----` as separate
  constants no longer flags its own source. Measured across six repositories, total findings fell
  from 16,798 to 1,016 and `AH-S201` false positives to zero.
- Added `harness report`, which renders a scan artifact as a Markdown brief grouped by severity
  with file, line, and symbol evidence per finding. Generation covers only `AH-R101`, so on most
  repositories the findings are the whole deliverable.
- Bare `harness` now runs a read-only audit of the current directory instead of printing help.
- Corrected the project URLs in `pyproject.toml` and `npm/package.json`, which pointed at a
  repository that does not exist.
- Rewrote the README and the npm README around the failure modes the tool detects, a walkthrough
  with real output, and an explicit statement of what the tool does not do.
- Removed `docs/build/`, the phase-by-phase implementation plans, now that the baseline is built.
- Added `harness audit`, `harness improve`, and `harness check`: one-command workflows that compose
  the existing scan, plan, approve, apply, and verify primitives and record a versioned
  `workflow_run` artifact at `.agentharness/workflow.json`. `audit` stays read-only, and `improve`
  requires separate approvals for the plan and for the exact staged files.
- Added `harness approve`, which records explicit human approval on a plan artifact. Without it the
  deterministic planner could only emit `unresolved` actions, so `harness apply` was unreachable
  from a real `harness plan` run.
- The planner now proposes the direct-provider generation templates as a
  `write_generated_files` action instead of a `review_only` placeholder, connecting planning to the
  existing generation templates.
- Verification now reports an unavailable Docker sandbox as `not_exercised` instead of `failed`, so
  `harness verify` no longer fails on machines without Docker while still reporting incompleteness.

## 0.1.0a1

- Renamed the distribution and import package from `autoharness` to `agentharness`. The PyPI name
  `autoharness` belongs to an unrelated project, so the old import name could collide in a shared
  environment. Artifact directories are now `.agentharness/`, environment variables use the
  `AGENTHARNESS_` prefix, and the sandbox image is `agentharness-sandbox`. The CLI command is
  still `harness`.
- Added the MIT license.
- Added an npm wrapper package that installs the matching Python wheel into a private virtual
  environment and forwards arguments and exit codes to the `harness` CLI.
- Added packaging metadata: authors, license, keywords, classifiers, and project URLs. The version
  is now read from `agentharness.__version__` so it has a single source of truth.
- Made apply rollback restore existing generated targets and generated-base snapshots.
- Enforced provider attempt deadlines for synchronous SDK clients without blocking the async router.
- Moved external-evidence caching outside scanned repositories and revalidated cached provenance.
- Rejected repository symlinks before host-side verification reads.

## 0.0.0-alpha (unpublished)

- Added read-only Python repository scanning with versioned JSON reports.
- Added evidence-backed deterministic findings and read-only planning.
- Added constrained direct-provider generation with staged previews, apply transactions, rollback,
  and three-way reapply checks.
- Added runtime reliability primitives for JSONL events, redaction, retry policy, attempt ledgers,
  malformed-output correction packets, and human failure summaries.
- Added a Docker sandbox backend with a separate target-execution image and doctor capability
  reporting.
- Added `harness verify` for deterministic verification checks in a disposable workspace.
- Added `harness benchmark` and a 10-case labeled alpha corpus with held-out fixtures.

Known alpha limits:

- Python only; TypeScript and framework adapters are not alpha-supported.
- Direct-provider generation is limited to the verified fixture pattern.
- Default tests and benchmark do not make live provider calls.
- Docker sandbox support depends on the host Docker daemon and `agentharness-sandbox:dev` image.
- Semantic eval drafts require developer-approved oracles before scoring.
