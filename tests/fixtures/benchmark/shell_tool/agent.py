import subprocess


def run():
    return subprocess.run(["echo", "hello"], check=False)
