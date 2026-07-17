# Alpha Support Matrix

## Supported in Alpha

| Area | Support |
| --- | --- |
| Python version | Python 3.12 |
| Scan mode | Static file inventory and AST parsing; no target imports |
| Providers | Direct OpenAI-compatible, Groq-like, and Hugging Face Inference call patterns |
| Side effects | Shell/process and filesystem-write candidates |
| Generation | Approved direct-provider fixture templates only |
| Runtime reliability | Fake-provider deterministic retry, redaction, and side-effect tests |
| Sandbox | Local Docker backend with separate `autoharness-sandbox:dev` image |
| Verification | Disposable workspace, fake credentials, denied-network sandbox smoke |
| Benchmark | 10 labeled fixture repositories with held-out cases |

## Not Supported in Alpha

| Area | Status |
| --- | --- |
| TypeScript or multi-language analysis | Not supported |
| LangGraph generation | Deferred |
| Browser/database/Kubernetes sandboxing | Not supported |
| Live provider tests in default CI | Not supported |
| Semantic correctness scoring | Draft evals only; developer approval required |
| General production-safety certification | Explicitly not claimed |

## Platform Notes

The sandbox backend is tested through Docker command enforcement and a real smoke on the local
Docker host. Docker Desktop rootless internals are not independently proven; claims are limited to
the non-root container user, read-only/writable mount policy, denied network, dropped capabilities,
`no-new-privileges`, and requested resource limits.
