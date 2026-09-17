"""Fixtures for the repo-cards suite.

The script has no `.py` extension and a uv shebang, so it is loaded by path rather than
imported. It is loaded once and its module-level caches are cleared between tests, which is
the only shared state it keeps.
"""
from __future__ import annotations

import datetime as dt
import importlib.machinery
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "bin" / "repo-cards"

_CACHES = ("_CHURN_CACHE", "_TOUCH_CACHE", "_CHANGED", "_CHANGED_SINCE", "_SHA_DATE")


@pytest.fixture(scope="session")
def _module():
    loader = importlib.machinery.SourceFileLoader("repo_cards", str(SCRIPT))
    spec = importlib.util.spec_from_loader("repo_cards", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


@pytest.fixture
def rc(_module, tmp_path, monkeypatch):
    """The module, pointed at a throwaway data home with its caches cleared."""
    monkeypatch.setenv("REPO_CARDS_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    _module._ROOTS = None
    for name in _CACHES:
        getattr(_module, name).clear()
    return _module


class Repo:
    """A throwaway git repo, with backdating, because half of drift is a date range."""

    def __init__(self, path: Path):
        self.path = path
        path.mkdir(parents=True, exist_ok=True)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test")

    def git(self, *args: str) -> str:
        return subprocess.run(["git", "-C", str(self.path), *args],
                              capture_output=True, text=True, check=True).stdout.strip()

    def write(self, rel: str, text: str) -> None:
        target = self.path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def commit(self, message: str, days_ago: int = 0) -> str:
        when = (dt.datetime.now() - dt.timedelta(days=days_ago)).isoformat()
        self.git("add", "-A")
        subprocess.run(["git", "-C", str(self.path), "commit", "-q", "-m", message],
                       check=True, capture_output=True,
                       env={"PATH": "/usr/bin:/bin", "HOME": str(self.path),
                            "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.com",
                            "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.com",
                            "GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when})
        return self.head()

    def merge(self, branch: str, message: str, days_ago: int = 0) -> str:
        """Land a branch the way a merge request does: a merge commit dated now, over work
        dated whenever it was done."""
        when = (dt.datetime.now() - dt.timedelta(days=days_ago)).isoformat()
        subprocess.run(["git", "-C", str(self.path), "merge", "--no-ff", "-q", "-m", message, branch],
                       check=True, capture_output=True,
                       env={"PATH": "/usr/bin:/bin", "HOME": str(self.path),
                            "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.com",
                            "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.com",
                            "GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when})
        return self.head()

    def head(self) -> str:
        return self.git("rev-parse", "--short", "HEAD")


@pytest.fixture
def repo(tmp_path):
    return Repo(tmp_path / "repo")


@pytest.fixture
def deck_factory(rc, tmp_path):
    """Register a repo and write it a deck, the way generate would."""
    def make(repo: Repo, cards: list[dict], name: str = "repo", **deck_fields) -> dict:
        registry = rc.registry_path()
        registry.parent.mkdir(parents=True, exist_ok=True)
        existing = json.loads(registry.read_text())["repos"] if registry.exists() else []
        existing = [r for r in existing if r["name"] != name] + [{"name": name, "root": str(repo.path)}]
        registry.write_text(json.dumps({"repos": sorted(existing, key=lambda r: r["name"])}) + "\n")
        rc._ROOTS = None

        deck = {"repo": name, "description": "test", "last_update_sha": repo.head(),
                "last_update_date": dt.date.today().isoformat(), "cards": cards, **deck_fields}
        path = rc.deck_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(deck))   # JSON is valid YAML, and it round-trips exactly
        return {"name": name, "root": str(repo.path)}
    return make


@pytest.fixture
def card():
    def make(cid: str, **fields) -> dict:
        return {"id": cid, "tags": ["t"], "q": f"Why {cid}?", "a": "Because.", **fields}
    return make
