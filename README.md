# repo-cards

Spaced-repetition Q&A decks for codebases, so you can re-enter a repo without re-reading it. Built
for working across many repos, where the expensive part of a context switch is not the code but
reconstructing *why* the constraints exist.

A Claude Code plugin (writes and maintains decks) plus a small CLI (the review loop).

## What a deck is

Not a summary. The facts where **being wrong is expensive**. The test applied to every card:

> If I believed the opposite of this, what would it cost me?

If the answer is not "a defect, a reopened decision, or a lost hour", it belongs in a document.
Anything `grep` answers in ten seconds is excluded on purpose. Decks run 60 to 80 cards, because
one that takes more than ten minutes a day gets abandoned.

```yaml
- id: outbox-row-is-a-prompt
  tags: [outbox, invariant]
  anchor: src/billing/outbox.py#enqueue
  q: >-
    ADR-7: enqueue writes an empty payload. Why is the outbox row blank, and what does that make it?
  a: >-
    It makes the message a prompt, not a snapshot. The row says this invoice changed; the bytes are
    rendered at send time, so a queued payload would go out stale.
```

## Install

Requires [uv](https://docs.astral.sh/uv/) and Claude Code.

```bash
git clone https://github.com/MitchellNeedham/repo-cards ~/code/repo-cards
~/code/repo-cards/install.sh          # Windows: install.ps1
```

`install.sh` links `repo-cards` into `~/.local/bin`. Then add the skill in Claude Code:

```
/plugin marketplace add MitchellNeedham/repo-cards
/plugin install repo-cards@repo-cards
```

## Use

```bash
repo-cards register ~/work/billing
```

Then, from Claude Code inside that repo:

```
/repo-cards:generate     # write the deck
/repo-cards:update       # bring it back in line with what has been committed since
```

`update` is the one that matters. It starts from `drift` (below), verifies every card whose source
moved, and only then considers new ones. Asking in plain words works too: *"update my repo cards"*
reaches the same skill.

Reviewing is yours. Boxes 1 to 5, due after 1, 2, 4, 8 and 16 days; a miss drops to box 1 rather
than back one step, because a fact you have lost is not most of the way to known.

```
$ repo-cards --limit 3

3 card(s)  [enter] reveal  y got it  n missed  s skip  q quit
──────────────────────────────────────────────────────────────────
1/3  billing  box 2  outbox invariant

  ADR-7: enqueue writes an empty payload. Why is the outbox row
  blank, and what does that make it?

  [enter] reveal, s skip, q quit >

  It makes the message a prompt, not a snapshot. The row says this
  invoice changed; the bytes are rendered at send time.

  anchor: src/billing/outbox.py#enqueue

  y got it / n missed / s skip / q quit > y
──────────────────────────────────────────────────────────────────
2 right, 1 missed, 0 skipped  (67%)
```

Meeting tomorrow on one feature? `brief` reads an area end to end, in the order that tells the
story, and **writes no state**, so a cram does not reschedule cards you already know:

```
$ repo-cards topics

billing
  payouts       14 cards  How a payout moves from requested to settled
  orientation    9 cards  What the system is and where the boundaries sit

$ repo-cards brief --topic payouts

billing · payouts
How a payout moves from requested to settled
14 card(s) · notes: ~/.local/share/repo-cards/billing/notes/payouts.md

  1. ADR-7: enqueue writes an empty payload. Why is the outbox row blank?
     It makes the message a prompt, not a snapshot. The row says this
     invoice changed; the bytes are rendered at send time.
     src/billing/outbox.py#enqueue
```

Ad-hoc slices need no curation: `--tag outbox,retry` takes several themes and `--grep 'idempoten'`
searches question, answer, anchor and tags. Both work on `review` and `brief`.

`update` starts from `drift`, which is what keeps a deck honest:

```
$ repo-cards drift --repo billing

deck generated at: a1b2c3d      HEAD now: 9f8e7d6

--- commits since a1b2c3d (4) ---
9f8e7d6 Send on commit, not on a timer
4c1a02b Drop the retry queue nobody could explain

--- cards whose anchor changed (2) : VERIFY THESE ---
  outbox-row-is-a-prompt        src/billing/outbox.py#enqueue
  retry-is-not-redelivery       src/billing/retry.py#schedule

--- file changed but the anchored symbol was not touched (5) : likely fine ---
--- changed files no card is anchored to (3) : CANDIDATES ---
  src/billing/webhooks.py
```

## Commands

| | |
|---|---|
| `repo-cards` | everything due, across every registered repo |
| `brief` | read an area end to end, in order, writing no state |
| `--repo N` `--tag a,b` `--grep RE` `--topic T` | narrow to a repo, themes, a search or a curated topic |
| `--limit N` `--new` `--all` | cap the session / only unseen / ignore due dates |
| `topics` `stats` `list` `drift` | topics defined, deck health, every card, what changed |
| `register PATH` `forget NAME` `repos` | manage the registry |
| `home` | where everything lives on this machine |

## Where data lives

**Nothing is written into the repo being carded.** Decks go in the platform data directory:
`~/.local/share/repo-cards`, `~/Library/Application Support/repo-cards` on macOS,
`%LOCALAPPDATA%\repo-cards` on Windows. `REPO_CARDS_HOME` overrides it, `XDG_DATA_HOME` is honoured
everywhere, `repo-cards home` prints what it resolved.

```
<data home>/
  registry.json       name -> repo root. Per machine, since paths differ
  <name>/
    deck.yaml         the cards. Content only, and portable
    state.json        Leitner state, keyed by card id
    notes/            long-form notes, which topics can point at
```

## Why it works this way

- **Content and state are separate files**, so regenerating a deck never costs review progress. A
  card that keeps its id keeps its box, which is what makes `update` safe to run often.
- **Every card carries a source anchor, and `update` verifies before it adds.** A stale card is
  worse than a missing one because you act on it confidently. A deck that only grows starts lying.
- **Anchors name a symbol, not just a file**, so one commit to a large module does not flag every
  card drawn from it. On a real 17-commit window: 16 cards to verify instead of 28.

MIT.
