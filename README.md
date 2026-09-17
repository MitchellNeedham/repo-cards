# repo-cards

Spaced-repetition Q&A decks for codebases, so you can re-enter a repo without re-reading it. Built
for working across many repos, where the expensive part of a context switch is not the code but
reconstructing *why* the constraints exist.

A Claude Code plugin that writes and maintains the decks, plus a CLI that reviews them.

## Install

Requires [uv](https://docs.astral.sh/uv/) and Claude Code.

```bash
git clone https://github.com/MitchellNeedham/repo-cards ~/code/repo-cards
~/code/repo-cards/install.sh          # Windows: install.ps1
```

```
/plugin marketplace add MitchellNeedham/repo-cards
/plugin install repo-cards@repo-cards
```

## What a deck is

Not a summary. The facts where **being wrong is expensive**. The test applied to every card:

> If I believed the opposite of this, what would it cost me?

If the answer is not "a defect, a reopened decision, or a lost hour", it belongs in a document.
Anything `grep` answers in ten seconds is excluded on purpose.

```yaml
- id: outbox-row-is-a-prompt
  tags: [outbox, invariant]
  priority: 1                             # 1 foundational, 2 core (default), 3 detail
  anchor: src/billing/outbox.py#enqueue   # where the fact is defined
  look:                                   # how to go and check it yourself
    src/billing/outbox.py#enqueue: the empty payload, and the comment arguing it
    docs/adr/adr-7-outbox.md: the decision, and what it rejected
  q: >-
    ADR-7: enqueue writes an empty payload. Why is the outbox row blank, and what does that make it?
  a: >-
    It makes the message a prompt, not a snapshot. The row says this invoice changed; the bytes are
    rendered at send time, so a queued payload would go out stale.
```

`priority` decides what a short session spends its time on. `look` is the route you would take to
answer the question yourself, shown **before** the answer so you can go and check. `anchor` is the
one place the fact is defined, and is what drift and churn are measured on.

A path may also name another registered repo, as `sfap::src/api/contract.py#handshake`. The
expensive knowledge in a pair of services is usually the contract between them, and a card about
it has to be verified when *either* side moves.

## Use

From Claude Code, inside the repo you want carded:

```
/repo-cards:generate     # registers the repo and writes the deck
/repo-cards:update       # brings it back in line with what has been committed since
```

That is the whole setup. `update` verifies every card whose source moved before it adds anything,
and with no argument it sweeps every registered repo.

Then `repo-cards` asks what to review. Both lists scroll, with paging and `home`/`end`, and your
choice is remembered for next time.

```
╭─ Which decks? 2/4 selected ───────────────────────────────╮
│                                                           │
│  ❯ ◉ billing        77 cards   12 due →   all topics      │
│    ◉ checkout       84 cards    9 due →   last-week       │
│    ○ platform       40 cards    0 due                     │
│                                                           │
│    no deck: search-api, ingest +2                         │
│    /repo-cards:generate                                   │
│                                                           │
╰─ ↑/↓ move · space toggle · → topics · enter start ────────╯
```

Then one card at a time, sized to its content and centred:

```
╭─ billing · recall ─────────────────────── 4/22  box 2  ★★★ ─╮
│                                                             │
│   ▌payouts  ▌last-week                                      │
│                                                             │
│   ADR-7: enqueue writes an empty payload. Why is the        │
│   outbox row blank, and what does that make it?             │
│                                                             │
│   → src/billing/outbox.py#enqueue                           │
│     the empty payload, and the comment arguing it           │
│   → docs/adr/adr-7-outbox.md                                │
│     the decision, and what it rejected                      │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   It makes the message a prompt, not a snapshot. The row    │
│   says this invoice changed; the bytes are rendered at      │
│   send time.                                                │
│                                                             │
│   anchor  src/billing/outbox.py#enqueue                     │
│                                                             │
╰─ ←/→ move · y got it · n missed · l learn · q quit ─────────╯
```

`←`/`→` move, `enter` reveals, `y`/`n` grade. Boxes 1 to 5, due after 1, 2, 4, 8 and 16 days; a
miss drops to box 1, because a fact you have lost is not most of the way to known.

**`f` flags a card you do not believe**, and asks why. "I forgot this" and "this is not true any
more" are different facts and only the second one is a defect, so a flag grades nothing. The note
goes with it:

```
╭─ billing · recall ──────────────────────────────────────────╮
│   ADR-7: enqueue writes an empty payload. Why is the        │
│   outbox row blank, and what does that make it?             │
│                                                             │
│   why? rendered in the worker now, not at send time█        │
╰─ ←/→ move · enter reveal · l learn · f unflag · q quit ─────╯
```

It lands at the top of the next `drift`, in your own words, and is the first thing an update looks
at. That is how review feeds the deck rather than only consuming it, and it catches what git
cannot: a card that was wrong the day it was written.

**Two modes.** `test` (the default) hides the answer and is the only one that moves a card's box.
`learn` shows everything and grades nothing. `l` switches mid-session.

**`e` keeps your own note on a card**, in `$EDITOR` or as a typed line:

```
│   anchor  src/billing/outbox.py#enqueue                     │
│                                                             │
│   your note                                                 │
│   bit me on the backfill in August: the replay re-rendered  │
│   at today's rates                                          │
```

The deck says what the repo decided. The note says what it cost you, which is why it lives beside
the deck rather than in it: an update rewrites cards and never touches your notes. They show under
the answer and in `brief`, travel with `export`, and follow a card through a rename.

**Not every card is a plain question.** `cloze` blanks out the load-bearing words, `order` shuffles
a sequence, and `locate` asks *where you would look*, treating the routes as the answer. A recall
card with good routes is asked that way about one time in six.

**Those three can be typed and marked** with `t`, because their answers are short and exact:

```
╭─ billing · fill the blanks ──────────────── 4/22  box 2  ★★★ ─╮
│   The ledger is ▁▁▁▁▁▁▁▁▁▁▁▁▁; the projection is written      │
│   ▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁.                                         │
│                                                               │
│   2? in one transaction█                                      │
├───────────────────────────────────────────────────────────────┤
│   ✓ authoritative                                             │
│   ✗ in the same transaction                                   │
│       you said: in one transaction                            │
│                                                               │
│   marked from what you typed · y or n overrides               │
╰─ ←/→ move · y got it · n missed · l learn · f flag · q quit ──╯
```

A typo passes, a different word does not, and the mark moves the box like any other grade.

On a **prose** card `t` measures instead of marking: it shows how much of the answer's content your
words covered, and you still grade yourself. That line is drawn on purpose. On a card whose answer
is a *why*, "blank to save space" and "blank because it is a prompt, not a snapshot" look alike to
any string comparison, and one of them is the defect the card exists to prevent. `rapidfuzz` would
match better and `model2vec` would match meaning in thirty megabytes without an LLM; neither is
reached for, because the accuracy they buy is not the accuracy this needs, and both cost the
instant offline start that gets the tool run each morning.

**Topics** are curated reading orders, plus `last-week` and `last-month`, which are built from git
history: the cards whose anchor a commit touched in that window, newest first. Those two need no
maintenance and are the fastest way back in after time away. Work that landed through a merge is
dated when it landed, not when it was written, so a branch merged this morning counts as this
week however long it sat.

**`catchup` is the other half of coming back.** Its baseline is the last time you *reviewed* a
deck, not the last time the deck was updated, so it answers what the repo did while you were on
something else. Commits are grouped under the cards that sit on what they touched:

```
$ repo-cards catchup --repo billing

billing  last reviewed 2026-08-27, 21 day(s) ago
34 commit(s) here, 6 card(s) sitting on what they touched

  ⟳ outbox-row-is-a-prompt  src/billing/outbox.py#enqueue
     ADR-7: enqueue writes an empty payload. Why is the outbox row blank?
     a41c9f2  Render at send time for backfills too
     7b2e004  Drop the payload column, which nothing had read since ADR-7

  6 commit(s) touching nothing carded:
     3c1d88e  Add the reconciliation job
```

It writes no state and needs no model, which is the point: re-entry should cost a second, not a
session.

`drift` is the triage that `update` starts from:

```
$ repo-cards drift

  repo          commits  verify  flagged  routes  dead  new files   state
  billing            12       7        2       3     1          4   behind
  checkout            5      10        -       0     -         11   behind
  platform            -       -        1       -     -          -   up to date
  search-api          -       -        -       -     -          -   no deck

  2 deck(s) behind. Detail: repo-cards drift --repo <name>
  billing: far enough behind that a regenerate beats an update
  3 card(s) flagged during review in billing, platform. Detail: repo-cards flags
```

## Commands

| | |
|---|---|
| `repo-cards` | pick decks, then review everything due |
| `test` `learn` | answer hidden and graded, or everything visible and not |
| `brief` | read an area end to end, in order, writing no state |
| `--repo N` `--tag a,b` `--grep RE` `--topic T` `--priority 1` | narrow the session |
| `--limit N` `--new` `--all` `--no-pick` | cap it, unseen only, ignore due dates, skip the picker |
| `topics` `stats` `list` `drift` | what exists, deck health, every card, what changed |
| `check` `--strict` | validate a deck against the rules it is written to |
| `adopt OLD=NEW` | give a renamed card the old id's review history |
| `export --repo N` `import PATH` | hand a deck to somebody else, keeping your own progress |
| `catchup` `--since D` | what moved since you last reviewed, read-only |
| `flags` `flags --clear` | cards you marked suspect during review, and clearing them |
| `register PATH` `forget NAME` `repos` `home` | the registry, and where things live |

## Where data lives

**Nothing is written into the repo being carded.** Decks go in the platform data directory:
`~/.local/share/repo-cards`, `~/Library/Application Support/repo-cards` on macOS,
`%LOCALAPPDATA%\repo-cards` on Windows. `REPO_CARDS_HOME` overrides it, `XDG_DATA_HOME` is honoured
everywhere, and `repo-cards home` prints what it resolved.

```
<data home>/
  registry.json       name -> repo root. Per machine, since paths differ
  session.json        last picked decks and mode
  <name>/
    deck.yaml         the cards. Content only, and portable
    state.json        Leitner state, keyed by card id
    notes/            long-form notes, which topics can point at
```

Portable is meant literally. `repo-cards export --repo billing --out ./billing-deck` writes the
cards and their notes somewhere you can commit or send, and `repo-cards import ./billing-deck`
installs them on the other machine. Review history stays where it is: the ids that match keep their
boxes, so importing a colleague's deck costs you nothing you had learned.

## Why it works this way

- **Content and state are separate files**, so regenerating a deck never costs review progress. A
  card that keeps its id keeps its box, which is what makes `update` safe to run often. `check`
  guards the promise: it lists every state entry no card claims and guesses which renamed card it
  belongs to, and `adopt` hands the history back. Without that, a reworded id silently resets a
  card you had at box 4.
- **Every card carries a source anchor, and `update` verifies before it adds.** A stale card is
  worse than a missing one, because you act on it confidently. A deck that only grows starts lying.
- **Anchors name a symbol, not just a file**, so one commit to a large module does not flag every
  card drawn from it. On a real 17-commit window: 16 cards to verify instead of 28.
- **Each card remembers the commit it was checked against**, so verifying one is not undone by the
  next commit to the same file. Without it, the cards on the busiest files are flagged every pass
  and the update becomes a thing you stop running.
- **The deck's rules are checked, not just described.** `repo-cards check` enforces what the skill
  asks for, so a generated deck is validated by a program rather than by the care of whoever
  generated it. Broken routes, duplicate ids, yes/no questions and anchors with no symbol are all
  found in milliseconds.
- **Review feeds the deck, not just the schedule.** A flag raised during review and a card missed
  three times running both land in `drift`, so an update fixes what the reading is telling you as
  well as what the commits are.
- **Churn is measured, not declared.** A card whose anchor was edited twenty times this year
  outranks one pointing at a decision nobody has revisited in three.
- **Priority is weighted, with a starvation guard.** A card's score also falls the longer it stays
  overdue. Simulated over 180 days at 15 cards a day across eight decks, weighting alone left 455
  of 640 cards never seen; with the guard, none. That simulation is
  `tests/simulate_starvation.py`, so the claim can be re-run rather than believed.

## Development

One uv script, one dependency, and tests that need nothing installed:

```bash
uv run --with pytest --with pyyaml pytest tests/ -q
./tests/simulate_starvation.py
```

The suite covers the places where being wrong is silent rather than loud: box transitions and
queue order, drift's symbol narrowing and per-card `verified` baselines, cross-repo refs, the
git date handling, and every rule `check` enforces. A mis-ordered queue still looks like a
queue, which is why it is worth a test and a `--help` is not.

MIT.
