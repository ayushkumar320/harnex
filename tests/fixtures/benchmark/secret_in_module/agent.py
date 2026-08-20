import subprocess

API_KEY = "sk-proj-h7Qw2Zx9Lm4Rt8Bv6Nc1Ke5Yj3Pd0Sa7Uf2Gh9Wq4Xz"


def run(cmd):
    return subprocess.run(cmd, shell=True)
