# Contributing to Verda

Thanks for considering a contribution. A few things to know before you
open a PR.

## Inbound = outbound (AGPL-3.0)

This project is licensed under the GNU Affero General Public License
v3.0. By submitting a contribution you agree that your contribution is
licensed under the same terms. There is no separate CLA — see the next
section for the lightweight equivalent.

## Developer Certificate of Origin (DCO)

Every commit must carry a `Signed-off-by:` trailer. That trailer is a
binding statement that you wrote (or have the right to contribute) the
code, and that you are licensing it under the same license as the
project. The full text is at https://developercertificate.org/.

The easiest way to add the trailer is the `-s` flag:

```bash
git commit -s -m "feat(scope): add the thing"
```

That appends a line that looks like this to your commit message:

```
Signed-off-by: Your Name <you@example.com>
```

The name and email **must match the values in `git config`** and must
be real (no pseudonyms, no `noreply` aliases). The CI bot enforces this
on every PR. PRs with any unsigned commits will not merge.

If you forgot to sign off the most recent commit:

```bash
git commit --amend --signoff
```

If you forgot on several commits:

```bash
git rebase --signoff HEAD~3   # last 3 commits
```

## Signed commits

The main branch requires GPG- or SSH-signed commits. To enable SSH
signing locally:

```bash
git config gpg.format ssh
git config user.signingkey ~/.ssh/id_ed25519.pub
git config commit.gpgsign true
```

Then add the same key on GitHub under **Settings → SSH and GPG keys →
New SSH key → Key type: Signing key**. Your commits will then show as
**Verified** on the PR.

## Branching

Use a descriptive prefix on your branch:

| Prefix    | When to use                                             |
| --------- | ------------------------------------------------------- |
| `feat/`   | A new user-visible feature                              |
| `fix/`    | A bug fix                                               |
| `chore/`  | Tooling, deps, build, or any non-functional change      |
| `docs/`   | Documentation only                                      |
| `test/`   | Tests or test infrastructure only                       |
| `refactor/` | Restructuring without behaviour change                |
| `perf/`   | Performance improvements                                |
| `ci/`     | CI / GitHub Actions workflow changes                    |

Examples: `feat/precedent-ranking`, `fix/swahili-ocr-encoding`,
`chore/upgrade-fastapi-018`.

## Commit message format

Conventional Commits, single-line summary under 72 characters:

```
type(scope): summary in imperative mood, no trailing period
```

Examples:

- `feat(precedent-linker): rank by recency before topic`
- `fix(auth): refresh JWKS on 401 from upstream`
- `docs(readme): document make smoke output`

A body is welcome; separate it from the subject with a blank line.

## Pull-request checklist

Before requesting review, please confirm:

- [ ] Every commit is **signed off** (`git log --pretty=%B | grep "Signed-off-by"`)
- [ ] Every commit is **GPG/SSH signed** (the PR shows green "Verified")
- [ ] The branch is rebased on top of latest `main`
- [ ] `cd backend && PYTHONPATH=. ../.venv/bin/python -m unittest discover -s tests` passes
- [ ] `cd frontend && npm run build` succeeds
- [ ] The PR description explains the **why**, not just the what
- [ ] If you touched anything in `backend/wakili/auth/`, `backend/wakili/services/encryption.py`, or any exporter, you added or updated a test

## Reporting security issues

Please do **not** open a public GitHub issue for security problems.
See [`SECURITY.md`](./SECURITY.md) for the responsible-disclosure
address.

## Code of conduct

By participating in this project you agree to abide by the
[`Code of Conduct`](./CODE_OF_CONDUCT.md).

## Legal note for contributors operating from at-risk jurisdictions

If contributing publicly would put you at risk, you may contribute via
an anonymous Git author identity, provided:

1. You sign off the commit with that same identity, and
2. You can demonstrate (privately, to a maintainer) that you control
   the email address used in the sign-off.

This is the only situation in which we will accept non-real-name
sign-offs.
