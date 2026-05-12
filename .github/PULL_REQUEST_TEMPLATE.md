<!--
Thanks for the contribution. Please fill out the sections below. PRs
with empty descriptions or missing checks will not be reviewed.
-->

## What

<!-- One paragraph: what does this PR do, in plain language? -->

## Why

<!--
The motivation. Link to an issue, an ADR in `.codex/decisions/`, or
the user behaviour that prompted the change. "Refactor" is not a why;
"the orchestrator could not stream results past 30s" is.
-->

## How

<!--
The mechanism. Note any non-obvious choices (algorithms, schema
changes, library swaps) so a reviewer can understand the trade-offs.
-->

## Testing

<!--
What did you run, locally, and what did you see? Paste output.
- backend:  `cd backend && PYTHONPATH=. ../.venv/bin/python -m unittest discover -s tests`
- frontend: `cd frontend && npm run build`
- e2e:      `make stack && make smoke`
-->

## Pre-merge checklist

- [ ] Every commit is **DCO sign-off**ed (`git commit -s`)
- [ ] Every commit is **GPG/SSH signed** (green "Verified" badge)
- [ ] Branch is rebased on the latest `main`
- [ ] Backend tests pass (`make test`)
- [ ] Frontend builds (`cd frontend && npm run build`)
- [ ] If this PR touches `auth/`, `services/encryption.py`, an exporter,
      an MCP server, or a jurisdiction pack — a test was added or
      updated
- [ ] If this PR adds a new dependency, the license is noted in
      `NOTICE`
- [ ] The PR title follows Conventional Commits
      (`feat(scope): …` / `fix(scope): …` / `chore(scope): …` / …)

## Trademark / brand confirmation

- [ ] This PR does not change the project name, mark, or domains. If
      it does, I have read `TRADEMARK.md` and have prior written
      permission.
