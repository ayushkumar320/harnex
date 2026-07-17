from pathlib import Path


def run():
    Path("result.txt").write_text("hello", encoding="utf-8")
