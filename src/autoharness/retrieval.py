"""Deterministic local documentation and docstring retrieval."""

from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path

from rapidfuzz import fuzz

from autoharness.repository import build_inventory
from autoharness.retrieval_models import RetrievedEvidence

DOCUMENT_NAMES = {"README.md", "README.rst", "README.txt", "AGENTS.md"}
DOCUMENT_SUFFIXES = {".md", ".rst", ".txt"}
MAX_CHUNK_CHARS = 1600
TOKEN_RE = re.compile(r"[a-zA-Z0-9_.-]+")


def build_local_index(root: Path) -> list[RetrievedEvidence]:
    inventory = build_inventory(root)
    evidence: list[RetrievedEvidence] = []
    for file in inventory.included_files:
        path = Path(inventory.root) / file.path
        if _is_document_path(file.path):
            evidence.extend(_document_chunks(path, file.path))
        elif file.language == "python":
            evidence.extend(_docstring_chunks(path, file.path))
    evidence.sort(key=lambda item: item.id)
    return evidence


def retrieve_local(
    index: list[RetrievedEvidence],
    query: str,
    *,
    limit: int = 5,
) -> list[RetrievedEvidence]:
    query_tokens = set(_tokens(query))
    ranked = []
    for item in index:
        text_tokens = set(_tokens(item.text))
        overlap = len(query_tokens & text_tokens)
        fuzzy = fuzz.partial_ratio(query, item.text) / 100
        score = overlap + fuzzy
        if score > 0:
            ranked.append((score, item))
    ranked.sort(key=lambda pair: (-pair[0], pair[1].id))
    return [item.model_copy(update={"score": round(score, 4)}) for score, item in ranked[:limit]]


def _is_document_path(path: str) -> bool:
    item = Path(path)
    return item.name in DOCUMENT_NAMES or (
        path.startswith("docs/") and item.suffix in DOCUMENT_SUFFIXES
    )


def _document_chunks(path: Path, rel_path: str) -> list[RetrievedEvidence]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    chunks = []
    current_heading = Path(rel_path).name
    current_start = 1
    current_lines: list[str] = []
    for index, line in enumerate(lines, start=1):
        if line.startswith("#") and current_lines:
            chunks.append(
                _chunk(rel_path, current_heading, current_start, index - 1, current_lines)
            )
            current_heading = line.lstrip("#").strip() or current_heading
            current_start = index
            current_lines = [line]
        else:
            if line.startswith("#"):
                current_heading = line.lstrip("#").strip() or current_heading
                current_start = index
            current_lines.append(line)
        if sum(len(part) for part in current_lines) > MAX_CHUNK_CHARS:
            chunks.append(_chunk(rel_path, current_heading, current_start, index, current_lines))
            current_start = index + 1
            current_lines = []
    if current_lines:
        chunks.append(_chunk(rel_path, current_heading, current_start, len(lines), current_lines))
    return chunks


def _docstring_chunks(path: Path, rel_path: str) -> list[RetrievedEvidence]:
    source = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    chunks: list[RetrievedEvidence] = []
    module_doc = ast.get_docstring(tree)
    if module_doc:
        chunks.append(_doc_chunk(rel_path, "<module>", 1, module_doc))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            docstring = ast.get_docstring(node)
            if docstring:
                chunks.append(_doc_chunk(rel_path, node.name, node.lineno, docstring))
    return chunks


def _chunk(
    rel_path: str,
    heading: str,
    start: int,
    end: int,
    lines: list[str],
) -> RetrievedEvidence:
    text = "\n".join(lines).strip()
    return RetrievedEvidence(
        id=_evidence_id(rel_path, start, end, text),
        source="local_documentation",
        path=rel_path,
        heading_or_symbol=heading,
        start_line=start,
        end_line=end,
        content_hash=_sha256(text),
        text=text,
        score=0,
    )


def _doc_chunk(rel_path: str, symbol: str, line: int, text: str) -> RetrievedEvidence:
    cleaned = text.strip()
    return RetrievedEvidence(
        id=_evidence_id(rel_path, line, line, cleaned),
        source="docstring",
        path=rel_path,
        heading_or_symbol=symbol,
        start_line=line,
        end_line=line,
        content_hash=_sha256(cleaned),
        text=cleaned,
        score=0,
    )


def _evidence_id(path: str, start: int, end: int, text: str) -> str:
    digest = hashlib.sha256(f"{path}:{start}:{end}:{text}".encode()).hexdigest()[:16]
    return f"local:{digest}"


def _sha256(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]
