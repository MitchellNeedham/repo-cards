# repo-cards

Spaced-repetition Q&A decks for codebases, so you can re-enter a repo without re-reading it. Built
for working across many repos, where the expensive part of a context switch is not the code but
reconstructing *why* the constraints exist.

A Claude Code plugin (writes and maintains decks) plus a small CLI (the review loop).

## What a deck is

Not a summary. The facts where **being wrong is expensive**. The test applied to every card:

> If I believed the opposite of this, what would it cost me?

If the answer is not "a defect, a reopened decision, or a lost hour", it belongs in a document.
Anything `grep` answers in ten seconds is excluded on purpose. A deck is as big as the number of
cards that clear the bar, and no bigger; ordering is what keeps a large one reviewable in ten
minutes rather than a size cap.

```yaml
- id: outbox-row-is-a-prompt
  tags: [outbox, invariant]
  priority: 1                             # 1 foundational, 2 core (default), 3 detail
  anchor: src/billing/outbox.py#enqueue   # where the fact is defined
  look:                                   # how to go and check it yourself
    src/billing/outbox.py#enqueue: the empty payload, and the comment arguing it
    docs/adr/adr-7-outbox.md: the decision, and what it rejected
    src/billing/tests/test_outbox.py: the test that pins it
  q: >-
    ADR-7: enqueue writes an empty payload. Why is the outbox row blank, and what does that make it?
  a: >-
    It makes the message a prompt, not a snapshot. The row says this invoice changed; the bytes are
    rendered at send time, so a queued payload would go out stale.
```

**`priority` is why a short session is worth doing.** Cards are ordered by a weighted shuffle, so
foundational and recently-changed ones land near the front without the order being identical every
day. It never changes the review intervals: a card you know still backs off to 16 days however
load-bearing it is.

**`look` is the route, not the citation.** `anchor` names the one place the fact is defined and is
what drift tracks. `look` is where you would go to answer the question yourself, and it is shown
**under the question, before the answer**, so you can go and check rather than just read. Every
path must exist, and `drift` reports dead ones.

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

From Claude Code, inside the repo you want carded:

```
/repo-cards:generate     # registers the repo and writes the deck
/repo-cards:update       # brings it back in line with what has been committed since
```

That is the whole setup. `generate` registers the repo itself; the `repo-cards register` CLI command
exists for scripting or for registering without generating.

`update` is the one that matters. It starts from `drift`, verifies every card whose source moved,
and only then considers new ones. With no argument it sweeps every registered repo, so coming back
from a fortnight elsewhere is one command. Asking in plain words works too.

Run `repo-cards` bare and it asks what to review: pick which decks to mix, and press `→` on any of
them to choose topics within it.

```
╭─ Which decks? 2/4 selected ───────────────────────────────╮
│                                                           │
│  ❯ ◉ analytics      77 cards   12 due →   all topics      │
│    ◉ pondaq         84 cards    9 due →   plan-flow       │
│    ○ hermes         40 cards    0 due                     │
│  ↓ 12 more                                                │
│                                                           │
╰─ ↑/↓ move · space toggle · → topics · enter start ────────╯
```

Both lists scroll once they outgrow the terminal, with `page up`/`page down` and `home`/`end`
(or `g`/`G`).

Then one card at a time, sized to its content and centred. `←`/`→` move between cards, `enter`
reveals, `y`/`n` grade.

**Two modes.** `repo-cards test` (the default) hides the answer until you have had a go, and is the
only one that moves a card's box. `repo-cards learn` shows everything at once and grades nothing,
for building the picture or meeting what an update just changed. `l` switches mid-session, because
realising you do not know an area is exactly when you want to stop testing and start reading.

**`last-week` and `last-month` appear on their own**, built from the repository's git history:
the cards whose anchor was touched by a commit in that window, newest first. That is what you want
when you come back after time away, and it reflects what the repo has been doing rather than when
the deck was last edited. Either is dropped when it covers most of the deck, because a window that
means "everything" is not a filter.
Boxes 1 to 5, due after 1, 2, 4, 8 and 16 days; a miss drops to box 1 rather than back one step,
because a fact you have lost is not most of the way to known.

```
╭─ billing ▌payouts · recall ───────────── 4/22  box 2  ★★★ ─╮
│                                                            │
│   ADR-7: enqueue writes an empty payload. Why is the       │
│   outbox row blank, and what does that make it?            │
│                                                            │
│   → src/billing/outbox.py#enqueue                          │
│     the empty payload, and the comment arguing it          │
│   → docs/adr/adr-7-outbox.md                               │
│     the decision, and what it rejected                     │
│                                                            │
├────────────────────────────────────────────────────────────┤
│                                                            │
│   It makes the message a prompt, not a snapshot. The row   │
│   says this invoice changed; the bytes are rendered at     │
│   send time.                                               │
│                                                            │
│   anchor  src/billing/outbox.py#enqueue                    │
│                                                            │
│   #outbox  #invariant                                      │
│                                                            │
╰─ ←/→ · y got it · n missed · q quit  ✓ got it ─────────────╯
```

Repo and topic each get a stable colour, hashed from the name and de-collided so no two you have
registered look alike. Paths are clickable in terminals that support hyperlinks.

**Not every card is a plain question.** `cloze` blanks out the load-bearing words, `order` shuffles
a sequence for you to re-order, and `locate` asks *where you would look* and treats the routes as
the answer. A recall card with good routes is asked that way about one time in six, so the variety
costs no authoring.

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
     ↳ src/billing/outbox.py#enqueue  the empty payload, and the comment arguing it
     ↳ docs/adr/adr-7-outbox.md  the decision, and what it rejected
     ↳ src/billing/tests/test_outbox.py  the test that pins it
     It makes the message a prompt, not a snapshot. The row says this
     invoice changed; the bytes are rendered at send time.
```

Ad-hoc slices need no curation: `--tag outbox,retry` takes several themes and `--grep 'idempoten'`
searches question, answer, anchor and tags. Both work on `review` and `brief`.

`drift` is the triage the update starts from, across every repo at once:

```
$ repo-cards drift

  repo                  commits  verify  routes  dead  new files   state
  billing                    12       7       3     1          4   behind
  pondaq                      5      10       0     -         11   behind
  hermes                      -       -       -     -          -   up to date
  vpn                         -       -       -     -          -   no deck

  2 deck(s) behind. Detail: repo-cards drift --repo <name>   (--full for all)
  1 repo(s) registered with no deck: vpn
```

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
--- cards whose `look` route changed (3) : directions may be stale ---
--- paths that no longer exist (1) : FIX THESE ---
  settle-is-one-way             src/billing/queue.py

--- changed files no card points at (3) : CANDIDATES ---
  src/billing/webhooks.py
```

## Commands

| | |
|---|---|
| `repo-cards` | everything due, across every registered repo |
| `brief` | read an area end to end, in order, writing no state |
| `--repo N` `--tag a,b` `--grep RE` `--topic T` `--priority 1` | narrow to a repo, themes, a search, a topic or a tier |
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
- **Churn is measured, not declared.** A card whose anchor has been edited twenty times this year
  outranks one pointing at a decision nobody has revisited in three, because that is where being
  wrong costs something today. One `git log` per repo, no field to maintain.
- **Priority is weighted, with a starvation guard.** A card's score also falls the longer it stays
  overdue, so the tail cannot be permanently outranked. Simulated over 180 days at 15 cards a day
  across eight decks, weighting alone left 455 of 640 cards never seen; with the guard, none.

MIT.
