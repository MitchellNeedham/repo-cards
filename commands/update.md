---
description: Update this repository's card deck against everything committed since it was generated
---

Bring card decks back in line with what has been committed since they were written.

**First load the `repo-cards` skill** (Skill tool, `repo-cards:repo-cards`) for the card bar, the
card format and the anchoring rules.

**Scope.** `$ARGUMENTS` names a repo, in which case update that one. With no argument, update the
repo the working directory is in if it has a deck; if it does not, sweep every registered repo.

**Sweeping.** Run `repo-cards drift` with no `--repo`. It prints one line per repo: commits behind,
cards to verify, changed files no card covers, and the decks that do not exist yet. Then:

* Report that table before doing anything, so the size of the job is visible up front.
* Work through the repos that are `behind`, most cards-to-verify first, one at a time, running
  `repo-cards drift --repo <name>` for the detail on each.
* **Updating several repos is expensive.** If more than three are behind, do the worst one, report
  it, and ask before continuing rather than burning the session on all of them.
* Repos listed as `no deck` are not this command's job. Name them once and move on; they want
  `/repo-cards:generate` run from inside them.

For each repo in scope, `repo-cards drift --repo <name>` reports the commits since
`last_update_sha`, the files changed, cards whose anchor changed, cards where the file moved but
the anchored symbol did not, and changed files no card is anchored to.

Then, in this order:

1. **Start with the flagged cards.** `repo-cards drift` lists them first, under *cards you flagged
   during review*. They were marked with `f` by somebody who met the card and did not believe it,
   which beats any diff as a signal. Verify, rewrite or retire each one, then clear them with
   `repo-cards flags --clear --repo <name>` so the next pass does not re-read them.
2. **Rewrite what keeps being missed.** `drift` lists cards missed three or more times under
   *cards missed 3+ times*. That is a defect in the writing, not a hard fact: split it, or make the
   question answerable rather than recognisable. This is the only step that improves a card's
   quality rather than its currency, so do not skip it because git had nothing to say.
3. **Verify before adding.** For every card the report flags hot, read the anchor as it is *now* and
   decide: still true (leave it, id included), now wrong (rewrite the answer, keep the id so the
   review box survives), or no longer a fact (retire it). **Stamp every card you read with
   `verified: <short HEAD>`**, kept or rewritten, so the next pass measures it from here rather
   than from the deck's baseline and stops re-reading the same hot files.
   **This is the point of the command.** A deck that only grows is a deck that quietly starts lying,
   and a stale card is worse than a missing one because it gets acted on confidently.
4. **Read the commit messages, not just the diff.** A commit that reverses an earlier decision is
   the highest-value card in an update, and the card it contradicts must be retired in the same
   pass.
5. **Then consider new cards** from the uncovered-files list, against the same bar. Most changed
   files warrant no card.
6. **Fix the topics.** A retired card leaves a dangling id, which `repo-cards topics` flags. A new
   card usually belongs in an existing topic; a genuinely new feature area may want its own.
7. Bump `last_update_sha` to the current short HEAD and `last_update_date` to today. Cards you did
   not reach keep whatever `verified` stamp they had, which is what makes a partial pass honest.
8. Re-validate as for generation, then report: verified, rewritten, retired, added, topics touched,
   with one line of reasoning each. Short enough to read in a minute.

Never edit or regenerate `state.json`. A card that keeps its id keeps its review box; if a card's
meaning has changed enough that its history would mislead, give it a new id instead.

If the deck has drifted hundreds of commits, say so and offer a regenerate rather than pretending an
incremental pass covered it.
