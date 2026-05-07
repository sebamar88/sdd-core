from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tarfile
import tomllib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMP_ROOT = REPO_ROOT / ".tmp-release-check"
SMOKE_ROOT = TEMP_ROOT / "smoke-repo"
VENV_ROOT = TEMP_ROOT / "venv"
NPM_PACK_ROOT = TEMP_ROOT / "npm-pack"
NPM_PROJECT_ROOT = TEMP_ROOT / "npm-project"
NPM_SMOKE_ROOT = TEMP_ROOT / "npm-smoke-repo"
NPM_RELATIVE_SMOKE_ROOT = Path("npm-relative-smoke-repo")
VERSION_PREFIX = 'VERSION = "'


def run(command: list[str], *, cwd: Path = REPO_ROOT) -> None:
    printable = " ".join(command)
    env = os.environ.copy()
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    env["UV_LINK_MODE"] = "copy"
    print(f"$ {printable}", flush=True)
    subprocess.run(command, cwd=cwd, check=True, env=env)


def run_capture(command: list[str], *, cwd: Path = REPO_ROOT) -> str:
    printable = " ".join(command)
    env = os.environ.copy()
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    env["UV_LINK_MODE"] = "copy"
    print(f"$ {printable}", flush=True)
    completed = subprocess.run(command, cwd=cwd, check=True, env=env, text=True, capture_output=True)
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    return completed.stdout


def venv_python() -> Path:
    if os.name == "nt":
        return VENV_ROOT / "Scripts" / "python.exe"
    return VENV_ROOT / "bin" / "python"


def venv_cli() -> Path:
    if os.name == "nt":
        return VENV_ROOT / "Scripts" / "proofkit.exe"
    return VENV_ROOT / "bin" / "proofkit"


def npm_command() -> str | None:
    return shutil.which("npm")


def node_command() -> str | None:
    return shutil.which("node")


def uv_command() -> str | None:
    return shutil.which("uv")


def create_virtualenv() -> None:
    try:
        run([sys.executable, "-m", "venv", str(VENV_ROOT)])
        return
    except subprocess.CalledProcessError:
        uv = uv_command()
        if uv is None:
            raise

    if VENV_ROOT.exists():
        shutil.rmtree(VENV_ROOT)
    run([uv, "venv", "--seed", str(VENV_ROOT), "--python", sys.executable])


def read_project_version() -> str:
    metadata = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(metadata["project"]["version"])


def read_package_version() -> str:
    import json

    metadata = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    return str(metadata["version"])


def read_cli_version() -> str:
    text = (REPO_ROOT / "proofkit" / "_types.py").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith(VERSION_PREFIX):
            return line.split('"', 2)[1]
    raise AssertionError("proofkit._types VERSION was not found")


def verify_versions() -> str:
    pyproject_version = read_project_version()
    package_version = read_package_version()
    cli_version = read_cli_version()
    versions = {
        "pyproject.toml": pyproject_version,
        "package.json": package_version,
        "proofkit/_types.py": cli_version,
    }

    if len(set(versions.values())) != 1:
        details = ", ".join(f"{source}={version}" for source, version in versions.items())
        raise AssertionError(f"version mismatch: {details}")

    tag_name = os.environ.get("GITHUB_REF_NAME", "")
    ref_type = os.environ.get("GITHUB_REF_TYPE", "")
    if ref_type == "tag" or tag_name.startswith("v"):
        expected_tag = f"v{pyproject_version}"
        if tag_name != expected_tag:
            raise AssertionError(f"tag {tag_name!r} does not match package version {expected_tag!r}")

    print(f"Version check passed: {pyproject_version}", flush=True)
    return pyproject_version


def clean_temp() -> None:
    if TEMP_ROOT.exists():
        shutil.rmtree(TEMP_ROOT)


def release_check(*, keep_temp: bool) -> None:
    clean_temp()
    TEMP_ROOT.mkdir(parents=True)

    try:
        verify_versions()
        run(
            [
                sys.executable,
                "-m",
                "py_compile",
                "scripts/sdd.py",
                "proofkit/cli.py",
                "proofkit/_types.py",
                "proofkit/__init__.py",
                "proofkit/__main__.py",
                "tests/test_sdd.py",
                "scripts/release_check.py",
            ]
        )
        run([sys.executable, "-m", "unittest", "tests/test_sdd.py"])
        run([sys.executable, "scripts/sdd.py", "validate"])
        run([sys.executable, "scripts/sdd.py", "status"])
        run([sys.executable, "-m", "proofkit", "version"])

        create_virtualenv()

        run([str(venv_python()), "-m", "pip", "install", ".", "--dry-run"])
        run([str(venv_python()), "-m", "pip", "install", "."])
        run([str(venv_cli()), "version"])
        run([str(venv_cli()), "init", "--root", str(SMOKE_ROOT)])
        run([str(venv_cli()), "validate", "--root", str(SMOKE_ROOT)])
        run([str(venv_cli()), "run", "release-gate", "--profile", "standard", "--title", "Release gate", "--root", str(SMOKE_ROOT)])
        run([str(venv_cli()), "guard", "--root", str(SMOKE_ROOT), "--require-active-change", "--strict-state"])
        (SMOKE_ROOT / ".git").mkdir()
        run([str(venv_cli()), "install-hooks", "--root", str(SMOKE_ROOT)])

        for adapter in ["codex", "claude-code", "gemini-cli", "opencode", "qwen-code", "generic-markdown"]:
            adapter_path = SMOKE_ROOT / ".proofkit" / "adapters" / f"{adapter}.json"
            if not adapter_path.is_file():
                raise AssertionError(f"packaged adapter was not initialized: {adapter_path}")
        workflow_proposal = SMOKE_ROOT / ".proofkit" / "changes" / "release-gate" / "proposal.md"
        if not workflow_proposal.is_file():
            raise AssertionError(f"installed CLI did not create workflow change: {workflow_proposal}")

        readiness_doc = SMOKE_ROOT / "docs" / "production-readiness-v0.1.md"
        adapters_doc = SMOKE_ROOT / "docs" / "adapters-v0.1.md"
        if not readiness_doc.is_file():
            raise AssertionError(f"packaged readiness doc was not initialized: {readiness_doc}")
        if not adapters_doc.is_file():
            raise AssertionError(f"packaged adapters doc was not initialized: {adapters_doc}")

        npm = npm_command()
        node = node_command()
        if npm is None or node is None:
            print("npm wrapper check skipped: npm and node are not both available on PATH.")
        else:
            NPM_PACK_ROOT.mkdir(parents=True)
            NPM_PROJECT_ROOT.mkdir(parents=True)
            pack_output = run_capture([npm, "pack", "--pack-destination", str(NPM_PACK_ROOT)])
            tarball_name = pack_output.strip().splitlines()[-1]
            tarball_path = NPM_PACK_ROOT / tarball_name
            if not tarball_path.is_file():
                raise AssertionError(f"npm pack did not create tarball: {tarball_path}")
            with tarfile.open(tarball_path, "r:gz") as package:
                names = package.getnames()
                forbidden = [name for name in names if "__pycache__" in name or name.endswith(".pyc") or name.startswith("package/docs/superpowers/")]
                if forbidden:
                    raise AssertionError(f"npm package contains non-product files: {forbidden}")

            run([npm, "install", str(tarball_path), "--prefix", str(NPM_PROJECT_ROOT)])
            npm_launcher = NPM_PROJECT_ROOT / "node_modules" / "proofkit-cli" / "bin" / "proofkit.js"
            run([node, str(npm_launcher), "version"])
            run([node, str(npm_launcher), "init", "--root", str(NPM_SMOKE_ROOT)])
            run([node, str(npm_launcher), "validate", "--root", str(NPM_SMOKE_ROOT)])
            run([node, str(npm_launcher), "init", "--root", str(NPM_RELATIVE_SMOKE_ROOT)], cwd=NPM_PROJECT_ROOT)
            run([node, str(npm_launcher), "validate", "--root", str(NPM_RELATIVE_SMOKE_ROOT)], cwd=NPM_PROJECT_ROOT)
            run(
                [
                    node,
                    str(npm_launcher),
                    "run",
                    "npm-release-gate",
                    "--profile",
                    "standard",
                    "--title",
                    "npm release gate",
                    "--root",
                    str(NPM_RELATIVE_SMOKE_ROOT),
                ],
                cwd=NPM_PROJECT_ROOT,
            )
            run(
                [node, str(npm_launcher), "guard", "--root", str(NPM_RELATIVE_SMOKE_ROOT), "--require-active-change", "--strict-state"],
                cwd=NPM_PROJECT_ROOT,
            )
            (NPM_PROJECT_ROOT / NPM_RELATIVE_SMOKE_ROOT / ".git").mkdir()
            run([node, str(npm_launcher), "install-hooks", "--root", str(NPM_RELATIVE_SMOKE_ROOT)], cwd=NPM_PROJECT_ROOT)

            npm_adapter = NPM_SMOKE_ROOT / ".proofkit" / "adapters" / "codex.json"
            if not npm_adapter.is_file():
                raise AssertionError(f"npm wrapper did not initialize packaged adapters: {npm_adapter}")
            relative_npm_adapter = NPM_PROJECT_ROOT / NPM_RELATIVE_SMOKE_ROOT / ".proofkit" / "adapters" / "codex.json"
            if not relative_npm_adapter.is_file():
                raise AssertionError(f"npm wrapper did not resolve relative roots from caller cwd: {relative_npm_adapter}")
            relative_npm_proposal = (
                NPM_PROJECT_ROOT / NPM_RELATIVE_SMOKE_ROOT / ".proofkit" / "changes" / "npm-release-gate" / "proposal.md"
            )
            if not relative_npm_proposal.is_file():
                raise AssertionError(f"npm wrapper did not create workflow change from caller cwd: {relative_npm_proposal}")

        print("Release check passed.")
    finally:
        if not keep_temp:
            clean_temp()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run ProofKit release readiness checks.")
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
