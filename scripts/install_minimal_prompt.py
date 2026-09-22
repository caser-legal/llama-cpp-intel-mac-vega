#!/usr/bin/env python3
import argparse
import pathlib
import subprocess


def install(repo):
    repo = pathlib.Path(repo).expanduser().resolve()
    patch = pathlib.Path(__file__).resolve().parents[1] / "hermes-minimal-prompt.patch"
    for name in ("agent/agent_init.py", "agent/system_prompt.py"):
        if not (repo / name).is_file():
            raise RuntimeError("Hermes source files were not found in the selected installation")
    reverse = subprocess.run(["git", "apply", "--reverse", "--check", str(patch)],
                             cwd=repo, capture_output=True, text=True)
    if reverse.returncode == 0:
        return "already installed"
    check = subprocess.run(["git", "apply", "--check", str(patch)],
                           cwd=repo, capture_output=True, text=True)
    if check.returncode:
        raise RuntimeError("This Hermes version does not match the prompt patch; no source changes were made. "
                           "Review the patch against your installed version.\n" + check.stderr.strip())
    subprocess.run(["git", "apply", str(patch)], cwd=repo, check=True)
    return "installed"


def main():
    parser = argparse.ArgumentParser(description="Install the opt-in lightweight prompt support; never starts Hermes")
    parser.add_argument("--repo", type=pathlib.Path, default=pathlib.Path.home() / ".hermes/hermes-agent")
    args = parser.parse_args()
    print("Lightweight prompt patch:", install(args.repo))


if __name__ == "__main__":
    main()
