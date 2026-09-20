---
description: Generate a spaced-repetition card deck for this repository
---

Generate a repo-cards deck for the repository in the current working directory, or for
`$ARGUMENTS` if a path or name was given.

**First load the `repo-cards` skill** (Skill tool, `repo-cards:repo-cards`). It holds the bar for
what earns a card, the card format, the anchoring rules and the topic format. Everything below
assumes it, and a deck written without it will be a summary rather than a deck.

Then:

1. **Register the repo yourself if it is not already** (`repo-cards repos` to check, then
   `repo-cards register <repo root>`). The caller should not have to do this first: running this
   command inside a fresh repo is the whole setup. `repo-cards home` shows where the deck goes.
   Nothing is written into the repo itself.
2. **Read `repo-cards feedback --repo <name>` first** if this repo has a deck history. It is every
   objection a reader has ever raised against its cards and what was done about each one, which is
   the only input to a deck that cannot be derived from the repo. Cards retired as *not useful*
   mark ground that does not earn a card, *badly asked* marks questions this codebase phrases
   badly, and *never was true* marks an area a previous pass misread. Do not write again what the
   log says was thrown away, and report which feedback you acted on.
3. Read the repo's own orientation: `CLAUDE.md`, `README.md`, the docs index, any ADR folder
   or decision register. That is where the load-bearing knowledge already is. Only derive it from
   code and `git log` when no such record exists.
4. Draft the cards against the skill's bar, grouped by theme with `# ---` section comments. Aim for
   60 to 80, and say so before exceeding that.
5. Propose four to eight topics in the same pass, including an `orientation` topic.
6. Set `repo`, `description`, `last_update_sha` (current short HEAD) and `last_update_date`. Do not
   put the repo root in the deck; that lives in the registry.
7. Validate with `repo-cards check --repo <name>` and fix what it reports. Errors are defects: a
   route that 404s, a duplicate id, a topic naming a card that does not exist. Warnings are the
   deck's own bar, so fix the ones that are right and name the ones you are keeping. Do not report
   a deck as finished while `check` still exits 1.
8. Report the card count, the tag breakdown, the topics, and anything deliberately left out.

If a deck already exists for this repo, stop and say so: `/repo-cards:update` is the command that
keeps an existing deck current without discarding review progress.

When the user has asked for a regenerate anyway, because `drift` reported the deck too far behind
to verify card by card, **keep the ids of cards whose fact survives**: an id is what carries the
review box. Then run `repo-cards check --repo <name>`, which lists every state entry no card claims
and guesses which new id it belongs to, and hand each one back with
`repo-cards adopt --repo <name> old-id=new-id`. Report how many boxes were preserved and how many
were genuinely retired.
