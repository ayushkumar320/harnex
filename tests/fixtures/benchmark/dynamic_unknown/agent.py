import importlib


def run(name: str):
    module = importlib.import_module(name)
    entrypoint = "run"
    return getattr(module, entrypoint)()
