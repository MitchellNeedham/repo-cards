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


class TestMergeWorkflow:
    """Work that lands through a merge request, which is most work on most teams.

    A merge commit lists no files of its own, and the branch's commits are dated when the
    work was done rather than when it landed. Read plainly, a week of merged branches looks
    like a week in which nothing was touched.
    """

    @pytest.fixture
    def merged(self, worked_on):
        worked_on.git("checkout", "-q", "-b", "feature")
        worked_on.write("src/mod.py", "def alpha():\n    return 111\n")
        # A file that exists nowhere else, so churn cannot find it via an earlier commit.
        worked_on.write("src/feature.py", "def gamma():\n    return 3\n")
        # Older than the churn window, so every assertion below is about the merge
        # carrying the work rather than about the branch commit being found on its own.
        worked_on.commit("Work done long before it landed", days_ago=200)
        worked_on.git("checkout", "-q", "main")
        worked_on.merge("feature", "Merge branch 'feature'", days_ago=1)
        return worked_on

    def test_a_merge_carries_the_files_it_brought_in(self, rc, merged):
        commits = rc.commits_since(merged.path, (rc.today() - dt.timedelta(days=3)).isoformat())
        assert any("src/mod.py" in c[3] for c in commits)

    def test_the_changed_set_sees_merged_work(self, rc, merged):
        since = (rc.today() - dt.timedelta(days=3)).isoformat()
        assert "src/mod.py" in rc.changed_since_date(merged.path, since)

    def test_computed_topics_see_merged_work(self, rc, merged, deck_factory, card):
        entry = deck_factory(merged, [card("a", anchor="src/mod.py#alpha"),
                                      card("b", anchor="src/other.py#beta"),
                                      card("c", anchor="src/other.py#beta"),
                                      card("d", anchor="src/other.py#beta")])
        deck, _cards = rc.load_deck(entry)
        assert rc.all_topics(deck)["last-week"]["cards"] == ["a"]

    def test_churn_counts_merged_work(self, rc, merged):
        assert rc.repo_churn(merged.path).get("src/feature.py", 0) >= 1
