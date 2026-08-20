from pathlib import Path


def check():
    groq = Path.home() / ".config" / "groq_keys.env"
    openai = Path.home() / ".config" / "openai.env"
    return groq.is_file() and openai.is_file()
