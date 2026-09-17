"""Drift: which cards a range of commits actually puts in doubt.

Over-reporting is the failure that matters here. An update that flags every card on a busy
file is one nobody runs, and the deck then rots for a reason that looks like discipline.
"""
from __future__ import annotations

import datetime as dt
import json

import pytest

# Far enough apart that `git diff -U5` cannot spill one function's context into the other.
MODULE = """\
def alpha():
    return 1
{gap}

def beta():
    return 2
"""
GAP = "\n" * 20


@pytest.fixture
def two_symbols(repo):
    repo.write("src/mod.py", MODULE.format(gap=GAP))
    repo.write("docs/adr-1.md", "ADR-1: alpha is one\n")
    repo.commit("init", days_ago=30)
    return repo


def test_a_commit_to_one_symbol_leaves_the_other_alone(rc, two_symbols, deck_factory, card):
    entry = deck_factory(two_symbols, [card("a", anchor="src/mod.py#alpha"),
                                       card("b", anchor="src/mod.py#beta")])
    two_symbols.write("src/mod.py", MODULE.format(gap=GAP).replace("return 1", "return 111"))
    two_symbols.commit("Change alpha only")

    f = rc.drift_facts(entry)
    assert [c["id"] for c in f["hot"]] == ["a"]
    assert [c["id"] for c in f["cold"]] == ["b"]


def test_a_file_anchor_with_no_symbol_is_always_hot(rc, two_symbols, deck_factory, card):
    entry = deck_factory(two_symbols, [card("a", anchor="src/mod.py")])
    two_symbols.write("src/mod.py", MODULE.format(gap=GAP).replace("return 1", "return 111"))
    two_symbols.commit("Change alpha only")
    assert [c["id"] for c in rc.drift_facts(entry)["hot"]] == ["a"]


def test_a_verified_stamp_narrows_the_range_to_that_card(rc, two_symbols, deck_factory, card):
    """The whole point: a card checked after the commit that touched it is not re-read."""
    entry = deck_factory(two_symbols, [card("a", anchor="src/mod.py#alpha"),
                                       card("b", anchor="src/mod.py#alpha")])
    two_symbols.write("src/mod.py", MODULE.format(gap=GAP).replace("return 1", "return 111"))
    head = two_symbols.commit("Change alpha")

    deck_path = rc.deck_path(entry["name"])
    deck = json.loads(deck_path.read_text())
    deck["cards"][1]["verified"] = head
    deck_path.write_text(json.dumps(deck))

    f = rc.drift_facts(entry)
    assert [c["id"] for c in f["hot"]] == ["a"]
    assert f["verified_skip"] == 1


def test_a_verified_sha_this_repo_never_had_falls_back(rc, two_symbols, deck_factory, card):
    """After a rebase the stamp is meaningless, and silently clearing the card is the wrong
    way to be wrong."""
    entry = deck_factory(two_symbols, [card("a", anchor="src/mod.py#alpha", verified="deadbee")])
    two_symbols.write("src/mod.py", MODULE.format(gap=GAP).replace("return 1", "return 111"))
    two_symbols.commit("Change alpha")
    assert [c["id"] for c in rc.drift_facts(entry)["hot"]] == ["a"]


def test_a_dead_route_is_reported_however_current_the_deck_is(rc, two_symbols, deck_factory, card):
    entry = deck_factory(two_symbols, [card("a", anchor="src/mod.py#alpha",
                                            look={"src/gone.py": "not there"})])
    f = rc.drift_facts(entry)
    assert f["status"] == "up to date"
    assert f["dead"] == [("a", "src/gone.py")]


def test_changed_files_no_card_covers_are_listed(rc, two_symbols, deck_factory, card):
    entry = deck_factory(two_symbols, [card("a", anchor="src/mod.py#alpha")])
    two_symbols.write("src/new.py", "def gamma():\n    return 3\n")
    two_symbols.commit("Add gamma")
    assert rc.drift_facts(entry)["uncovered"] == ["src/new.py"]


def test_flags_and_lapses_reach_the_report(rc, two_symbols, deck_factory, card):
    entry = deck_factory(two_symbols, [card("a", anchor="src/mod.py#alpha"),
                                       card("b", anchor="src/mod.py#beta")])
    rc.save_state(entry["name"], {
        "a": {"box": 1, "due": "2026-01-01", "seen": 1, "lapses": 0, "flagged": "2026-09-17"},
        "b": {"box": 1, "due": "2026-01-01", "seen": 9, "lapses": rc.STICKY_LAPSES},
    })
    f = rc.drift_facts(entry)
    assert [c["id"] for c, _when in f["flagged"]] == ["a"]
    assert [c["id"] for c, _n in f["sticky"]] == ["b"]


class TestCrossRepo:
    """`name::path` refs, which are the only way to card a contract between two services."""

    @pytest.fixture
    def pair(self, rc, tmp_path, deck_factory, card, two_symbols):
        from conftest import Repo
        other = Repo(tmp_path / "other")
        other.write("api/contract.py", MODULE.format(gap=GAP))
        other.commit("init", days_ago=30)
        deck_factory(other, [], name="other")
        entry = deck_factory(two_symbols, [card("a", anchor="other::api/contract.py#alpha")])
        return entry, other

    def test_the_other_repo_moving_makes_a_card_hot(self, rc, pair):
        entry, other = pair
        other.write("api/contract.py", MODULE.format(gap=GAP).replace("return 1", "return 111"))
        other.commit("Change the contract")

        f = rc.drift_facts(entry)
        assert [c["id"] for c in f["hot"]] == ["a"]
        # Nothing has happened in this repo at all, which a sha comparison cannot see.
        assert f["status"] == "linked moved"
        assert f["log"] == ""

    def test_the_other_repo_standing_still_says_nothing(self, rc, pair):
        entry, _other = pair
        f = rc.drift_facts(entry)
        assert f["hot"] == []
        assert f["status"] == "up to date"

    def test_a_ref_to_an_unregistered_repo_is_reported(self, rc, two_symbols, deck_factory, card):
        entry = deck_factory(two_symbols, [card("a", anchor="ghost::api/contract.py")])
        assert rc.drift_facts(entry)["unknown_repo"] == [("a", "ghost::api/contract.py")]

    def test_coverage_ignores_refs_into_other_repos(self, rc, pair):
        """A file in another repo says nothing about whether this repo's changes are carded."""
        entry, _other = pair
        assert rc.local_paths({"anchor": "other::api/contract.py", "look": {"src/mod.py": "x"}},
                              entry["name"]) == ["src/mod.py"]


def test_a_bare_date_is_pinned_to_midnight(rc):
    """git's approxidate reads `2026-09-17` as that date at the current time of day, so an
    unpinned baseline silently loses the commits made earlier the same day."""
    assert rc.since_arg("2026-09-17") == "2026-09-17 00:00:00"


def test_same_day_commits_are_visible_to_a_date_baseline(rc, repo):
    repo.write("a.py", "x = 1\n")
    repo.commit("this morning")
    assert rc.changed_since_date(repo.path, dt.date.today().isoformat()) == {"a.py"}
