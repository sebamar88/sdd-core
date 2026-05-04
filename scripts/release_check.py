from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMP_ROOT = REPO_ROOT / ".tmp-release-check"
SMOKE_ROOT = TEMP_ROOT / "smoke-repo"
VENV_ROOT = TEMP_ROOT / "venv"


def run(command: list[str], *, cwd: Path = REPO_ROOT) -> None:
    printable = " ".join(command)
    env = os.environ.copy()
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    print(f"$ {printable}", flush=True)
    subprocess.run(command, cwd=cwd, check=True, env=env)


def venv_python() -> Path:
    if os.name == "nt":
        return VENV_ROOT / "Scripts" / "python.exe"
    return VENV_ROOT / "bin" / "python"


def venv_cli() -> Path:
    if os.name == "nt":
        return VENV_ROOT / "Scripts" / "ssd-core.exe"
    return VENV_ROOT / "bin" / "ssd-core"


def clean_temp() -> None:
    if TEMP_ROOT.exists():
        shutil.rmtree(TEMP_ROOT)


def release_check(*, keep_temp: bool) -> None:
    clean_temp()
    TEMP_ROOT.mkdir(parents=True)

    try:
        run([sys.executable, "-m", "py_compile", "scripts/sdd.py", "ssd_core/cli.py", "ssd_core/__main__.py", "tests/test_sdd.py"])
        run([sys.executable, "-m", "unittest", "tests/test_sdd.py"])
        run([sys.executable, "scripts/sdd.py", "validate"])
        run([sys.executable, "scripts/sdd.py", "status"])
        run([sys.executable, "-m", "ssd_core", "version"])
        run([sys.executable, "-m", "pip", "install", ".", "--dry-run"])

        print(f"$ {sys.executable} -m venv {VENV_ROOT}", flush=True)
        venv.create(VENV_ROOT, with_pip=True)

        run([str(venv_python()), "-m", "pip", "install", "."])
        run([str(venv_cli()), "version"])
        run([str(venv_cli()), "init", "--root", str(SMOKE_ROOT)])
        run([str(venv_cli()), "validate", "--root", str(SMOKE_ROOT)])

        for adapter in ["codex", "claude-code", "gemini-cli", "opencode", "qwen-code", "generic-markdown"]:
            adapter_path = SMOKE_ROOT / ".sdd" / "adapters" / f"{adapter}.json"
            if not adapter_path.is_file():
                raise AssertionError(f"packaged adapter was not initialized: {adapter_path}")

        readiness_doc = SMOKE_ROOT / "docs" / "production-readiness-v0.1.md"
        adapters_doc = SMOKE_ROOT / "docs" / "adapters-v0.1.md"
        if not readiness_doc.is_file():
            raise AssertionError(f"packaged readiness doc was not initialized: {readiness_doc}")
        if not adapters_doc.is_file():
            raise AssertionError(f"packaged adapters doc was not initialized: {adapters_doc}")

        print("Release check passed.")
    finally:
        if not keep_temp:
            clean_temp()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run SSD-Core release readiness checks.")
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="keep .tmp-release-check for debugging",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    release_check(keep_temp=args.keep_temp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
