---
description: Update this repository's card deck against everything committed since it was generated
---

Update the repo-cards deck for the repository in the current working directory, or for `$ARGUMENTS`
if a repo name was given.

**First load the `repo-cards` skill** (Skill tool, `repo-cards:repo-cards`) for the card bar, the
card format and the anchoring rules.

Start with `repo-cards drift --repo <name>`. It reports the commits since `last_update_sha`, the
files changed, cards whose anchor changed, cards where the file moved but the anchored symbol did
not, and changed files no card is anchored to.

Then, in this order:

1. **Verify before adding.** For every card the report flags hot, read the anchor as it is *now* and
   decide: still true (leave it, id included), now wrong (rewrite the answer, keep the id so the
   review box survives), or no longer a fact (retire it).
   **This is the point of the command.** A deck that only grows is a deck that quietly starts lying,
   and a stale card is worse than a missing one because it gets acted on confidently.
2. **Read the commit messages, not just the diff.** A commit that reverses an earlier decision is
   the highest-value card in an update, and the card it contradicts must be retired in the same
   pass.
3. **Then consider new cards** from the uncovered-files list, against the same bar. Most changed
   files warrant no card.
4. **Fix the topics.** A retired card leaves a dangling id, which `repo-cards topics` flags. A new
   card usually belongs in an existing topic; a genuinely new feature area may want its own.
5. Bump `last_update_sha` to the current short HEAD and `last_update_date` to today.
6. Re-validate as for generation, then report: verified, rewritten, retired, added, topics touched,
   with one line of reasoning each. Short enough to read in a minute.

Never edit or regenerate `state.json`. A card that keeps its id keeps its review box; if a card's
meaning has changed enough that its history would mislead, give it a new id instead.

If the deck has drifted hundreds of commits, say so and offer a regenerate rather than pretending an
incremental pass covered it.
