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

    def test_a_short_blank_tolerates_a_typo_as_well(self, rc):
        """0.85 is a different rule at every length: it forgives two letters of
        `authoritative` and nothing at all of `box`, where one slip scores 0.67."""
        card = {"id": "c", "a": "A card sits in a {{box}}."}
        assert rc.check_answer(card, "cloze", ["bxo"])[0]

    def test_two_letters_are_too_short_to_have_a_typo(self, rc):
        """`in` and `on` are one edit apart and mean different things."""
        assert not rc.close_enough("in", "on")

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
    """`/` in a session: typed, marked, and overridable."""

    CLOZE = {"kind": "cloze", "a": "The ledger is {{authoritative}}."}

    def test_a_right_answer_advances_the_box(self, rc, session, card):
        state = session([card("a", anchor="src/mod.py#alpha", **self.CLOZE)],
                        ["/", "q"], lines=["authoritative"],
                        state={"a": {"box": 2, "due": "2026-01-01", "seen": 1, "lapses": 0}})
        assert state["a"]["box"] == 3

    def test_a_wrong_answer_returns_it_to_box_one(self, rc, session, card):
        state = session([card("a", anchor="src/mod.py#alpha", **self.CLOZE)],
                        ["/", "q"], lines=["whatever"],
                        state={"a": {"box": 4, "due": "2026-01-01", "seen": 1, "lapses": 0}})
        assert state["a"]["box"] == 1
        assert state["a"]["lapses"] == 1

    def test_you_can_override_the_mark(self, rc, session, card):
        """The mark is a fact about the words, not about whether you knew it."""
        state = session([card("a", anchor="src/mod.py#alpha", **self.CLOZE),
                         card("b", anchor="src/mod.py#alpha")],
                        ["/", "y", "q"], lines=["not the word"],
                        state={"a": {"box": 2, "due": "2026-01-01", "seen": 1, "lapses": 0}})
        assert state["a"]["box"] == 3
        assert state["a"]["lapses"] == 0

    def test_typing_is_not_offered_in_learn_mode(self, rc, session, card):
        state = session([card("a", anchor="src/mod.py#alpha", **self.CLOZE)],
                        ["/", "q"], lines=["authoritative"], mode="learn")
        assert state == {}

    def test_the_old_type_key_no_longer_does_anything(self, rc, session, card):
        """One key for one thing: `/` is what the field advertises."""
        state = session([card("a", anchor="src/mod.py#alpha", **self.CLOZE)],
                        ["t", "q"], lines=["authoritative"],
                        state={"a": {"box": 2, "due": "2026-01-01", "seen": 1, "lapses": 0}})
        assert state == {}


class TestAnswerField:
    """The field on the front of a card, which is the only thing saying it can be answered."""

    def plain(self, rc, lines):
        return rc._INVISIBLE.sub("", "\n".join(lines))

    def test_the_field_rests_with_a_placeholder_in_it(self, rc):
        assert self.plain(rc, rc.answer_field("recall", None, 60)) == "  answer: type / to start"

    def test_typing_replaces_the_placeholder(self, rc):
        out = self.plain(rc, rc.answer_field("recall", "a prompt", 60))
        assert out == "  answer: a prompt\u2588"

    def test_a_kind_with_a_shape_says_what_it_wants(self, rc):
        """The placeholder is where `numbers, not words` is said, since the field is always up."""
        assert "numbers" in self.plain(rc, rc.answer_field("order", None, 60))
        assert "paths" in self.plain(rc, rc.answer_field("locate", None, 60))

    def test_a_cloze_has_no_field_because_it_fills_the_sentence(self, rc):
        out = self.plain(rc, rc.answer_field("cloze", None, 60))
        assert out == "  type / to fill the blanks"

    def test_a_long_answer_wraps_rather_than_running_off_the_edge(self, rc):
        """The page cuts an overlong line at the end, which is the half you are writing."""
        typed = "the row says this invoice changed and the bytes are rendered at send time"
        out = self.plain(rc, rc.answer_field("recall", typed, 50)).split("\n")
        assert len(out) > 1
        assert all(len(ln) <= 50 for ln in out)
        assert out[-1].endswith("\u2588")

    def test_a_word_too_long_to_break_on_a_space_is_split(self, rc):
        """Otherwise the line is cut and the cursor goes with it."""
        out = self.plain(rc, rc.answer_field("locate", "src/" + "billing/" * 12, 50)).split("\n")
        assert all(len(ln) <= 50 for ln in out)
        assert out[-1].endswith("\u2588")


class TestOverlapHint:
    """Prose is measured, never marked."""

    ANSWER = "The ledger is authoritative; the projection is written in the same transaction."

    def test_the_same_words_score_full(self, rc):
        assert rc.word_overlap(self.ANSWER, self.ANSWER) == 1.0

    def test_nothing_in_common_scores_zero(self, rc):
        assert rc.word_overlap("no idea at all", self.ANSWER) == 0.0

    def test_a_typo_counts_as_the_word(self, rc):
        """A hint that lists `transacton` among the words you did not say is about spelling."""
        assert rc.word_overlap("the projection is written in one transacton",
                               "the projection is written in one transaction") == 1.0

    def test_a_short_answer_is_measured_even_with_nothing_to_count(self, rc):
        """Every word a stopword, so there are no content words: scoring it zero would say
        the reader produced none of an answer they typed exactly."""
        assert rc.word_overlap("it is the one", "it is the one") == 1.0

    def test_a_crude_stem_lets_versions_meet_versioned(self, rc):
        assert rc.word_overlap("versions", "the handshake is versioned") > 0

    def test_filler_words_do_not_flatter_an_answer(self, rc):
        assert rc.word_overlap("it is the and of in on at for", self.ANSWER) == 0.0

    def test_saying_more_than_the_card_is_not_punished(self, rc):
        """Recall, not precision: the question is how much of the answer you produced."""
        assert rc.word_overlap(self.ANSWER + " and it is checked by a test", self.ANSWER) == 1.0

    def test_a_typed_prose_answer_reveals_but_does_not_grade(self, rc, session, card):
        state = session([card("a", anchor="src/mod.py#alpha", a=self.ANSWER)],
                        ["/", "q"], lines=["something about ledgers"])
        assert state == {}

    def test_you_still_grade_it_yourself(self, rc, session, card):
        state = session([card("a", anchor="src/mod.py#alpha", a=self.ANSWER)],
                        ["/", "y", "q"], lines=["the ledger is authoritative"],
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


class TestTabRow:
    """The row of faces: the same names in the same columns on every card."""

    @staticmethod
    def plain(rc, lines):
        return [rc._INVISIBLE.sub("", ln).strip() for ln in lines]

    def test_the_row_reads_the_same_whatever_the_card_carries(self, rc):
        """The complaint it answers: why and question used to move as routes came and went."""
        everything = self.plain(rc, rc.render_tab_row(list(rc.TAB_ORDER), "answer", 76))
        bare = self.plain(rc, rc.render_tab_row(["answer", "why", "question"], "answer", 76))
        assert everything[0] == bare[0]
        assert bare[0].split() == ["answer", "\u2502", "routes", "\u2502", "note",
                                   "\u2502", "why", "\u2502", "question"]

    def test_a_face_this_card_has_not_got_is_struck_out(self, rc, monkeypatch):
        """Piped output has no colour at all, so the three states only differ in front of one."""
        for key, code in (("reset", "\033[0m"), ("bold", "\033[1m"),
                          ("dim", "\033[2m"), ("strike", "\033[9m")):
            monkeypatch.setitem(rc.C, key, code)
        row = rc.render_tab_row(["answer", "why", "question"], "answer", 76)[0]
        assert "\033[9mroutes" in row and "\033[9mnote" in row
        assert "\033[9mwhy" not in row and "\033[9manswer" not in row

    def test_the_keys_that_move_between_them_sit_under_the_row(self, rc):
        assert "\u2191/\u2193" in self.plain(rc, rc.render_tab_row(list(rc.TAB_ORDER), "why", 76))[1]

    def test_the_strike_is_explained_only_when_something_is_struck(self, rc):
        full = self.plain(rc, rc.render_tab_row(list(rc.TAB_ORDER), "answer", 76))[1]
        some = self.plain(rc, rc.render_tab_row(["answer", "why", "question"], "answer", 76))[1]
        assert "struck out" not in full
        assert "struck out" in some

    def test_a_narrow_page_keeps_the_keys_and_drops_the_aside(self, rc):
        width = rc.MIN_WIDTH - 2
        lines = self.plain(rc, rc.render_tab_row(["answer", "why", "question"], "answer", width))
        assert "\u2191/\u2193" in lines[1] and "struck out" not in lines[1]
        assert all(len(ln) <= width for ln in lines)

    def test_the_key_row_no_longer_repeats_the_hint(self, rc):
        """Said once, beside the row it drives. The whole set is still behind `?`."""
        for mode in ("test", "learn"):
            assert "tabs" not in rc._INVISIBLE.sub("", rc.card_keys("recall", {}, True, mode))
        assert any(key == "\u2191/\u2193" for key, _what, _when in rc.KEYS)


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


class TestDiffAndInPlaceCloze:
    """What the reader typed, shown against what was wanted."""

    ANSWER = "It makes the message a prompt, not a snapshot."

    def plain(self, rc, lines):
        return rc._INVISIBLE.sub("", "\n".join(lines))

    def test_the_marked_answer_still_fills_the_line(self, rc, monkeypatch):
        """Colour is off when the output is piped, so the paint that broke the measure only
        exists in front of a terminal. Turned on here, which is where the bug lived."""
        for key, code in (("reset", "\033[0m"), ("bold", "\033[1m"),
                          ("cyan", "\033[36m"), ("dim", "\033[2m")):
            monkeypatch.setitem(rc.C, key, code)
        answer = " ".join(["alpha bravo charlie delta echo foxtrot"] * 3)
        lines = self.plain(rc, rc.render_overlap("nothing", answer, 60)).split("\n")
        filled = [ln for ln in lines if "alpha" in ln or "bravo" in ln]
        assert min(len(ln) for ln in filled[:-1]) > 45
        assert all(len(ln) <= 60 for ln in lines)

    def test_the_words_you_missed_are_named(self, rc):
        out = self.plain(rc, rc.render_overlap("the row says it changed", self.ANSWER, 70))
        assert "you did not say:" in out
        assert "prompt" in out.split("you did not say:")[1]
        assert "snapshot" in out.split("you did not say:")[1]

    def test_words_you_did_say_are_not_named(self, rc):
        out = self.plain(rc, rc.render_overlap("a prompt, not a snapshot", self.ANSWER, 70))
        missed = out.split("you did not say:")[1]
        assert "prompt" not in missed and "snapshot" not in missed

    def test_saying_all_of_it_names_nothing(self, rc):
        out = self.plain(rc, rc.render_overlap(self.ANSWER, self.ANSWER, 70))
        assert "you did not say:" not in out
        assert "~100%" in out

    def test_the_answer_comes_with_the_diff(self, rc):
        """It stands in for the plain answer rather than sitting above a second copy."""
        out = self.plain(rc, rc.render_overlap("nothing", self.ANSWER, 70))
        assert "It makes the message a prompt" in out.replace("\n", " ")

    def test_a_filled_blank_shows_what_you_typed(self, rc):
        card = {"id": "c", "a": "The ledger is {{authoritative}}; written {{in one transaction}}."}
        out = rc._INVISIBLE.sub("", rc.cloze_sentence(card, ["authoritative"], 1, "in one"))
        assert "The ledger is authoritative;" in out

    def test_the_blank_you_are_on_carries_the_cursor(self, rc):
        card = {"id": "c", "a": "The ledger is {{authoritative}}; written {{in one transaction}}."}
        out = rc._INVISIBLE.sub("", rc.cloze_sentence(card, ["authoritative"], 1, "in one"))
        assert "written in one█." in out

    def test_blanks_you_have_not_reached_stay_blank(self, rc):
        card = {"id": "c", "a": "The ledger is {{authoritative}}; written {{in one transaction}}."}
        out = rc._INVISIBLE.sub("", rc.cloze_sentence(card, [], 0, "auth"))
        assert "▁" in out.split(";")[1]


class TestWrapping:
    """A line is measured in the columns it occupies, not the characters it carries."""

    WORDS = "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima"

    def test_painting_a_word_does_not_move_the_break(self, rc):
        """A coloured word carries twenty characters the terminal never draws."""
        painted = rc.wrap(" ".join(f"\033[1m{w}\033[0m" for w in self.WORDS.split()), 40)
        assert rc._INVISIBLE.sub("", painted) == rc.wrap(self.WORDS, 40)

    def test_a_hyperlink_does_not_move_it_either(self, rc):
        """An OSC 8 wrapper is longer than the path it links, and it is drawn as the path."""
        linked = " ".join(f"\033]8;;file:///{w}\033\\{w}\033]8;;\033\\" for w in self.WORDS.split())
        assert rc._INVISIBLE.sub("", rc.wrap(linked, 40)) == rc.wrap(self.WORDS, 40)


class TestOpeningRoutes:
    """`look` says go and check. The number key is that instruction carried out."""

    @pytest.fixture
    def carded(self, rc, repo, deck_factory, card, monkeypatch):
        repo.write("src/mod.py", "def alpha():\n    return 1\n\n\ndef beta():\n    return 2\n")
        repo.commit("init")
        deck_factory(repo, [card("a", anchor="src/mod.py#beta")])
        ran = []
        monkeypatch.setattr(rc, "run_outside_screen", lambda argv: ran.append(argv) or True)
        return repo, ran

    def test_a_route_opens_in_the_viewer(self, rc, carded, monkeypatch):
        repo, ran = carded
        monkeypatch.setenv("EDITOR", "vim")
        assert rc.open_ref("src/mod.py", repo.path) == ""
        assert ran[0][0] == "vim" and ran[0][-1].endswith("src/mod.py")

    def test_an_anchored_symbol_opens_at_its_line(self, rc, carded, monkeypatch):
        repo, ran = carded
        monkeypatch.setenv("EDITOR", "vim")
        rc.open_ref("src/mod.py#beta", repo.path)
        assert "+5" in ran[0]

    def test_a_viewer_that_cannot_jump_is_not_given_a_line(self, rc, carded, monkeypatch):
        repo, ran = carded
        monkeypatch.setenv("EDITOR", "mystery-editor")
        rc.open_ref("src/mod.py#beta", repo.path)
        assert not any(a.startswith("+") for a in ran[0])

    def test_a_path_that_is_gone_says_so_rather_than_opening_nothing(self, rc, carded, monkeypatch):
        repo, _ran = carded
        monkeypatch.setenv("EDITOR", "vim")
        assert "no such path" in rc.open_ref("src/gone.py", repo.path)

    def test_a_ref_into_an_unregistered_repo_says_which(self, rc, carded, monkeypatch):
        repo, _ran = carded
        monkeypatch.setenv("EDITOR", "vim")
        assert "ghost is not registered" in rc.open_ref("ghost::src/mod.py", repo.path)

    def test_a_cross_repo_route_resolves_through_the_registry(self, rc, carded, tmp_path, monkeypatch,
                                                              deck_factory, card):
        from conftest import Repo
        repo, ran = carded
        other = Repo(tmp_path / "other")
        other.write("api/contract.py", "def handshake():\n    return 1\n")
        other.commit("init")
        deck_factory(other, [], name="other")
        monkeypatch.setenv("EDITOR", "vim")
        assert rc.open_ref("other::api/contract.py", repo.path) == ""
        assert ran[0][-1].endswith("api/contract.py")
