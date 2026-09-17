#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""The experiment behind OVERDUE_PER_DAY, runnable.

A weighted queue has a failure mode that never shows up in a short session and is invisible
in the one place you would look, the daily review, because the cards you see are the right
cards. It is the cards you never see that are wrong, and there is no screen for those.

Somebody working across eight repos cannot review a whole deck a day, so the queue is capped.
Weighting alone means the tail of the distribution never out-ranks the head, ever: a detail
card at priority 3 sits behind 185 foundational cards for the entire simulated period. The
guard escalates a card the longer it stays overdue, capped, so it takes weeks rather than
days to overtake a tier and the weighting still means something.

    ./tests/simulate_starvation.py            # both arms, 180 days
    ./tests/simulate_starvation.py --days 365
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.machinery
import importlib.util
import random
import statistics
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "bin" / "repo-cards"


def load():
    loader = importlib.machinery.SourceFileLoader("repo_cards", str(SCRIPT))
    spec = importlib.util.spec_from_loader("repo_cards", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


#: Eight decks of eighty, and a priority mix at the quarter-foundational the skill asks for.
DECKS, PER_DECK = 8, 80
MIX = {1: 185, 2: 295, 3: 160}


def build(rng) -> list[dict]:
    pool = [p for p, n in MIX.items() for _ in range(n)]
    rng.shuffle(pool)
    return [{"id": f"d{i // PER_DECK}-c{i}", "priority": pool[i], "anchor": f"src/m{i}.py"}
            for i in range(DECKS * PER_DECK)]


def simulate(rc, overdue_per_day: float, days: int, per_day: int, accuracy: float, seed: int) -> dict:
    rng = random.Random(seed)
    cards = build(rng)
    start = dt.date(2026, 1, 1)
    clock = {"now": start}

    rc.OVERDUE_PER_DAY = overdue_per_day
    rc.today = lambda: clock["now"]
    rc.random.seed(seed)

    state = {c["id"]: {"box": 1, "due": start.isoformat(), "seen": 0, "lapses": 0} for c in cards}
    deck: dict = {}

    for day in range(days):
        clock["now"] = start + dt.timedelta(days=day)
        due = [c for c in cards if rc.is_due(state[c["id"]])]
        due.sort(key=lambda c: rc.order_score(c, deck, state[c["id"]]))
        for card in due[:per_day]:
            cs = state[card["id"]]
            cs["seen"] += 1
            if rng.random() < accuracy:
                cs["box"] = min(cs["box"] + 1, rc.MAX_BOX)
            else:
                cs["lapses"] += 1
                cs["box"] = 1
            cs["due"] = (clock["now"] + dt.timedelta(days=rc.INTERVALS[cs["box"]])).isoformat()

    unseen = [c for c in cards if state[c["id"]]["seen"] == 0]
    return {
        "unseen": len(unseen),
        "unseen_by_priority": {p: sum(1 for c in unseen if c["priority"] == p) for p in (1, 2, 3)},
        "median_reviews": statistics.median(state[c["id"]]["seen"] for c in cards),
        "reviews_p3": statistics.mean(state[c["id"]]["seen"] for c in cards if c["priority"] == 3),
        "reviews_p1": statistics.mean(state[c["id"]]["seen"] for c in cards if c["priority"] == 1),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--days", type=int, default=180)
    p.add_argument("--per-day", type=int, default=15)
    p.add_argument("--accuracy", type=float, default=0.8)
    p.add_argument("--seed", type=int, default=7)
    args = p.parse_args()

    rc = load()
    total = DECKS * PER_DECK
    print(f"\n{args.days} days · {args.per_day} cards/day · {DECKS} decks · {total} cards"
          f" · {MIX[1]} foundational\n")
    print(f"  {'guard':<22} {'never seen':>10} {'of those p3':>12} {'mean reviews p1':>16} {'p3':>6}")
    for label, rate in (("off (weighting only)", 0.0), (f"on ({rc.OVERDUE_PER_DAY or 0.05}/day)", 0.05)):
        r = simulate(rc, rate, args.days, args.per_day, args.accuracy, args.seed)
        print(f"  {label:<22} {r['unseen']:>10} {r['unseen_by_priority'][3]:>12} "
              f"{r['reviews_p1']:>16.1f} {r['reviews_p3']:>6.1f}")
    print("\n  A card only overtakes a tier after weeks of neglect, so the weighting still"
          "\n  decides what a short session opens with.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
