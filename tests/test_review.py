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
