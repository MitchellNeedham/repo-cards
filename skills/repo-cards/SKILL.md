---
name: repo-cards
description: Generate and maintain a spaced-repetition Q&A card deck for a codebase, so a repo can be re-entered without re-reading it. Use when asked to make, generate, update or refresh repo cards, flashcards or a deck for a repository, or when asked what changed since the deck was last updated. Also covers reviewing cards and registering a repo.
---

# Repo cards

Cards that keep a repo's **load-bearing knowledge** available across context switches, for someone
working across many repositories. Reviewed on a Leitner schedule by the `repo-cards` command.

The deck is not a summary of the repo. It is the set of facts where **being wrong is expensive**.

**This file is the shared reference.** `/repo-cards:generate` and `/repo-cards:update` are the
entry points and both load it first; the two Mode sections below are their workflows. Reached
directly (someone asks in plain words), work out which mode they mean and follow it.

## The command

Everything mechanical is done by `repo-cards`, installed on PATH by this plugin's `install.sh`.
If it is not found, fall back to `"$CLAUDE_PLUGIN_ROOT/bin/repo-cards"` inside a Bash call (the
variable is set in the environment for commands, and is *not* expanded in this file's prose).

```bash
repo-cards home                 # where decks, state and notes live on this machine
repo-cards repos                # what is registered
repo-cards register PATH        # add a repo (--name to override the deck name)
repo-cards drift --repo NAME    # what changed since the deck was generated
repo-cards catchup --repo NAME  # what moved since you last reviewed it. Read-only
repo-cards check --repo NAME    # validate a deck. Exit 1 if anything is broken
repo-cards adopt --repo NAME old=new    # give a renamed card the old id's review history
repo-cards export --repo NAME   # write the deck out, to share or to commit
repo-cards import PATH          # install a deck somebody else wrote
repo-cards stats                # due counts, box distribution, stickiest cards
repo-cards flags                # cards flagged as suspect during review
repo-cards flags --clear        # clear them, once an update has dealt with them
repo-cards list --repo NAME     # every card with its box and due date
repo-cards topics               # what topics a deck defines
repo-cards brief --topic NAME   # read one area end to end; writes no state
```

## Where things live

Nothing is ever written into the repo being carded. `repo-cards home` prints the real paths;
the layout is:

```
<data home>/
  registry.json            name -> repo root, per machine
  <name>/
    deck.yaml              the cards. Content only
    state.json             Leitner state, keyed by card id. NEVER edit or regenerate this
    notes/                 long-form notes for this repo, if any
```

A deck is content and nothing else: no paths, no schedule, no machine. `repo-cards export` writes
one out (a directory carries `notes/` with it) and `repo-cards import` installs it, keeping whatever
review history this machine already had for the ids that survive. That is how a deck reaches a
teammate or gets committed to the repo it describes. The importing machine must have the repo
registered, and cross-repo refs need the other repos registered under the same names, which
`export` warns about. Suggest it when somebody asks how to share a deck or onboard somebody with
one, not otherwise.

`<data home>` is platform-native: `~/.local/share/repo-cards` on Linux,
`~/Library/Application Support/repo-cards` on macOS, `%LOCALAPPDATA%\repo-cards` on Windows.
`REPO_CARDS_HOME` overrides it, and `XDG_DATA_HOME` is honoured on every platform.

Content and state are separate files **so regenerating a deck never costs review progress**. A card
that keeps its id keeps its box. Retiring a card leaves an orphaned state entry, which is ignored.

That promise is only as good as the ids, and a regenerate is exactly where they slip: reword one
while rewriting a deck and that card is back in box 1 with no warning, because an orphaned entry is
ignored rather than reported. `repo-cards check` lists every state entry no card claims, with the
closest unclaimed id and how alike the two are, and `repo-cards adopt --repo NAME old=new` hands the
history over. **Run `check` after any regenerate** and deal with the orphans before reporting the
deck as done.

## What earns a card

One test, applied honestly:

> **If I believed the opposite of this card, what would it cost me?**

A card earns its place when the answer is: I would write a defect, reopen a decision that was
already settled with reasons, or lose an hour to something nobody wrote down. Everything else is
recognition-level knowledge that belongs in a document, not a deck.

**Include:**

* **Invariants.** Rules where a violation is a defect rather than a preference.
* **Load-bearing splits.** Which component owns what, and *why the boundary is where it is*. A
  boundary someone can talk themselves across is the expensive kind. Where the two sides live in
  different repos, anchor across with `other-repo::path` (see `look` below).
* **Reasoning behind decisions.** Not the verdict, the argument. The verdict alone does not stop
  the decision being reopened. Where the repo has stable decision ids cited in code comments
  (`ADR-7`, `RFC-12`, `D-3`), build cards on them: they are stable, they are already the vocabulary,
  and knowing them makes a code comment resolvable in one hop.
* **Counter-intuitive mechanics on the hot paths.** The places where the obvious implementation is
  wrong and the code says so. These are usually the best cards in a deck, because the docstring
  already contains the argument.
* **Rejected alternatives**, where the repo records them. "Why not X" prevents more waste than
  "why Y".
* **Vocabulary** a newcomer cannot infer, especially domain terms that drive design decisions.
* **Traps that cost time.** The VPN that must be on, the role that lacks DDL rights.

**Exclude:**

* Anything a `grep` answers in ten seconds: file locations, function signatures, command flags.
* API surface listings, directory trees, dependency lists.
* Anything that changes under ordinary refactoring. That is guaranteed rot for no benefit.
* Facts with no consequence. "There are five Django apps" is trivia; "services never speak HTTP,
  because the same operation is called by a user, by the scheduler and by a backfill" is a card.
* Two cards where one will do. If two facts are always recalled together, they are one card.

**Sizing.** However many cards clear the bar, and no more. Do not pad a deck to a number, and do not
stop at one: a repo that supports 30 honest cards should get 30, and one with a decade of
load-bearing decisions can carry several hundred. The bar is the limit, not a count. Review is
ordered by priority, churn and how overdue a card is, so a large deck stays reviewable in short
sessions rather than demanding to be finished.

## Writing a card

```yaml
- id: outbox-row-is-a-prompt          # stable kebab-case slug; state.json keys on it
  tags: [outbox, invariant]           # lowercase; --tag filters on these
  priority: 1                         # 1 foundational, 2 core (default, omit it), 3 detail
  anchor: src/billing/outbox.py#enqueue   # where the fact is DEFINED. One path, drift-tracked
  verified: 4f2a91c                      # the commit this card was last checked against
  look:                               # how you would go and check. Path: what you would find
    src/billing/outbox.py#enqueue: the empty payload, and the comment arguing it
    src/billing/sender.py#render: where the bytes are actually built
    docs/adr/adr-7-outbox.md: the decision, and what it rejected
  q: >-
    ADR-7: enqueue writes an empty payload. Why is the outbox row blank, and what does that make it?
  a: >-
    It makes the message a prompt, not a snapshot. The row says this invoice changed; the bytes are
    rendered at send time from the invoice as it is then, so a queued payload would go out stale.
```

### priority

**1 foundational**: being wrong causes a defect or reopens a settled decision. The invariants, the
load-bearing splits, the vocabulary that drives design. Expect roughly a quarter of a deck.
**2 core**: the default, so omit it. **3 detail**: narrow mechanics and ops specifics, real but
cheap to be wrong about.

Priority decides what surfaces first in a capped session; it does not change the review intervals,
so a card you demonstrably know still backs off however important it is. Recently added or rewritten
cards get the same kind of boost, which is why `added:` and `updated:` are worth stamping.

**Churn is measured, not declared.** The CLI counts commits touching each card's anchor over the
last 180 days and boosts the ones that are moving, normalised against the deck's own distribution.
A card anchored on a file being edited weekly is knowledge at risk; one anchored on a decision
nobody has touched in three years is settled. There is no field for this and nothing to maintain,
but it is a reason to **anchor on the file that actually changes** rather than a stable summary of
it.

### kind

Most cards are plain recall and need no `kind:`. The others exist because asking a different shape
of question exercises a different thing, and `locate` in particular is what makes somebody learn
the repo rather than the answer.

```yaml
kind: cloze        # blanks are marked in the answer with {{double braces}}
a: >-
  The ledger is {{authoritative}}; the projection is written {{in the same transaction}}.

kind: locate       # "where would you look?" - the card's `look` routes ARE the answer
                   # needs no extra fields, but the card must carry good routes

kind: order        # put the steps in sequence; shown shuffled, revealed in order
sequence: [propose, approve, publish, apply]
a: >-
  Optional commentary shown under the correct order.
```

A plain recall card carrying two or more routes is also asked as `locate` about one time in six, so
the variety costs no extra authoring. Reach for an explicit `kind:` when the shape genuinely fits:
`cloze` for a rule with two or three load-bearing words in it, `order` for a pipeline or lifecycle.

### look

`anchor` is one path, the place the fact is *defined*; drift tracks it precisely and churn is
measured on it. `look` is the **route you would take to answer the question yourself**, and it is
shown *under the question, before the answer*, so it can be followed, and it is what teaches the repo rather
than the fact: the decision that argued it, the test that pins it, the caller that shows why it
matters. Two or three entries, each saying what is there, not just where.

Prefer a mix of kinds over three files in the same directory: a decision record, an implementation,
and the test or spec that holds it to account. Every path must exist; `drift` reports dead ones as
`FIX THESE` and a route that 404s teaches nothing.

**The question must be answerable from memory, not recognition.** "Is the event log the source of
truth?" is worthless: yes is guessable. "State ADR-7, including the transaction rule" is a card.
Prefer *why*, *what breaks if not*, and *what was rejected* over *what*.

**The answer is one to four sentences.** If it needs more, it is two cards or it is a document.
Where the repo phrases something better than you would, quote the repo: its wording is what the
reader will meet again in a docstring.

**`verified` is what keeps an update from re-reading the same cards forever.** It names the commit
the card was last checked against, and drift measures that card from there rather than from the
deck's baseline. Without it, a card anchored on a file that moves every week is flagged in every
single pass, the pass grows tedious, and an update that cries wolf stops being run. Stamp it on
every card you *read and kept*, not only the ones you rewrote: checking and finding nothing wrong
is the work that the stamp records. A stamp naming a commit the repo has never heard of, after a
rebase, falls back to the deck's baseline rather than clearing the card.

**The anchor is what makes the deck maintainable.** One repo-relative path per card, naming where
the fact is *defined*, not everywhere it is mentioned. An anchor to a file that changes constantly
is a signal the card is too low-level. Cards drawn from a whole-repo convention can anchor on
`CLAUDE.md` or the docs index.

**Always add `#symbol` when the fact lives in one function, class or constant.** `drift` narrows a
file-level hit by checking whether the symbol appears in the diff, and splits its report into cards
to verify and cards where the file moved but the symbol did not. Without symbols, one commit to a
large module flags every card drawn from it and the update drowns in false positives. Measured on a
real 17-commit window, this was the difference between 28 cards to verify and 16.

**A path may name another registered repo**, written `name::path/to/thing#symbol`, where `name`
is what `repo-cards repos` calls it. That is for the knowledge that lives *between* two services:
the contract, and the assumption each side makes about the other. Drift, churn and the computed
recent topics all follow the qualifier, so a card in one deck is flagged for verification when the
other repo moves under it, and `repo-cards drift` reports a deck as `linked moved` when its own
repo is untouched but a linked one is not. Use it for facts that genuinely span a boundary, and
check the other repo is registered first: a ref naming an unregistered repo is reported as broken,
because nobody can follow it.

Use YAML `>-` for prose and `|-` where line structure matters (tables, ordered lists). Avoid
unquoted colons in plain scalars.

## Topics

A topic is a **curated reading order**: the cards for one feature, in the order that tells the
story. `repo-cards brief --topic NAME` reads one end to end and writes no state, which is what
somebody does the night before a meeting about that feature.

```yaml
topics:
  plan-flow:
    description: How a plan moves from proposed through applied, and what watches it
    notes: notes/plan-lifecycle.md     # optional, relative to the deck directory
    cards:                             # ordered, and a card may appear in several topics
      - plan-five-states
      - plan-three-triggers
      - plan-version-allocation
```

**Order is the point.** A topic is read to rebuild a mental model, and the story runs in a
direction: what triggers it, then what it writes, then what carries it, then what watches it.
Alphabetical or tag order teaches nothing that a `--tag` filter would not.

**Propose four to eight topics when generating a deck.** Cover the areas somebody would actually
hold a meeting about, and always include an `orientation` topic for coming back after months away.
Point `notes:` at a long-form note where one exists.

A topic is not the only way to slice a deck, and not every slice needs one. `--tag a,b` and
`--grep PATTERN` need no curation and handle the ad-hoc case; a topic earns its place when the
feature spans tags or when the order matters.

## Mode: generate

1. `repo-cards register <repo root>` first, so the deck has a home. Confirm the path with
   `repo-cards home` if the user asks where things went.
2. Read the repo's own orientation: `CLAUDE.md`, `README.md`, the docs index, any ADR folder or
   decision register. **This is where the load-bearing knowledge already is.** A repo with a
   decisions register has done most of the work for you.
3. For a repo with no such record, derive it: the invariants are implicit in what the tests assert
   and what the code comments defend, and `git log` shows what has been fixed twice.
4. Draft cards against the bar above. Group by theme with `# ---` section comments.
5. Write the deck to `<data home>/<name>/deck.yaml` with `repo`, `description`,
   `last_update_sha` (current short HEAD) and `last_update_date`. Do **not** put the repo root in
   the deck: that is machine-specific and lives in the registry.
6. **Propose topics** in the same pass, per the section above. They are cheap while the whole deck
   is in front of you and tedious to retrofit.
7. **Validate with `repo-cards check --repo <name>` and fix what it reports.** It enforces what
   this file describes: duplicate ids, missing fields, topic ids that resolve to nothing, routes
   and notes files that do not exist, cross-repo refs naming an unregistered repo, cloze cards with
   no blanks. It also warns where the deck misses its own bar: anchors with no `#symbol`, questions
   answerable yes or no, answers longer than four sentences, cards with fewer than two routes.
   Errors are defects and must be fixed. Warnings are judgement, so fix the ones that are right and
   say why you are keeping the rest.
8. Report the card count, the tag breakdown and the topics, and name anything deliberately left
   out.

## Mode: update

Run `repo-cards drift --repo <name>` first. It prints the commits since `last_update_sha`, the
files changed, **cards whose anchor changed**, cards where the file moved but the symbol did not,
and **changed files no card is anchored to**.

Then, in order:

1. **Start with the cards the reader flagged.** `f` during review marks a card the reader did not
   believe, and that is a stronger signal than any commit: they met the card, knew the area, and
   said it was wrong. Verify each one, rewrite or retire it, and clear the flags with
   `repo-cards flags --clear --repo <name>` once they are dealt with. A flag left standing after an
   update is worse than none, because the next pass re-reads a card that is now fine.
2. **Rewrite the cards nobody can hold on to.** `drift` lists cards missed three times or more.
   That is almost never a hard fact: it is two facts under one id, or a question that can be
   recognised rather than answered. Split it or rewrite the question. Keep the id if the fact is
   the same one; give it a new id if you have genuinely changed what is being asked, so its
   history does not flatter the new card.
3. **Verify before adding.** For every card the drift report flags hot, read the anchor as it is
   *now* and decide: still true (leave it, id included), now wrong (rewrite the answer, keep the id
   so the box survives), or no longer a fact (retire it).
   **This step is the point of the update.** A deck that only grows is a deck that quietly starts
   lying.
4. **Read the commit messages, not just the diff.** A commit like "Drop RabbitMQ, which nobody can
   say what was wrong with" is a decision with reasoning, which is exactly what a card is for. A
   decision *reversed* is the highest-value card in an update, and the old card must be retired in
   the same pass.
5. **Then consider new cards** from the uncovered-files list, against the same bar. Most changed
   files warrant no card.
6. **Fix the routes.** `drift` reports two things beside the anchors: cards whose `look` route
   changed, where the fact is probably intact but the directions moved, and **paths that no longer
   exist**, which are defects and should be repaired in every pass.
7. **Fix the topics.** A retired card leaves a dangling id, which `repo-cards topics` flags; a new
   card usually belongs in an existing topic, and a genuinely new feature area may want its own.
8. **Stamp what changed, and what you checked.** A rewritten card gets `updated: <today>`; a new
   one gets `added: <today>`. That is the only record of recency, since the deck is not in git, and
   it is what floats new material to the front of a session. **Every card you read in this pass
   also gets `verified: <short HEAD>`**, whether or not you changed it, so the next update measures
   it from here instead of from the deck's baseline.
9. Bump `last_update_sha` and `last_update_date`.
10. Re-validate with `repo-cards check --repo <name>` and report: verified, rewritten, retired,
   added, topics touched, one line of reasoning each. Short enough to read in a minute.

`drift` decides this for you rather than leaving it to judgement: past roughly 60 commits, or once
a quarter of the cards point at paths that no longer exist, it reports that the deck has drifted far
enough that a regenerate beats verifying it card by card. Say so and offer `/repo-cards:generate`
rather than pretending an incremental pass covered it.

## Reviewing

The user drives this themselves, but if asked:

```bash
repo-cards                  # due cards across every registered repo
repo-cards --repo billing   # one repo
repo-cards --tag invariant  # one theme
repo-cards --limit 15       # cap the session
repo-cards --new            # only cards never seen
repo-cards --all            # ignore due dates (cram)
repo-cards --tag a,b        # several themes at once
repo-cards --grep PATTERN   # regex over question, answer, anchor and tags
repo-cards --topic NAME     # one curated topic, graded as usual
repo-cards --priority 1     # drill only the foundational cards
repo-cards --no-pick        # skip the picker and take everything due
repo-cards learn            # everything visible, nothing graded
repo-cards test             # the default: answer hidden, self-graded
```

**`last-week` and `last-month` are computed topics**, not ones to write. Membership is "this
card's anchor was touched by a commit in that window", read from git, newest first, counting work
merged in that window as landing then rather than when the branch was written. They need no
maintenance and cannot go stale, but they are a reason to **anchor on the file that actually
changes** rather than a stable summary of it: an anchor nothing commits to will never appear in
either.

Run bare in a terminal, `repo-cards` opens a picker: choose which decks to mix, and drill into any
of them with `→` to pick topics. Both lists scroll, with paging and `home`/`end`. In the session, `←`/`→` move between cards (there is no skip),
`enter` reveals, `y`/`n` grade. File paths are clickable where the terminal supports it.

**`f` flags a card as suspect**, in either mode, and grades nothing. It is the answer to "this card
is wrong now", which is a different thing from "I could not remember this" and deserves a different
response: a miss is a scheduling fact, a flag is a defect in the deck. Flags are the first section
of `repo-cards drift` and the first step of an update, because a reader who knows the area and does
not believe the card is a better signal than any diff.

Flagging asks **why**, and the answer is carried into the report in the reader's own words. Take it
seriously: "rendered in the worker now, not at send time" points straight at what to read, where
the flag alone only says which card to doubt. The note is raised after the flag, so an abandoned
prompt still leaves the flag standing.

`brief` is the read-only counterpart, in deck or topic order rather than shuffled, for rebuilding a
mental model rather than testing it. Suggest it when somebody says they have a meeting about an
area, or are returning to a repo after a while.

`repo-cards catchup` answers the other returning question: not what the deck owes the repo, which
is `drift` and is work for an update, but **what the repo did while you were on something else**.
Its baseline is the last time you *reviewed* the deck, and it prints the commits since then grouped
under the cards that sit on what they touched, newest first. It writes no state and needs no model,
so suggest it before offering an update: somebody coming back after three weeks usually wants to
read for a minute, not spend a session regenerating cards.

Boxes 1 to 5, due after 1, 2, 4, 8 and 16 days. A miss returns a card to box 1 rather than back one
step, because a fact you have lost is not most of the way to known.

## Notes

* `repo-cards` is a `uv` script with an inline dependency on `pyyaml`. It needs `uv` on PATH and
  has no virtualenv of its own. Its tests run with
  `uv run --with pytest --with pyyaml pytest tests/ -q` from the plugin's own checkout.
* Never regenerate or hand-edit `state.json`. If a card's meaning changes enough that its history is
  misleading, give it a new id, which resets it honestly. `repo-cards adopt` is the one supported
  way to move an entry, and it exists for the opposite case: the id changed but the fact did not.
* `repo-cards stats` shows the stickiest cards by lapse count, and `drift` lists the ones missed
  three times or more as cards to rewrite. That many lapses usually means the card is badly written
  rather than the fact being hard: it is probably two facts, or the question is recognisable rather
  than answerable. Offer to rewrite it.
