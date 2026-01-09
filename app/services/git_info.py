import os
import subprocess
from datetime import datetime
from typing import Tuple

GIT_DIR_ENV = "HYDROX_GIT_DIR"


def _run_git(args: list[str]) -> str:
    git_dir = os.getenv(GIT_DIR_ENV)
    cmd = ["git"]
    env = os.environ.copy()
    if git_dir:
        cmd.extend(["--git-dir", git_dir])
    cmd.extend(args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def get_git_status() -> Tuple[str, str]:
    branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    commit_date = _run_git(["show", "-s", "--format=%cI", "HEAD"])
    if commit_date:
        try:
            commit_date = datetime.fromisoformat(commit_date.replace("Z", "+00:00")).isoformat()
        except ValueError:
            pass
    return (branch or "unknown"), (commit_date or "unknown")
