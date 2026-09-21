"""The deck's own rules, which `check` exists to enforce rather than describe."""
from __future__ import annotations

import argparse
import json

import pytest


@pytest.fixture
def checker(rc, repo, deck_factory):
    repo.write("src/mod.py", "def alpha():\n    return 1\n")
    repo.write("docs/adr-1.md", "ADR-1\n")
    repo.write("tests/test_mod.py", "def test_alpha():\n    pass\n")
    repo.commit("init")

    def run(cards, **deck_fields):
        entry = deck_factory(repo, cards, **deck_fields)
        deck, loaded = rc.load_deck(entry)
        return {(lvl, msg.split(":")[0].split(",")[0]) for lvl, _scope, msg in
                rc.check_deck(entry, deck, loaded)}, rc.check_deck(entry, deck, loaded)
    return run


@pytest.fixture
def good(card):
    return card("alpha-is-one", anchor="src/mod.py#alpha", level="orientation",
                look={"src/mod.py#alpha": "the implementation",
                      "docs/adr-1.md": "the decision, and what it rejected"},
                q="Why is alpha one, and what breaks if it is not?",
                a="Because the protocol pins it.")


def levels(found, level):
    return [msg for lvl, _scope, msg in found if lvl == level]


def test_a_good_card_is_clean(checker, good):
    _summary, found = checker([good])
    assert found == []


class TestTheMixAndTheLength:
    """What the deck asks of a newcomer, and how much of it it says at once."""

    def test_an_unknown_level_is_an_error(self, checker, good):
        _s, found = checker([{**good, "level": "advanced"}])
        assert any("is not one of" in m for m in levels(found, "error"))

    def test_a_deck_that_declares_no_level_is_warned_once(self, checker, good):
        _s, found = checker([{k: v for k, v in good.items() if k != "level"}])
        assert [m for m in levels(found, "warn") if "declares a `level`" in m]

    def test_too_little_orientation_is_warned(self, checker, good):
        cards = [{**good, "id": f"c{n}", "level": "deep"} for n in range(4)] + [good]
        _s, found = checker(cards)
        assert any("20% of cards are `orientation`" in m for m in levels(found, "warn"))

    def test_half_orientation_passes(self, checker, good):
        cards = [{**good, "id": f"c{n}", "level": "deep"} for n in range(2)]
        cards += [{**good, "id": f"o{n}"} for n in range(2)]
        _s, found = checker(cards)
        assert not [m for m in levels(found, "warn") if "orientation" in m]

    def test_an_answer_that_became_a_paragraph_is_warned(self, checker, good):
        long_answer = "The ledger is authoritative and the projection is derived from it. " * 4
        _s, found = checker([{**good, "a": long_answer}])
        assert any("against a target of 100" in m for m in levels(found, "warn"))

    def test_a_short_answer_is_not_warned(self, checker, good):
        _s, found = checker([good])
        assert not [m for m in levels(found, "warn") if "target of 100" in m]


def test_duplicate_ids_are_an_error(checker, good):
    _s, found = checker([good, dict(good)])
    assert any("duplicate id" in m for m in levels(found, "error"))


def test_a_missing_anchor_is_an_error(checker, good):
    card = {k: v for k, v in good.items() if k != "anchor"}
    _s, found = checker([card])
    assert any("no `anchor`" in m for m in levels(found, "error"))


def test_a_route_that_does_not_exist_is_an_error(checker, good):
    _s, found = checker([{**good, "look": {**good["look"], "src/gone.py": "nowhere"}}])
    assert any("path does not exist" in m for m in levels(found, "error"))


def test_a_topic_naming_a_missing_card_is_an_error(checker, good):
    _s, found = checker([good], topics={"orientation": {"description": "d", "cards": ["ghost"]}})
    assert any("not in the deck" in m for m in levels(found, "error"))


def test_cloze_without_blanks_is_an_error(checker, good):
    _s, found = checker([{**good, "kind": "cloze"}])
    assert any("marks no {{blanks}}" in m for m in levels(found, "error"))


def test_order_without_a_sequence_is_an_error(checker, good):
    _s, found = checker([{**good, "kind": "order"}])
    assert any("`sequence`" in m for m in levels(found, "error"))


def test_a_yes_or_no_question_is_a_warning(checker, good):
    _s, found = checker([{**good, "q": "Is alpha one?"}])
    assert any("yes or no" in m for m in levels(found, "warn"))


def test_an_answer_of_five_sentences_is_a_warning(checker, good):
    _s, found = checker([{**good, "a": "One. Two. Three. Four. Five."}])
    assert any("sentences" in m for m in levels(found, "warn"))


def test_an_anchor_with_no_symbol_is_a_warning(checker, good):
    _s, found = checker([{**good, "anchor": "src/mod.py"}])
    assert any("#symbol" in m for m in levels(found, "warn"))


def test_an_anchor_into_prose_needs_no_symbol(checker, good):
    _s, found = checker([{**good, "anchor": "docs/adr-1.md"}])
    assert not any("#symbol" in m for m in levels(found, "warn"))


def test_one_route_is_a_warning(checker, good):
    _s, found = checker([{**good, "look": {"src/mod.py#alpha": "the implementation"}}])
    assert any("fewer than two" in m for m in levels(found, "warn"))


def test_routes_all_in_one_directory_are_a_warning(checker, good):
    _s, found = checker([{**good, "look": {"src/mod.py#alpha": "one", "src/mod.py": "two"}}])
    assert any("one directory" in m for m in levels(found, "warn"))


def test_a_non_kebab_id_is_a_warning(checker, good):
    _s, found = checker([{**good, "id": "Alpha_Is_One"}])
    assert any("kebab" in m for m in levels(found, "warn"))


class TestOrphanedState:
    """What a regenerate costs when an id is reworded, and how it is handed back."""

    @pytest.fixture
    def regenerated(self, rc, repo, deck_factory, card):
        repo.write("src/mod.py", "def alpha():\n    return 1\n")
        repo.commit("init")
        entry = deck_factory(repo, [card("alpha-is-one", anchor="src/mod.py#alpha")])
        rc.save_state("repo", {"alpha-is-one": {"box": 4, "due": "2026-10-01", "seen": 7, "lapses": 1},
                               "long-retired": {"box": 2, "due": "2026-10-01", "seen": 3, "lapses": 0}})
        # The regenerate: same fact, reworded id.
        path = rc.deck_path("repo")
        deck = json.loads(path.read_text())
        deck["cards"][0]["id"] = "alpha-is-always-one"
        path.write_text(json.dumps(deck))
        return entry

    def test_a_reworded_id_is_matched_to_its_history(self, rc, regenerated):
        _deck, cards = rc.load_deck(regenerated)
        orphans = rc.orphan_state(cards, rc.load_state("repo"))
        by_id = {cid: (match, ratio) for cid, _cs, match, ratio in orphans}
        assert by_id["alpha-is-one"][0] == "alpha-is-always-one"

    def test_a_genuinely_retired_card_is_matched_to_nothing(self, rc, regenerated):
        _deck, cards = rc.load_deck(regenerated)
        orphans = dict((cid, match) for cid, _cs, match, _r in rc.orphan_state(cards, rc.load_state("repo")))
        assert orphans["long-retired"] == ""

    def test_adopt_moves_the_box_across(self, rc, regenerated):
        args = argparse.Namespace(repo="repo", path="alpha-is-one=alpha-is-always-one")
        assert rc.cmd_adopt(args) == 0
        state = rc.load_state("repo")
        assert state["alpha-is-always-one"]["box"] == 4
        assert "alpha-is-one" not in state

    def test_adopt_refuses_to_overwrite_a_live_history(self, rc, regenerated):
        rc.save_state("repo", {**rc.load_state("repo"),
                               "alpha-is-always-one": {"box": 1, "due": "2026-10-01", "seen": 1, "lapses": 0}})
        args = argparse.Namespace(repo="repo", path="alpha-is-one=alpha-is-always-one")
        assert rc.cmd_adopt(args) == 1
        assert rc.load_state("repo")["alpha-is-always-one"]["box"] == 1


def test_check_exits_one_on_an_error(rc, repo, deck_factory, card, capsys):
    repo.write("src/mod.py", "def alpha():\n    return 1\n")
    repo.commit("init")
    deck_factory(repo, [card("a", anchor="src/gone.py")])
    args = argparse.Namespace(repo="repo", errors_only=False, strict=False)
    assert rc.cmd_check(args) == 1


def test_check_exits_zero_on_warnings_alone(rc, repo, deck_factory, card):
    repo.write("src/mod.py", "def alpha():\n    return 1\n")
    repo.commit("init")
    deck_factory(repo, [card("a", anchor="src/mod.py")])   # no symbol: a warning, not an error
    args = argparse.Namespace(repo="repo", errors_only=False, strict=False)
    assert rc.cmd_check(args) == 0
    assert rc.cmd_check(argparse.Namespace(repo="repo", errors_only=False, strict=True)) == 1
