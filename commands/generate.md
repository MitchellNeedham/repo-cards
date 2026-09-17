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
2. Read the repo's own orientation first: `CLAUDE.md`, `README.md`, the docs index, any ADR folder
   or decision register. That is where the load-bearing knowledge already is. Only derive it from
   code and `git log` when no such record exists.
3. Draft the cards against the skill's bar, grouped by theme with `# ---` section comments. Aim for
   60 to 80, and say so before exceeding that.
4. Propose four to eight topics in the same pass, including an `orientation` topic.
5. Set `repo`, `description`, `last_update_sha` (current short HEAD) and `last_update_date`. Do not
   put the repo root in the deck; that lives in the registry.
6. Validate with `repo-cards check --repo <name>` and fix what it reports. Errors are defects: a
   route that 404s, a duplicate id, a topic naming a card that does not exist. Warnings are the
   deck's own bar, so fix the ones that are right and name the ones you are keeping. Do not report
   a deck as finished while `check` still exits 1.
7. Report the card count, the tag breakdown, the topics, and anything deliberately left out.

If a deck already exists for this repo, stop and say so: `/repo-cards:update` is the command that
keeps an existing deck current without discarding review progress.
