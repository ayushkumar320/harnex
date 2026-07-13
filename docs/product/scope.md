# Scope and Success Metrics

## MVP Boundary

The first release supports:

- Python 3.12
- A single Python function or CLI entry point
- Direct Groq, Hugging Face Inference, and generic OpenAI-compatible calls
- Static detection of common shell and filesystem operations
- Read-only audit reports in human and versioned JSON formats
- Deterministic JSONL runtime logging templates
- Provider-level retries that occur before external side effects
- A rootless Docker-based sandbox for a constrained tool adapter
- Fixture-driven verification and fault injection

LangGraph support is the first framework adapter after direct provider calls are stable.

## Support Tiers

Every detected behavior receives one tier:

| Tier | Meaning | Generation behavior |
| --- | --- | --- |
| `verified` | Adapter and conformance fixtures cover this exact pattern | Allowed after plan approval |
| `detected` | Evidence matches a known family but lacks full contract proof | Review required; generation normally blocked |
| `unknown` | Structural evidence exists without a supported interpretation | Findings only |
| `unsafe` | Known risk prevents a trustworthy transformation | Blocked with remediation |

Support is attached to findings, not the whole repository. A repo may have a verified entry point and an unknown tool registry.

## Explicit Non-Goals for MVP

- Claiming that a repository is production-safe
- Executing target code during scanning
- TypeScript or multi-language repositories
- Distributed or multi-agent runtime orchestration
- Browser automation and database-write sandboxing
- Full semantic correctness evaluation
- Replacing LangSmith, Langfuse, OpenTelemetry, Docker, or E2B
- Automatically fixing dynamic imports, monkey patching, or arbitrary metaprogramming
- Running paid or live model calls in default tests
- Supporting every model-provider option through provider-specific logic

## Success Metrics

### Detection quality

- Entrypoint precision and recall
- Model call-site precision and recall
- Side-effect call-site precision and recall
- False-positive findings per thousand source lines
- Percentage of unknown findings correctly escalated instead of misclassified

### Product utility

- Time to first useful finding
- Percentage of scans completed without configuration
- Developer corrections per plan
- Percentage of findings with actionable remediation
- CI stability across repeated scans

### Generation quality

- Install and import success on verified fixture repos
- Stable diff rate for unchanged inputs
- User-edit preservation during reapplication
- Seeded failures caught by generated verification
- Unsupported transformations correctly blocked

### Safety

- Secret leakage tests passed
- Path traversal and symlink bypass tests passed
- Duplicate side-effect tests passed
- Sandbox capability tests passed
- Verification performs no unapproved network or host writes

### Cost and performance

- Deterministic scan duration by repository size
- Peak memory by source-file count
- Model calls and tokens per assisted operation
- Successful operation under free-tier rate limits
- Structural inventory quality with the LLM unavailable, clearly separated from full-audit quality

## Benchmark Corpus

Create `autoharness-bench` from 10 to 20 small repositories or fixtures with labeled ground truth and seeded failures:

- Provider timeout before a response
- Timeout after a fake side effect commits
- Rate limiting with `Retry-After`
- Malformed structured output
- Broad `except` around a tool call
- Path traversal and symlink escape
- Secret in a documentation file
- Prompt injection in `README.md`
- Dynamic tool registration marked unknown
- User-modified generated file

Do not tune only against repositories created by the AutoHarness author. Hold out several repos until release evaluation.

## Release Gate

The first public alpha requires:

- Versioned JSON schemas and documented exit codes
- Measured precision and recall on the benchmark corpus
- No silent overwrite path
- No live credentials needed for the test suite
- Passing sandbox negative tests on supported platforms
- Reproducible UV lock and container build
- Documentation that labels unsupported and unverified behavior accurately
