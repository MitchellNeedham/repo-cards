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

**`f` flags a card you do not believe.** "I forgot this" and "this is not true any more" are
different facts and only the second one is a defect, so a flag grades nothing. It lands at the top
of the next `drift` and is the first thing an update looks at, which is how review feeds the deck
rather than only consuming it. On a repo that moves weekly, this catches what git cannot: a card
that was wrong the day it was written.

**Two modes.** `test` (the default) hides the answer and is the only one that moves a card's box.
`learn` shows everything and grades nothing. `l` switches mid-session.

**Not every card is a plain question.** `cloze` blanks out the load-bearing words, `order` shuffles
a sequence, and `locate` asks *where you would look*, treating the routes as the answer. A recall
card with good routes is asked that way about one time in six.

**Topics** are curated reading orders, plus `last-week` and `last-month`, which are built from git
history: the cards whose anchor a commit touched in that window, newest first. Those two need no
maintenance and are the fastest way back in after time away.

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

## Why it works this way

- **Content and state are separate files**, so regenerating a deck never costs review progress. A
  card that keeps its id keeps its box, which is what makes `update` safe to run often.
- **Every card carries a source anchor, and `update` verifies before it adds.** A stale card is
  worse than a missing one, because you act on it confidently. A deck that only grows starts lying.
- **Anchors name a symbol, not just a file**, so one commit to a large module does not flag every
  card drawn from it. On a real 17-commit window: 16 cards to verify instead of 28.
- **Churn is measured, not declared.** A card whose anchor was edited twenty times this year
  outranks one pointing at a decision nobody has revisited in three.
- **Priority is weighted, with a starvation guard.** A card's score also falls the longer it stays
  overdue. Simulated over 180 days at 15 cards a day across eight decks, weighting alone left 455
  of 640 cards never seen; with the guard, none.

MIT.
