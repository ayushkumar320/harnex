from pathlib import Path

from autoharness.retrieval import build_local_index, retrieve_local


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_local_retrieval_indexes_docs_and_docstrings_deterministically(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    write(repo / "README.md", "# Agent\n\nUses OpenAI chat completions with tools.\n")
    write(
        repo / "agent.py",
        '"""Module docs about retries."""\n\n'
        "def run():\n"
        '    """Entrypoint docstring for model calls."""\n'
        "    return None\n",
    )

    first = build_local_index(repo)
    second = build_local_index(repo)
    results = retrieve_local(first, "OpenAI model calls", limit=2)

    assert [item.id for item in first] == [item.id for item in second]
    assert {item.source for item in first} == {"local_documentation", "docstring"}
    assert {item.path for item in results} == {"README.md", "agent.py"}


def test_retrieval_uses_phase_one_secret_filters(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    write(repo / "README.md", "# Public\n\nProvider docs.\n")
    write(repo / ".env", "OPENAI_API_KEY=sk-secret\n")

    index = build_local_index(repo)
    serialized = "\n".join(item.text for item in index)

    assert "sk-secret" not in serialized
