# Security Policy

AgentHarness is an alpha-stage reliability auditor. Please report security issues privately before
public disclosure.

## Supported Versions

| Version | Support |
| --- | --- |
| `0.1.0a4` | Security fixes accepted for the alpha code line |

## Reporting

Open a private security advisory or contact the project maintainer directly. Include:

- Affected command or module
- Minimal reproduction steps
- Whether target repository code was executed
- Whether secrets, filesystem writes, network access, or Docker isolation were involved

Do not include real credentials. Use fixture tokens such as `sk-redacted-test-token`.

## Current Security Claims

- `harness scan` does not import or execute target modules.
- Default benchmark and tests do not call live model providers.
- The Docker sandbox backend fails closed when Docker or the sandbox image is unavailable.
- Verification separates deterministic controls from draft semantic evals.

AgentHarness does not claim that a scanned repository is production-safe.
