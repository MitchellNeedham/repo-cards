"""The session itself: what a keypress does to a card's state.

Driven by replacing the key reader rather than a terminal, so these are tests of the
session's logic and not of raw mode.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def session(rc, repo, deck_factory, card, monkeypatch):
    """Build a one or two card queue and drive it with a scripted set of keys."""
    def run(cards, keys, lines=(), mode="test", state=None):
        repo.write("src/mod.py", "def alpha():\n    return 1\n")
        repo.commit("init")
        entry = deck_factory(repo, cards)
        deck, loaded = rc.load_deck(entry)
        st = state or {}
        queue = [(entry, c, st, deck, ({}, 0.0)) for c in loaded]

        keys_it, lines_it = iter(keys), iter(lines)
        monkeypatch.setattr(rc, "read_key", lambda lower=True: next(keys_it, "q"))
        monkeypatch.setattr(rc, "read_line", lambda label, draw=None: next(lines_it, ""))
        monkeypatch.setattr(rc, "draw_card", lambda *a, **k: None)
        rc.run_session(queue, mode)
        return rc.load_state(entry["name"])
    return run


def test_f_flags_without_grading(rc, session, card):
    state = session([card("a", anchor="src/mod.py#alpha")], ["f", "q"])
    assert state["a"]["flagged"] == rc.today().isoformat()
    assert state["a"]["seen"] == 0


def test_a_flag_carries_the_reason_you_gave(rc, session, card):
    state = session([card("a", anchor="src/mod.py#alpha")], ["f", "q"],
                    lines=["rendered in the worker now"])
    assert state["a"]["flag_note"] == "rendered in the worker now"


def test_an_abandoned_prompt_still_leaves_the_flag(rc, session, card):
    """The flag is the part that matters, so it is raised before the question is asked."""
    state = session([card("a", anchor="src/mod.py#alpha")], ["f", "q"], lines=[""])
    assert state["a"]["flagged"]
    assert "flag_note" not in state["a"]


def test_flagging_twice_clears_the_note_with_the_flag(rc, session, card):
    state = session([card("a", anchor="src/mod.py#alpha")], ["f", "f", "q"], lines=["wrong"])
    assert state == {}


def test_a_flag_raised_in_learn_mode_is_kept(rc, session, card):
    state = session([card("a", anchor="src/mod.py#alpha")], ["f", "q"], mode="learn")
    assert state["a"]["flagged"]


def test_a_regrade_replaces_rather_than_repeats(rc, session, card):
    """Grades are held until the session ends, so going back and changing your mind counts
    once. Grading the last card ends the session, hence the second card."""
    state = session([card("a", anchor="src/mod.py#alpha"), card("b", anchor="src/mod.py#alpha")],
                    ["enter", "y", "left", "n", "q"],
                    state={"a": {"box": 3, "due": "2026-01-01", "seen": 4, "lapses": 0}})
    assert state["a"]["seen"] == 5
    assert state["a"]["box"] == 1
    assert state["a"]["lapses"] == 1


class TestChecking:
    """Marking a typed answer, for the kinds where the answer is short and exact."""

    def test_a_cloze_blank_tolerates_a_typo(self, rc):
        card = {"id": "c", "a": "The ledger is {{authoritative}}."}
        assert rc.check_answer(card, "cloze", ["authoratative"])[0]

    def test_a_cloze_blank_does_not_tolerate_a_different_word(self, rc):
        """Similarity is not correctness: `later` is close to nothing and means everything."""
        card = {"id": "c", "a": "Written {{in the same transaction}}."}
        assert not rc.check_answer(card, "cloze", ["later"])[0]

    def test_every_blank_has_to_be_right(self, rc):
        card = {"id": "c", "a": "The ledger is {{authoritative}}; written {{in one transaction}}."}
        ok, parts = rc.check_answer(card, "cloze", ["authoritative", "whenever"])
        assert not ok
        assert [p[0] for p in parts] == [True, False]

    def test_a_missing_blank_is_not_silently_passed(self, rc):
        card = {"id": "c", "a": "{{one}} and {{two}}."}
        assert not rc.check_answer(card, "cloze", ["one"])[0]

    def test_an_order_is_read_against_what_was_shown(self, rc):
        card = {"id": "o", "kind": "order", "sequence": ["propose", "approve", "publish"], "a": ""}
        rc._SHUFFLE["o"] = ["publish", "propose", "approve"]
        assert rc.check_answer(card, "order", ["2 3 1"])[0]
        assert not rc.check_answer(card, "order", ["1 2 3"])[0]

    def test_an_order_accepts_any_separator(self, rc):
        card = {"id": "o", "kind": "order", "sequence": ["a", "b"], "a": ""}
        rc._SHUFFLE["o"] = ["b", "a"]
        assert rc.check_answer(card, "order", ["2,1"])[0]

    def test_a_shuffle_holds_still_while_the_card_is_redrawn(self, rc):
        """The card is redrawn on every keypress, and numbers mean nothing if it moves."""
        card = {"id": "o", "sequence": list("abcdefgh")}
        assert rc.shuffled_steps(card) == rc.shuffled_steps(card)

    def test_locate_accepts_a_basename(self, rc):
        card = {"id": "l", "look": {"src/billing/outbox.py#enqueue": "the writer",
                                    "docs/adr/adr-7.md": "the decision"}}
        assert rc.check_answer(card, "locate", ["outbox.py adr-7.md"])[0]

    def test_locate_wants_every_route(self, rc):
        card = {"id": "l", "look": {"src/billing/outbox.py": "the writer",
                                    "docs/adr/adr-7.md": "the decision"}}
        ok, parts = rc.check_answer(card, "locate", ["outbox.py"])
        assert not ok
        assert [p[0] for p in parts] == [True, False]


class TestTypedGrading:
    """`t` in a session: typed, marked, and overridable."""

    CLOZE = {"kind": "cloze", "a": "The ledger is {{authoritative}}."}

    def test_a_right_answer_advances_the_box(self, rc, session, card):
        state = session([card("a", anchor="src/mod.py#alpha", **self.CLOZE)],
                        ["t", "q"], lines=["authoritative"],
                        state={"a": {"box": 2, "due": "2026-01-01", "seen": 1, "lapses": 0}})
        assert state["a"]["box"] == 3

    def test_a_wrong_answer_returns_it_to_box_one(self, rc, session, card):
        state = session([card("a", anchor="src/mod.py#alpha", **self.CLOZE)],
                        ["t", "q"], lines=["whatever"],
                        state={"a": {"box": 4, "due": "2026-01-01", "seen": 1, "lapses": 0}})
        assert state["a"]["box"] == 1
        assert state["a"]["lapses"] == 1

    def test_you_can_override_the_mark(self, rc, session, card):
        """The mark is a fact about the words, not about whether you knew it."""
        state = session([card("a", anchor="src/mod.py#alpha", **self.CLOZE),
                         card("b", anchor="src/mod.py#alpha")],
                        ["t", "y", "q"], lines=["not the word"],
                        state={"a": {"box": 2, "due": "2026-01-01", "seen": 1, "lapses": 0}})
        assert state["a"]["box"] == 3
        assert state["a"]["lapses"] == 0

    def test_typing_is_not_offered_in_learn_mode(self, rc, session, card):
        state = session([card("a", anchor="src/mod.py#alpha", **self.CLOZE)],
                        ["t", "q"], lines=["authoritative"], mode="learn")
        assert state == {}
