---
name: repo-cards
description: Generate and maintain a spaced-repetition Q&A card deck for a codebase, so a repo can be re-entered without re-reading it. Use when asked to make, generate, update or refresh repo cards, flashcards or a deck for a repository, or when asked what changed since the deck was last updated. Also covers reviewing cards and registering a repo.
---

# Repo cards

Cards that keep a repo's **load-bearing knowledge** available across context switches, for someone
working across many repositories. Reviewed on a Leitner schedule by the `repo-cards` command.

The deck is not a summary of the repo. It is the set of facts where **being wrong is expensive**.

## The command

Everything mechanical is done by `repo-cards`, installed on PATH by this plugin's `install.sh`.
If it is not found, fall back to `"$CLAUDE_PLUGIN_ROOT/bin/repo-cards"` inside a Bash call (the
variable is set in the environment for commands, and is *not* expanded in this file's prose).

```bash
repo-cards home                 # where decks, state and notes live on this machine
repo-cards repos                # what is registered
repo-cards register PATH        # add a repo (--name to override the deck name)
repo-cards drift --repo NAME    # what changed since the deck was generated
repo-cards stats                # due counts, box distribution, stickiest cards
repo-cards list --repo NAME     # every card with its box and due date
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

`<data home>` is platform-native: `~/.local/share/repo-cards` on Linux,
`~/Library/Application Support/repo-cards` on macOS, `%LOCALAPPDATA%\repo-cards` on Windows.
`REPO_CARDS_HOME` overrides it, and `XDG_DATA_HOME` is honoured on every platform.

Content and state are separate files **so regenerating a deck never costs review progress**. A card
that keeps its id keeps its box. Retiring a card leaves an orphaned state entry, which is ignored.

## What earns a card

One test, applied honestly:

> **If I believed the opposite of this card, what would it cost me?**

A card earns its place when the answer is: I would write a defect, reopen a decision that was
already settled with reasons, or lose an hour to something nobody wrote down. Everything else is
recognition-level knowledge that belongs in a document, not a deck.

**Include:**

* **Invariants.** Rules where a violation is a defect rather than a preference.
* **Load-bearing splits.** Which component owns what, and *why the boundary is where it is*. A
  boundary someone can talk themselves across is the expensive kind.
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

**Sizing.** Default to **60 to 80 cards** for a substantial repo, and say so before going above it.
A deck that cannot be reviewed in ten minutes a day gets abandoned, and an abandoned deck is worse
than none because its staleness is invisible. A repo that only supports 20 honest cards should get
20.

## Writing a card

```yaml
- id: outbox-row-is-a-prompt          # stable kebab-case slug; state.json keys on it
  tags: [outbox, invariant]           # lowercase; --tag filters on these
  anchor: src/billing/outbox.py#enqueue   # repo-relative path, plus #symbol where it applies
  q: >-
    ADR-7: enqueue writes an empty payload. Why is the outbox row blank, and what does that make it?
  a: >-
    It makes the message a prompt, not a snapshot. The row says this invoice changed; the bytes are
    rendered at send time from the invoice as it is then, so a queued payload would go out stale.
```

**The question must be answerable from memory, not recognition.** "Is the event log the source of
truth?" is worthless: yes is guessable. "State ADR-7, including the transaction rule" is a card.
Prefer *why*, *what breaks if not*, and *what was rejected* over *what*.

**The answer is one to four sentences.** If it needs more, it is two cards or it is a document.
Where the repo phrases something better than you would, quote the repo: its wording is what the
reader will meet again in a docstring.

**The anchor is what makes the deck maintainable.** One repo-relative path per card, naming where
the fact is *defined*, not everywhere it is mentioned. An anchor to a file that changes constantly
is a signal the card is too low-level. Cards drawn from a whole-repo convention can anchor on
`CLAUDE.md` or the docs index.

**Always add `#symbol` when the fact lives in one function, class or constant.** `drift` narrows a
file-level hit by checking whether the symbol appears in the diff, and splits its report into cards
to verify and cards where the file moved but the symbol did not. Without symbols, one commit to a
large module flags every card drawn from it and the update drowns in false positives. Measured on a
real 17-commit window, this was the difference between 28 cards to verify and 16.

Use YAML `>-` for prose and `|-` where line structure matters (tables, ordered lists). Avoid
unquoted colons in plain scalars.

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
6. Validate before finishing: parse the YAML, check for duplicate ids, and check every card has
   `id`, `q`, `a`, `anchor`, `tags`.
7. Report the card count and tag breakdown, and name anything deliberately left out.

## Mode: update

Run `repo-cards drift --repo <name>` first. It prints the commits since `last_update_sha`, the
files changed, **cards whose anchor changed**, cards where the file moved but the symbol did not,
and **changed files no card is anchored to**.

Then, in order:

1. **Verify before adding.** For every card the drift report flags hot, read the anchor as it is
   *now* and decide: still true (leave it, id included), now wrong (rewrite the answer, keep the id
   so the box survives), or no longer a fact (retire it).
   **This step is the point of the update.** A deck that only grows is a deck that quietly starts
   lying.
2. **Read the commit messages, not just the diff.** A commit like "Drop RabbitMQ, which nobody can
   say what was wrong with" is a decision with reasoning, which is exactly what a card is for. A
   decision *reversed* is the highest-value card in an update, and the old card must be retired in
   the same pass.
3. **Then consider new cards** from the uncovered-files list, against the same bar. Most changed
   files warrant no card.
4. Bump `last_update_sha` and `last_update_date`.
5. Re-validate and report: verified, rewritten, retired, added, one line of reasoning each. Short
   enough to read in a minute.

If the deck has drifted a long way (hundreds of commits), say so and offer a regenerate rather than
pretending an incremental pass covered it.

## Reviewing

The user drives this themselves, but if asked:

```bash
repo-cards                  # due cards across every registered repo
repo-cards --repo billing   # one repo
repo-cards --tag invariant  # one theme
repo-cards --limit 15       # cap the session
repo-cards --new            # only cards never seen
repo-cards --all            # ignore due dates (cram before a meeting)
```

Boxes 1 to 5, due after 1, 2, 4, 8 and 16 days. A miss returns a card to box 1 rather than back one
step, because a fact you have lost is not most of the way to known.

## Notes

* `repo-cards` is a `uv` script with an inline dependency on `pyyaml`. It needs `uv` on PATH and
  has no virtualenv of its own.
* Never regenerate or hand-edit `state.json`. If a card's meaning changes enough that its history is
  misleading, give it a new id, which resets it honestly.
* `repo-cards stats` shows the stickiest cards by lapse count. Three or more lapses usually means
  the card is badly written rather than the fact being hard: it is probably two facts, or the
  question is recognisable rather than answerable. Offer to rewrite it.
