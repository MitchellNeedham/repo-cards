"""Catchup and the computed topics, which both turn git history into a reading order."""
from __future__ import annotations

import argparse
import datetime as dt

import pytest


@pytest.fixture
def worked_on(repo):
    repo.write("src/mod.py", "def alpha():\n    return 1\n")
    repo.write("src/other.py", "def beta():\n    return 2\n")
    repo.commit("init", days_ago=40)
    return repo


def test_commits_carry_their_files_and_subjects(rc, worked_on):
    worked_on.write("src/mod.py", "def alpha():\n    return 111\n")
    worked_on.commit("Bump alpha: it was wrong")
    commits = rc.commits_since(worked_on.path, (rc.today() - dt.timedelta(days=1)).isoformat())
    assert [c[2] for c in commits] == ["Bump alpha: it was wrong"]
    assert commits[0][3] == {"src/mod.py"}


def test_a_filename_of_digits_is_not_read_as_a_header(rc, worked_on):
    """The parser splits on NUL for exactly this reason: a path can look like anything."""
    worked_on.write("1234567890", "data\n")
    worked_on.commit("Add a numeric filename")
    commits = rc.commits_since(worked_on.path, (rc.today() - dt.timedelta(days=1)).isoformat())
    assert commits[0][3] == {"1234567890"}
    assert commits[0][2] == "Add a numeric filename"


def test_commits_come_back_newest_first(rc, worked_on):
    worked_on.write("src/mod.py", "def alpha():\n    return 2\n")
    worked_on.commit("older", days_ago=3)
    worked_on.write("src/mod.py", "def alpha():\n    return 3\n")
    worked_on.commit("newer", days_ago=1)
    commits = rc.commits_since(worked_on.path, (rc.today() - dt.timedelta(days=5)).isoformat())
    assert [c[2] for c in commits][:2] == ["newer", "older"]


def test_catchup_measures_from_your_last_review(rc, worked_on, deck_factory, card, capsys):
    entry = deck_factory(worked_on, [card("a", anchor="src/mod.py#alpha")])
    rc.save_state(entry["name"], {"a": {"box": 2, "due": "2026-10-01", "seen": 1, "lapses": 0,
                                        "last_seen": (rc.today() - dt.timedelta(days=5)).isoformat()}})
    # In order: git prunes traversal at a commit older than the cutoff, so a history whose
    # dates run backwards hides its own parents.
    worked_on.write("src/mod.py", "def alpha():\n    return 0\n")
    worked_on.commit("Before your last session", days_ago=9)
    worked_on.write("src/mod.py", "def alpha():\n    return 111\n")
    worked_on.commit("Bump alpha", days_ago=2)

    rc.cmd_catchup(argparse.Namespace(repo=entry["name"], since=None, full=False))
    out = capsys.readouterr().out
    assert "Bump alpha" in out
    assert "Before your last session" not in out
    assert "5 day(s) ago" in out


def test_catchup_writes_no_state(rc, worked_on, deck_factory, card, capsys):
    entry = deck_factory(worked_on, [card("a", anchor="src/mod.py#alpha")])
    worked_on.write("src/mod.py", "def alpha():\n    return 111\n")
    worked_on.commit("Bump alpha")
    rc.cmd_catchup(argparse.Namespace(repo=entry["name"], since=None, full=False))
    assert not rc.state_file(entry["name"]).exists()


def test_catchup_separates_commits_no_card_covers(rc, worked_on, deck_factory, card, capsys):
    entry = deck_factory(worked_on, [card("a", anchor="src/mod.py#alpha")])
    worked_on.write("src/elsewhere.py", "def gamma():\n    return 3\n")
    worked_on.commit("Work nobody has carded")
    rc.cmd_catchup(argparse.Namespace(repo=entry["name"], since=None, full=False))
    out = capsys.readouterr().out
    assert "touching nothing carded" in out
    assert "Work nobody has carded" in out


def test_computed_topics_are_built_from_history(rc, worked_on, deck_factory, card):
    entry = deck_factory(worked_on, [card("a", anchor="src/mod.py#alpha"),
                                     card("b", anchor="src/other.py#beta"),
                                     card("c", anchor="src/other.py#beta"),
                                     card("d", anchor="src/other.py#beta"),
                                     card("e", anchor="src/other.py#beta")])
    worked_on.write("src/mod.py", "def alpha():\n    return 111\n")
    worked_on.commit("Bump alpha", days_ago=2)
    deck, _cards = rc.load_deck(entry)
    assert rc.all_topics(deck)["last-week"]["cards"] == ["a"]


def test_a_window_covering_the_whole_deck_is_not_a_filter(rc, worked_on, deck_factory, card):
    """A big refactor touches everything, and a topic that selects everything teaches nothing."""
    entry = deck_factory(worked_on, [card("a", anchor="src/mod.py#alpha"),
                                     card("b", anchor="src/other.py#beta")])
    worked_on.write("src/mod.py", "def alpha():\n    return 111\n")
    worked_on.write("src/other.py", "def beta():\n    return 222\n")
    worked_on.commit("Reformat everything", days_ago=1)
    deck, _cards = rc.load_deck(entry)
    assert "last-week" not in rc.all_topics(deck)
