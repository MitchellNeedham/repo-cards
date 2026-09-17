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


class TestOverlapHint:
    """Prose is measured, never marked."""

    ANSWER = "The ledger is authoritative; the projection is written in the same transaction."

    def test_the_same_words_score_full(self, rc):
        assert rc.word_overlap(self.ANSWER, self.ANSWER) == 1.0

    def test_nothing_in_common_scores_zero(self, rc):
        assert rc.word_overlap("no idea at all", self.ANSWER) == 0.0

    def test_a_crude_stem_lets_versions_meet_versioned(self, rc):
        assert rc.word_overlap("versions", "the handshake is versioned") > 0

    def test_filler_words_do_not_flatter_an_answer(self, rc):
        assert rc.word_overlap("it is the and of in on at for", self.ANSWER) == 0.0

    def test_saying_more_than_the_card_is_not_punished(self, rc):
        """Recall, not precision: the question is how much of the answer you produced."""
        assert rc.word_overlap(self.ANSWER + " and it is checked by a test", self.ANSWER) == 1.0

    def test_a_typed_prose_answer_reveals_but_does_not_grade(self, rc, session, card):
        state = session([card("a", anchor="src/mod.py#alpha", a=self.ANSWER)],
                        ["t", "q"], lines=["something about ledgers"])
        assert state == {}

    def test_you_still_grade_it_yourself(self, rc, session, card):
        state = session([card("a", anchor="src/mod.py#alpha", a=self.ANSWER)],
                        ["t", "y", "q"], lines=["the ledger is authoritative"],
                        state={"a": {"box": 1, "due": "2026-01-01", "seen": 2, "lapses": 0}})
        assert state["a"]["box"] == 2


class TestCardNotes:
    """Your own note on a card: what it cost you, kept apart from what the repo decided."""

    def test_e_writes_a_note(self, rc, session, card):
        session([card("a", anchor="src/mod.py#alpha")], ["e", "q"],
                lines=["bit me on the backfill in August"])
        assert rc.read_card_note("repo", "a") == "bit me on the backfill in August"

    def test_notes_accumulate_rather_than_replace(self, rc, session, card):
        session([card("a", anchor="src/mod.py#alpha")], ["e", "e", "q"],
                lines=["first thing", "second thing"])
        assert rc.read_card_note("repo", "a").split("\n") == ["first thing", "second thing"]

    def test_an_abandoned_note_writes_nothing(self, rc, session, card):
        session([card("a", anchor="src/mod.py#alpha")], ["e", "q"], lines=[""])
        assert not rc.card_note_path("repo", "a").exists()

    def test_a_note_lives_under_notes_so_export_carries_it(self, rc):
        assert rc.card_note_path("repo", "a").is_relative_to(rc.deck_dir("repo") / "notes")

    def test_a_note_is_not_state_and_survives_a_rewritten_deck(self, rc, session, card):
        """It is deliberately not on the card: an update rewrites cards and must not touch this."""
        session([card("a", anchor="src/mod.py#alpha")], ["e", "q"], lines=["mine"])
        rc.deck_path("repo").write_text('{"repo": "repo", "cards": []}')
        assert rc.read_card_note("repo", "a") == "mine"

    def test_adopt_carries_the_note_to_the_new_id(self, rc, repo, deck_factory, card):
        import argparse
        repo.write("src/mod.py", "def alpha():\n    return 1\n")
        repo.commit("init")
        deck_factory(repo, [card("alpha-is-always-one", anchor="src/mod.py#alpha")])
        rc.save_state("repo", {"alpha-is-one": {"box": 3, "due": "2026-10-01", "seen": 2, "lapses": 0}})
        rc.append_card_note("repo", "alpha-is-one", "cost me an afternoon")

        rc.cmd_adopt(argparse.Namespace(repo="repo", path="alpha-is-one=alpha-is-always-one"))
        assert rc.read_card_note("repo", "alpha-is-always-one") == "cost me an afternoon"
        assert not rc.card_note_path("repo", "alpha-is-one").exists()


class TestWhyThisCard:
    """The panel that explains the queue, and the guarantee that it cannot lie."""

    def test_the_panel_sums_to_the_score_that_orders_the_queue(self, rc, monkeypatch, card):
        """Explaining the order in a second implementation is how the two drift apart."""
        monkeypatch.setattr(rc.random, "random", lambda: 0.0)
        c = card("a", priority=1, anchor="a.py")
        cs = {"box": 1, "due": (rc.today() - __import__("datetime").timedelta(days=10)).isoformat()}
        parts = rc.score_parts(c, {}, cs)
        assert sum(d for _w, d, _y in parts) == rc.order_score(c, {}, cs)

    def test_an_overdue_card_says_so(self, rc, card):
        import datetime as dt
        cs = {"box": 1, "due": (rc.today() - dt.timedelta(days=9)).isoformat()}
        labels = [w for w, _d, _y in rc.score_parts(card("a"), {}, cs)]
        assert any("overdue 9d" == w for w in labels)

    def test_a_card_that_is_not_overdue_says_nothing_about_it(self, rc, card):
        cs = {"box": 1, "due": rc.today().isoformat()}
        assert not any("overdue" in w for w, _d, _y in rc.score_parts(card("a"), {}, cs))

    def test_grades_accumulate_into_a_history(self, rc, session, card):
        state = session([card("a", anchor="src/mod.py#alpha"), card("b", anchor="src/mod.py#alpha")],
                        ["enter", "y", "enter", "n", "q"])
        assert state["a"]["history"] == "y"
        assert state["b"]["history"] == "n"

    def test_history_is_capped(self, rc, session, card):
        state = session([card("a", anchor="src/mod.py#alpha"), card("b", anchor="src/mod.py#alpha")],
                        ["enter", "y", "q"],
                        state={"a": {"box": 1, "due": "2026-01-01", "seen": 99, "lapses": 0,
                                     "history": "y" * rc.HISTORY_LEN}})
        assert len(state["a"]["history"]) == rc.HISTORY_LEN

    def test_tabs_offer_what_the_card_actually_has(self, rc, repo, deck_factory, card):
        repo.write("src/mod.py", "def alpha():\n    return 1\n")
        repo.commit("init")
        entry = deck_factory(repo, [card("a", anchor="src/mod.py#alpha")])
        bare = rc.card_tabs({"id": "a"}, entry, "recall")
        assert "routes" not in bare and "note" not in bare
        rc.append_card_note("repo", "a", "mine")
        with_note = rc.card_tabs({"id": "a", "look": {"src/mod.py": "x", "docs": "y"}}, entry, "recall")
        assert with_note == ["answer", "routes", "note", "why", "question"]

    def test_a_locate_card_has_no_routes_tab(self, rc, repo, deck_factory, card):
        """Its routes are the answer, so a routes tab would be the answer tab twice."""
        repo.write("src/mod.py", "def alpha():\n    return 1\n")
        repo.commit("init")
        entry = deck_factory(repo, [card("a", anchor="src/mod.py#alpha")])
        assert "routes" not in rc.card_tabs({"id": "a", "look": {"a": "x", "b": "y"}}, entry, "locate")


class TestQueueStrip:
    """The session in one row."""

    @staticmethod
    def glyphs(rc, text):
        return "".join(ch for ch in rc._INVISIBLE.sub("", text) if ch in "◉●○‹›")

    def rows(self, rc, n, state=None):
        card = {"id": "c"}
        return [({"name": "r"}, {"id": f"c{i}"}, state or {}, {}, ({}, 0.0)) for i in range(n)]

    def test_graded_missed_and_remaining_are_distinct(self, rc):
        strip = rc.queue_strip(self.rows(rc, 4), 2, {0: "y", 1: "n"}, 60)
        assert self.glyphs(rc, strip) == "●●◉○"

    def test_a_flagged_card_shows_before_it_is_graded(self, rc):
        rows = self.rows(rc, 3, state={"c2": {"flagged": "2026-09-17"}})
        assert self.glyphs(rc, rc.queue_strip(rows, 0, {}, 60)) == "◉○●"

    def test_a_long_queue_windows_around_where_you_are(self, rc):
        strip = rc.queue_strip(self.rows(rc, 200), 100, {}, 40)
        assert strip.startswith("  ") and "‹" in strip and "›" in strip
        assert len(self.glyphs(rc, strip)) == 36   # 34 pips plus both edge marks

    def test_the_start_of_a_long_queue_has_no_left_edge_mark(self, rc):
        assert "‹" not in rc.queue_strip(self.rows(rc, 200), 0, {}, 40)
