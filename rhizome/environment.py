from __future__ import annotations

import subprocess
from pathlib import Path


class Environment:
    """Git-backed environment for the artifact under construction."""

    RHIZOME_DIR = ".rhizome"
    BRANCH = "rhizome"

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._rhizome_dir = self.root / self.RHIZOME_DIR
        self._ensure_git()
        self._rhizome_dir.mkdir(parents=True, exist_ok=True)

    def _ensure_git(self) -> None:
        if not (self.root / ".git").exists():
            self._git("init")
        branches = self._git("branch", "--list", self.BRANCH).strip()
        if not branches:
            # Create the rhizome branch from current HEAD (or orphan if empty)
            try:
                self._git("rev-parse", "HEAD")
                self._git("branch", self.BRANCH)
            except subprocess.CalledProcessError:
                # Empty repo — create orphan branch with initial commit
                self._git("checkout", "--orphan", self.BRANCH)
                self._git("commit", "--allow-empty", "-m", "rhizome: init")
                return
        current = self._git("branch", "--show-current").strip()
        if current != self.BRANCH:
            self._git("checkout", self.BRANCH)

    def _git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout

    def read_file(self, relpath: str) -> str | None:
        p = self.root / relpath
        if p.exists():
            return p.read_text()
        return None

    def write_file(self, relpath: str, content: str) -> None:
        p = self.root / relpath
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)

    def delete_file(self, relpath: str) -> None:
        p = self.root / relpath
        if p.exists():
            p.unlink()

    def list_files(self) -> list[str]:
        output = self._git("ls-files")
        return [line for line in output.strip().splitlines() if line]

    def commit(self, message: str) -> str | None:
        self._git("add", "-A")
        # Check if there's anything to commit
        status = self._git("status", "--porcelain")
        if not status.strip():
            return None
        self._git("commit", "-m", message)
        return self._git("rev-parse", "HEAD").strip()

    def diff(self) -> str:
        return self._git("diff")

    def log(self, n: int = 10) -> str:
        return self._git("log", f"-{n}", "--oneline")

    @property
    def compost_path(self) -> Path:
        return self._rhizome_dir / "compost.json"
