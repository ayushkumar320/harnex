"""Read-only repository inventory for scanner input."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

import pathspec

from agentharness.errors import AgentHarnessError, ErrorContext
from agentharness.scan_models import ExcludedPath, IncludedFile, RepositoryInventory, ScanConfig

DEFAULT_MAX_FILE_BYTES = 1_000_000
AGENTHARNESS_IGNORE = ".agentharnessignore"

# ponytail: vendored code is excluded by directory name, so a first-party package that happens
# to be called `vendor` is skipped too. Add a per-repository include list if that becomes real.
DEFAULT_EXCLUDED_DIRS = {
    ".agentharness",
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "bower_components",
    ".eggs",
    "env",
    "node_modules",
    "site-packages",
    "third_party",
    "vendor",
    "vendored",
    "venv",
}
# A secret is a credential *name* followed by a credential-shaped *value*. Matching the name
# alone flags every README and .env.example that documents which variables to set.
# Value must stay on the assignment's own line: `\s` would let `KEY=\nNEXT_VAR` capture the
# following variable name as if it were a secret.
SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?:OPENAI_API_KEY|GROQ_API_KEY|HF_TOKEN|ANTHROPIC_API_KEY|AWS_SECRET_ACCESS_KEY)"
    r"[ \t]*[=:][ \t]*[\"']?([A-Za-z0-9_\-/+]{16,})"
)
PEM_PATTERN = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
SECRET_VALUE_PATTERN = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}")
PLACEHOLDER_PATTERN = re.compile(
    r"your|example|placeholder|changeme|change_me|dummy|sample|insert|replace|"
    r"xxx|\.\.\.|here|todo|redact|fake|test|abc123|<|\{\{",
    re.IGNORECASE,
)

SECRET_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".npmrc",
    ".pypirc",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
}

SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}
BINARY_SAMPLE_BYTES = 4096


def build_inventory(
    root_input: Path,
    *,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> RepositoryInventory:
    root = _resolve_root(root_input)
    gitignore = _load_pathspec(root, ".gitignore")
    agentharness_ignore = _load_pathspec(root, AGENTHARNESS_IGNORE)

    included: list[IncludedFile] = []
    excluded: list[ExcludedPath] = []

    for directory, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current = Path(directory)
        rel_dir = _relative_path(root, current)

        kept_dirs = []
        for dirname in sorted(dirnames):
            path = current / dirname
            rel = _join_rel(rel_dir, dirname)
            reason = _exclusion_reason(
                root,
                path,
                rel,
                gitignore=gitignore,
                agentharness_ignore=agentharness_ignore,
                is_dir=True,
                max_file_bytes=max_file_bytes,
            )
            if reason is None:
                kept_dirs.append(dirname)
            else:
                excluded.append(ExcludedPath(path=rel, reason=reason))
        dirnames[:] = kept_dirs

        for filename in sorted(filenames):
            path = current / filename
            rel = _join_rel(rel_dir, filename)
            reason = _exclusion_reason(
                root,
                path,
                rel,
                gitignore=gitignore,
                agentharness_ignore=agentharness_ignore,
                is_dir=False,
                max_file_bytes=max_file_bytes,
            )
            if reason is not None:
                excluded.append(ExcludedPath(path=rel, reason=reason))
                # A Python file carrying a credential-shaped literal is exactly where gaps
                # cluster. Report the secret, but keep the file in structural analysis: facts
                # record symbols and line numbers, never source text.
                if not (reason == "secret_content" and path.suffix == ".py"):
                    continue

            data = path.read_bytes()
            included.append(
                IncludedFile(
                    path=rel,
                    language=_language_for(path),
                    size_bytes=len(data),
                    content_hash=_sha256(data),
                )
            )

    included.sort(key=lambda item: item.path)
    excluded.sort(key=lambda item: item.path)
    language_counts: dict[str, int] = {}
    for item in included:
        language_counts[item.language] = language_counts.get(item.language, 0) + 1

    return RepositoryInventory(
        root=str(root),
        included_files=included,
        excluded_paths=excluded,
        language_counts=dict(sorted(language_counts.items())),
        scan_config=ScanConfig(max_file_bytes=max_file_bytes, ignore_file=AGENTHARNESS_IGNORE),
    )


def _resolve_root(root_input: Path) -> Path:
    root = root_input.expanduser().resolve(strict=False)
    if not root.exists():
        raise AgentHarnessError(
            code="AH-S001",
            message="Repository path does not exist.",
            context=ErrorContext(
                field="path",
                source="argument",
                expected="An existing repository directory.",
                next_action="Pass an existing directory to harness scan.",
            ),
            exit_code=3,
        )
    if not root.is_dir():
        raise AgentHarnessError(
            code="AH-S002",
            message="Repository path is not a directory.",
            context=ErrorContext(
                field="path",
                source="argument",
                expected="A repository directory.",
                next_action="Pass a directory rather than a file.",
            ),
            exit_code=3,
        )
    return root


def _load_pathspec(root: Path, filename: str) -> pathspec.PathSpec:
    path = root / filename
    if not path.exists() or not path.is_file():
        return pathspec.PathSpec.from_lines("gitwildmatch", [])
    lines = path.read_text(encoding="utf-8").splitlines()
    return pathspec.PathSpec.from_lines("gitwildmatch", lines)


def _exclusion_reason(
    root: Path,
    path: Path,
    rel: str,
    *,
    gitignore: pathspec.PathSpec,
    agentharness_ignore: pathspec.PathSpec,
    is_dir: bool,
    max_file_bytes: int,
) -> str | None:
    if path.name in DEFAULT_EXCLUDED_DIRS:
        return "default_excluded_directory"
    if path.is_symlink():
        try:
            target = path.resolve(strict=True)
        except OSError:
            return "broken_symlink"
        if not _is_relative_to(target, root):
            return "symlink_outside_root"
        return "symlink"
    rel_match = rel + "/" if is_dir else rel
    if gitignore.match_file(rel_match):
        return "gitignore"
    if agentharness_ignore.match_file(rel_match):
        return "agentharness_ignore"
    if not is_dir:
        if _looks_secret(path):
            return "secret_path"
        try:
            size = path.stat().st_size
        except OSError:
            return "unreadable"
        if size > max_file_bytes:
            return "oversized_file"
        sample = path.read_bytes()[:BINARY_SAMPLE_BYTES]
        if b"\x00" in sample:
            return "binary_file"
        if _looks_secret_content(sample):
            return "secret_content"
    return None


def _looks_secret(path: Path) -> bool:
    name = path.name.lower()
    return name in SECRET_NAMES or path.suffix.lower() in SECRET_SUFFIXES


def _looks_secret_content(sample: bytes) -> bool:
    text = sample.decode("utf-8", errors="ignore")
    if PEM_PATTERN.search(text) is not None:
        return True
    for match in SECRET_ASSIGNMENT_PATTERN.finditer(text):
        if not _is_placeholder(match.group(1)):
            return True
    return any(not _is_placeholder(match.group(0)) for match in SECRET_VALUE_PATTERN.finditer(text))


def _is_placeholder(value: str) -> bool:
    """True when a credential-shaped string is documentation rather than a live secret."""
    return PLACEHOLDER_PATTERN.search(value) is not None or len(set(value)) < 6


def _language_for(path: Path) -> str:
    if path.suffix == ".py":
        return "python"
    return "other"


def _relative_path(root: Path, path: Path) -> str:
    rel = path.relative_to(root)
    return "" if rel == Path(".") else rel.as_posix()


def _join_rel(parent: str, child: str) -> str:
    if not parent:
        return child
    return f"{parent}/{child}"


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()
