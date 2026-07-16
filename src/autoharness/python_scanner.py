"""AST-based Python structural scanner."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from autoharness.scan_models import IncludedFile, ParseFailure, StructuralFact

DETECTOR_VERSION = "phase3.python_scanner.v1"


def scan_python_files(
    root: Path,
    files: list[IncludedFile],
) -> tuple[list[StructuralFact], list[ParseFailure]]:
    facts: list[StructuralFact] = []
    failures: list[ParseFailure] = []
    for file in files:
        if file.language != "python":
            continue
        path = root / file.path
        source = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(source, filename=file.path)
        except SyntaxError as exc:
            failures.append(
                ParseFailure(
                    path=file.path,
                    reason=exc.msg,
                    line=exc.lineno,
                    column=exc.offset,
                )
            )
            continue
        visitor = PythonFactVisitor(file.path, file.content_hash)
        visitor.visit(tree)
        facts.extend(visitor.facts)
    facts.sort(
        key=lambda fact: (
            fact.path,
            fact.line or 0,
            fact.column or 0,
            fact.kind,
            fact.symbol or "",
        )
    )
    failures.sort(key=lambda failure: failure.path)
    return facts, failures


class PythonFactVisitor(ast.NodeVisitor):
    def __init__(self, path: str, content_hash: str) -> None:
        self.path = path
        self.content_hash = content_hash
        self.facts: list[StructuralFact] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._add(
            kind="function",
            detector_id="py.function",
            node=node,
            symbol=node.name,
            confidence_basis="AST FunctionDef node.",
        )
        self._detect_cli_decorator(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._add(
            kind="function",
            detector_id="py.async_function",
            node=node,
            symbol=node.name,
            confidence_basis="AST AsyncFunctionDef node.",
        )
        self._detect_cli_decorator(node)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._add(
                kind="import",
                detector_id="py.import",
                node=node,
                symbol=alias.name,
                confidence_basis="AST import node.",
            )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        for alias in node.names:
            symbol = f"{module}.{alias.name}" if module else alias.name
            self._add(
                kind="import",
                detector_id="py.import_from",
                node=node,
                symbol=symbol,
                confidence_basis="AST import-from node.",
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        symbol = dotted_name(node.func)
        self._add(
            kind="call_site",
            detector_id="py.call",
            node=node,
            symbol=symbol,
            confidence_basis="AST Call node.",
        )
        if symbol and is_model_call(symbol):
            self._add(
                kind="model_call_candidate",
                detector_id="py.model_call",
                node=node,
                symbol=symbol,
                confidence_basis="Known direct provider call symbol.",
                adapter_candidates=adapter_candidates(symbol),
            )
        if symbol and is_shell_call(symbol):
            self._add(
                kind="side_effect_candidate",
                detector_id="py.shell_call",
                node=node,
                symbol=symbol,
                detail="shell_or_process",
                confidence_basis="Known shell/process call symbol.",
            )
        if symbol and is_filesystem_write(symbol, node):
            self._add(
                kind="side_effect_candidate",
                detector_id="py.filesystem_write",
                node=node,
                symbol=symbol,
                detail="filesystem_write",
                confidence_basis="Known filesystem write/delete call symbol or open write mode.",
            )
        if symbol in {"getattr", "__import__", "importlib.import_module", "globals", "locals"}:
            self._add(
                kind="unknown_dynamic_pattern",
                detector_id="py.dynamic",
                node=node,
                symbol=symbol,
                confidence_basis="Dynamic lookup/import pattern requires later interpretation.",
            )
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> None:
        for handler in node.handlers:
            if handler.type is None or dotted_name(handler.type) in {"Exception", "BaseException"}:
                self._add(
                    kind="broad_exception_handler",
                    detector_id="py.broad_exception",
                    node=handler,
                    symbol=dotted_name(handler.type) if handler.type is not None else "bare_except",
                    confidence_basis="Bare except or broad Exception handler.",
                )
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        if _is_main_guard(node):
            self._add(
                kind="cli_candidate",
                detector_id="py.main_guard",
                node=node,
                symbol="__main__",
                confidence_basis="if __name__ == '__main__' guard.",
            )
        self.generic_visit(node)

    def _detect_cli_decorator(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for decorator in node.decorator_list:
            symbol = dotted_name(decorator.func if isinstance(decorator, ast.Call) else decorator)
            if symbol and (
                symbol.endswith(".command")
                or symbol.endswith(".callback")
                or symbol in {"click.command", "typer.command"}
            ):
                self._add(
                    kind="cli_candidate",
                    detector_id="py.cli_decorator",
                    node=node,
                    symbol=node.name,
                    detail=symbol,
                    confidence_basis="Typer or Click-style command decorator.",
                )

    def _add(
        self,
        *,
        kind: str,
        detector_id: str,
        node: ast.AST,
        confidence_basis: str,
        symbol: str | None = None,
        detail: str | None = None,
        adapter_candidates: list[str] | None = None,
    ) -> None:
        line = getattr(node, "lineno", None)
        column = getattr(node, "col_offset", None)
        self.facts.append(
            StructuralFact(
                kind=kind,
                path=self.path,
                line=line,
                column=column,
                symbol=symbol,
                detail=detail,
                detector_id=detector_id,
                evidence_hash=evidence_hash(self.content_hash, kind, line, column, symbol, detail),
                confidence_basis=confidence_basis,
                adapter_candidates=adapter_candidates or [],
            )
        )


def dotted_name(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = dotted_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def is_model_call(symbol: str) -> bool:
    lowered = symbol.lower()
    return (
        "chat.completions.create" in lowered
        or "responses.create" in lowered
        or "completions.create" in lowered
        or "inferenceclient" in lowered
        or lowered.startswith("groq.")
        or lowered.startswith("openai.")
    )


def adapter_candidates(symbol: str) -> list[str]:
    lowered = symbol.lower()
    adapters = []
    if "groq" in lowered:
        adapters.append("groq")
    if "inferenceclient" in lowered or "huggingface" in lowered:
        adapters.append("huggingface")
    if "openai" in lowered or "chat.completions.create" in lowered or "responses.create" in lowered:
        adapters.append("openai_compatible")
    return sorted(set(adapters))


def is_shell_call(symbol: str) -> bool:
    return symbol in {
        "os.system",
        "subprocess.call",
        "subprocess.check_call",
        "subprocess.check_output",
        "subprocess.Popen",
        "subprocess.run",
    }


def is_filesystem_write(symbol: str, node: ast.Call) -> bool:
    if (
        symbol
        in {
            "os.remove",
            "os.unlink",
            "os.rename",
            "os.replace",
            "shutil.rmtree",
            "Path.write_text",
            "Path.write_bytes",
            "write_text",
            "write_bytes",
        }
        or symbol.endswith(".write_text")
        or symbol.endswith(".write_bytes")
    ):
        return True
    if symbol == "open":
        return _open_uses_write_mode(node)
    return False


def _open_uses_write_mode(node: ast.Call) -> bool:
    mode: str | None = None
    if (
        len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and isinstance(node.args[1].value, str)
    ):
        mode = node.args[1].value
    for keyword in node.keywords:
        if (
            keyword.arg == "mode"
            and isinstance(keyword.value, ast.Constant)
            and isinstance(keyword.value.value, str)
        ):
            mode = keyword.value.value
    return mode is not None and any(flag in mode for flag in ("w", "a", "x", "+"))


def _is_main_guard(node: ast.If) -> bool:
    test = node.test
    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or len(test.comparators) != 1:
        return False
    if not isinstance(test.ops[0], ast.Eq):
        return False
    left = dotted_name(test.left)
    right = test.comparators[0]
    return left == "__name__" and isinstance(right, ast.Constant) and right.value == "__main__"


def evidence_hash(
    content_hash: str,
    kind: str,
    line: int | None,
    column: int | None,
    symbol: str | None,
    detail: str | None,
) -> str:
    payload = "|".join(
        [
            content_hash,
            kind,
            str(line or ""),
            str(column or ""),
            symbol or "",
            detail or "",
        ]
    )
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
