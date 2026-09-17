"""The scheduling maths.

This is where being wrong is silent: a mis-ordered queue still looks like a queue, and a box
that advances on a miss still shows a plausible due date. Nothing else in the tool fails this
quietly.
"""
from __future__ import annotations

import datetime as dt

import pytest


@pytest.fixture
def row(rc, repo, deck_factory, card):
    """One queue row, which is what a session is made of."""
    def make(box: int = 1, **card_fields):
        repo.write("a.py", "x = 1\n")
        repo.commit("init")
        c = card("c1", anchor="a.py", **card_fields)
        entry = deck_factory(repo, [c])
        state = {"c1": {"box": box, "due": rc.today().isoformat(), "seen": 1, "lapses": 0}}
        deck, cards = rc.load_deck(entry)
        return [(entry, cards[0], state, deck, ({}, 0.0))]
    return make


def test_a_right_answer_advances_one_box(rc, row):
    queue = row(box=2)
    rc.finish_session(queue, {0: "y"})
    assert queue[0][2]["c1"]["box"] == 3


def test_box_five_is_known_not_finished(rc, row):
    queue = row(box=5)
    rc.finish_session(queue, {0: "y"})
    assert queue[0][2]["c1"]["box"] == rc.MAX_BOX


def test_a_miss_returns_to_box_one_not_back_one_step(rc, row):
    queue = row(box=4)
    rc.finish_session(queue, {0: "n"})
    cs = queue[0][2]["c1"]
    assert cs["box"] == 1
    assert cs["lapses"] == 1


@pytest.mark.parametrize("box,days", [(1, 1), (2, 2), (3, 4), (4, 8), (5, 16)])
def test_due_dates_follow_the_intervals(rc, row, box, days):
    queue = row(box=box - 1 if box > 1 else 1)
    rc.finish_session(queue, {0: "y" if box > 1 else "n"})
    cs = queue[0][2]["c1"]
    assert cs["due"] == (rc.today() + dt.timedelta(days=rc.INTERVALS[cs["box"]])).isoformat()
    assert rc.INTERVALS[box] == days


def test_a_flag_is_saved_even_on_a_card_never_graded(rc, row):
    """save_state drops unseen cards, and a flag can be raised in learn mode on one."""
    queue = row()
    entry, _c, state, _d, _ch = queue[0]
    state["never-seen"] = {"box": 1, "due": rc.today().isoformat(), "seen": 0,
                           "lapses": 0, "flagged": rc.today().isoformat()}
    rc.finish_session(queue, {}, {entry["name"]: state})
    assert "never-seen" in rc.load_state(entry["name"])


def test_an_unseen_card_with_no_flag_is_not_written(rc, row):
    queue = row()
    entry, _c, state, _d, _ch = queue[0]
    state["never-seen"] = {"box": 1, "due": rc.today().isoformat(), "seen": 0, "lapses": 0}
    rc.finish_session(queue, {}, {entry["name"]: state})
    assert "never-seen" not in rc.load_state(entry["name"])


def _score(rc, monkeypatch, card, cs, deck=None):
    # Jitter is deliberately wider than the tier gap, so it has to be pinned to compare two
    # cards at all. A constant cancels out: it is added to both sides.
    monkeypatch.setattr(rc.random, "random", lambda: 0.5)
    return rc.order_score(card, deck or {}, cs)


def test_priority_orders_a_capped_session(rc, monkeypatch, card):
    due = {"box": 1, "due": rc.today().isoformat()}
    first = _score(rc, monkeypatch, card("a", priority=1), due)
    last = _score(rc, monkeypatch, card("b", priority=3), due)
    assert first < last


def test_neglect_eventually_beats_priority(rc, monkeypatch, card):
    """The starvation guard. Without it the tail of a large deck is never seen at all."""
    today = rc.today()
    fresh = _score(rc, monkeypatch, card("a", priority=1), {"box": 1, "due": today.isoformat()})
    stale = _score(rc, monkeypatch, card("b", priority=3),
                   {"box": 1, "due": (today - dt.timedelta(days=90)).isoformat()})
    assert stale < fresh


def test_neglect_takes_weeks_not_days_to_overtake_a_tier(rc, monkeypatch, card):
    """A gentle slope, or the weighting is flattened and priority stops meaning anything."""
    today = rc.today()
    fresh = _score(rc, monkeypatch, card("a", priority=1), {"box": 1, "due": today.isoformat()})
    yesterday = _score(rc, monkeypatch, card("b", priority=3),
                       {"box": 1, "due": (today - dt.timedelta(days=1)).isoformat()})
    assert yesterday > fresh


def test_overdue_bonus_is_capped(rc, monkeypatch, card):
    today = rc.today()
    a = _score(rc, monkeypatch, card("a"), {"box": 1, "due": (today - dt.timedelta(days=200)).isoformat()})
    b = _score(rc, monkeypatch, card("b"), {"box": 1, "due": (today - dt.timedelta(days=900)).isoformat()})
    assert a == b


def test_churn_gives_nothing_away_in_a_repo_that_does_not_move(rc, card):
    """Normalised against the deck's own spread, and floored, or a quiet repo boosts everything."""
    counts = {"a.py": 1, "b.py": 2}
    assert rc.churn_boost(card("c", anchor="a.py"), counts, p90=2.0) == 0.0


def test_churn_boosts_the_anchor_that_is_moving(rc, card):
    counts = {"hot.py": 40, "cold.py": 1}
    p90 = 40.0
    hot = rc.churn_boost(card("c", anchor="hot.py"), counts, p90)
    cold = rc.churn_boost(card("c", anchor="cold.py"), counts, p90)
    assert hot > cold
    assert hot <= rc.CHURN_WEIGHT
