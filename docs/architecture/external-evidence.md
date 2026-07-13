# External Evidence Architecture

## Purpose

AutoHarness is LLM-core, but model training data is not reliable for fast-changing SDKs, provider capabilities, migration guides, or error documentation. The external-evidence layer gives the LLM current, source-backed web context without turning arbitrary web content into authority.

Tavily is the first `ExternalEvidenceProvider`. It is separate from `ModelProvider`: Tavily retrieves evidence; Groq, Hugging Face, or a local model reasons over it.

## Pipeline Placement

```text
Repository facts + dependency versions
        |                     |
        |                     -> external evidence request planner
        |                                |
Local documentation                      -> credit/privacy policy
        |                                -> Tavily Search/Extract
        |                                -> provenance + cache
        +--------------- EvidenceBundle ----------------+
                                                         |
                                                   LLM reasoning
                                                         |
                                            deterministic validators
```

External evidence is most useful after deterministic scanning has identified exact package names, versions, symbols, and unresolved questions. Do not search the web before the system knows what evidence it needs.

## Contract

```python
class ExternalEvidenceProvider:
    async def search(self, request: EvidenceSearchRequest) -> EvidenceSearchResult: ...
    async def extract(self, request: EvidenceExtractRequest) -> list[ExternalEvidence]: ...
    async def capabilities(self) -> ExternalEvidenceCapabilities: ...
    def estimate_cost(self, request: ExternalEvidenceRequest) -> CreditEstimate: ...
```

Provider SDK objects remain inside the adapter.

`ExternalEvidence` contains:

- Canonical and final URL
- Title and domain
- Retrieved content or bounded chunks
- Search query hash and relevance score
- Retrieval timestamp and expiration
- Detected package, version, and symbol when applicable
- Content hash
- Provider request ID and credits used
- Trust label such as `official`, `maintainer`, or `unverified`

Trust labels help ranking but never bypass untrusted-input handling.

## Tavily Endpoint Use

### Search

Use basic Search to discover current official pages for a precise package/version/symbol question. Set `include_answer=false`; AutoHarness's configured LLM is the reasoning core. Prefer `include_domains` over broad exclusion lists.

### Extract

Use Extract after Search or when an adapter already knows the canonical documentation URL. Batch extraction and retain only relevant bounded chunks.

### Map

Use Map in the adapter-development workflow to discover a documentation site's relevant sections. It is not needed for routine scans.

### Crawl

Use Crawl for an explicit `harness docs sync` operation that creates a versioned documentation snapshot. Restrict paths, depth, page count, and official domains.

### Research

Do not use Tavily Research in normal scan or plan commands. Its dynamic credit consumption is poorly matched to predictable free-tier operation. Consider it only for explicit maintainer research with a separate budget.

## Product Workflows

### Online scan enrichment

```bash
harness scan . --online
```

After local scanning, AutoHarness may retrieve current official evidence for detected dependencies and unresolved API behavior. The report distinguishes local and external evidence and shows credits consumed.

### Documentation snapshot

```bash
harness docs sync .
```

The command detects supported dependencies, maps them to official domains, retrieves selected documentation, and stores a content-addressed snapshot under `.autoharness/cache/docs/` with a manifest.

### Plan refresh

```bash
harness plan . --refresh-docs
```

Refresh only evidence referenced by the plan or invalidated by dependency-version changes.

### Adapter research

```bash
harness adapters research langgraph
```

Maintainer workflow: map official docs, extract entrypoint/tool/provider APIs, ask the LLM to draft an adapter and fixtures, then keep the adapter `draft` until conformance tests pass.

### Online doctor

```bash
harness doctor . --online
```

Checks Tavily credentials, current credit availability when exposed, official-domain policies, cache health, and provider reachability without scanning private content.

## Credit Budget

Default configuration:

```yaml
web_evidence:
  enabled: false
  provider: tavily
  official_domains_only: true
  search_depth: basic
  include_answer: false
  max_credits_per_command: 3
  cache_ttl_days: 14
  max_results: 5
  max_extract_urls: 5
```

Before calling Tavily, estimate cost and reject requests that exceed the command budget. Track actual credits from the response when available. Deduplicate equivalent questions across findings and batch URL extraction.

Normal scan and plan commands should use Search and Extract only. Cache hits consume no Tavily credits and must be visible in verbose output.

## Query Privacy

Allowed query material:

- Public package and framework names
- Detected public version numbers
- Public API symbols
- Generic error codes
- Narrow technical questions

Disallowed by default:

- Private repository or organization names
- Source-code snippets
- Repository prompts or documentation passages
- Internal package and host names
- Credentials, user data, or secret-derived strings
- Raw stack traces that may contain private paths or values

The request builder operates on normalized public identifiers rather than arbitrary LLM-authored strings. The user can preview planned queries with `--verbose` or machine-readable plan output.

## Domain Policy

Adapters maintain official-domain mappings for supported packages. Search results from other domains may be shown as unverified suggestions but are excluded from the LLM evidence bundle by default.

Validate redirect targets, canonical URLs, and final extraction domains. Store source type and retrieval timestamp so the LLM and user can distinguish official docs from community content.

## Evidence Selection for the LLM

Build a bounded `EvidenceBundle` containing:

1. Structural facts and exact source evidence
2. Relevant local documentation chunks
3. Current official external chunks
4. Contradictions and version mismatches
5. Missing or stale evidence notices

Use relevance, package/version match, source trust, freshness, and diversity to select chunks. Do not flood the context window with complete documentation sites.

The LLM must cite evidence IDs in candidate findings, plan actions, and troubleshooting explanations. Deterministic validation rejects references to nonexistent or expired evidence.

## Failure Behavior

Tavily authentication, quota exhaustion, timeout, or unavailability does not silently broaden search or switch services. The command either:

- Uses a valid cached snapshot
- Continues with local evidence and labels current-web validation unavailable
- Stops when fresh external evidence is explicitly required by policy

The report distinguishes `not_requested`, `cache_hit`, `fresh`, `stale_used`, `unavailable`, and `budget_exhausted`.

## Security Controls

- External retrieval is disabled during isolated verification.
- All returned pages are untrusted and prompt-injection delimited.
- HTML and Markdown are cleaned with size and content-type limits.
- URLs, redirects, schemes, and domains are validated.
- Provider responses and error bodies pass through redaction.
- Cache files use content-addressed names and never become executable inputs.
- External evidence cannot expand permissions, paths, network access, or sandbox capabilities.

## Observability

Emit redacted events:

- `external_search_started`
- `external_search_finished`
- `external_extract_finished`
- `external_cache_hit`
- `external_budget_exhausted`
- `external_evidence_rejected`

Track latency, result count, accepted domains, cache status, estimated and actual credits, and evidence IDs. Do not log raw queries when privacy policy marks them sensitive.

## Testing

Default tests use a fake Tavily adapter and HTTP fixtures. Cover:

- Search and extraction normalization
- Credit estimation and hard budget enforcement
- Cache hit, expiration, and dependency-version invalidation
- Query deduplication and extraction batching
- Domain and redirect policy
- Prompt injection in web content
- Secret or private identifier rejection in queries
- Quota, timeout, malformed response, and partial extraction
- Evidence citation validation in LLM output
- Zero network calls when online enrichment is disabled or during verification

Live Tavily smoke tests are opt-in and capped at one basic search plus one small extraction batch.

## Delivery Order

1. Define schemas and fake `ExternalEvidenceProvider`.
2. Add query privacy and credit-policy validators.
3. Implement Tavily Search and Extract.
4. Add content-addressed cache and provenance.
5. Feed bounded evidence bundles to the LLM.
6. Add `--online`, `--refresh-docs`, and `harness docs sync` UX.
7. Add Map/Crawl for maintainer and snapshot workflows.
8. Evaluate Research separately; keep it outside normal commands.
