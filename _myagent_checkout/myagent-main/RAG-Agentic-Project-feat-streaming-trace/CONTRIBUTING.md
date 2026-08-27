# Contributing — Git & Team Workflow

This is the part of the project that turns "we built an AI app" into "we learned to work like engineers." It's graded as much as the app. Read it on day one and hold each other to it in pull request reviews.

---

## Repository setup
- One `main` branch, **protected**: no direct pushes, PRs only, **at least one approving review** required to merge.
- A `.gitignore` from day one (`node_modules/`, `__pycache__/`, `.env`, build artifacts, uploaded files, model dumps). One is included in this repo.
- `.env.example` is committed; the real `.env` (with config) is **never** committed.
- The README is updated as the project evolves — not written the night before demos.

## Branching strategy — GitHub Flow
Keep it simple. This isn't the place for release branches.

```
main                 ← always deployable, protected
 └─ feature/<name>   ← one branch per issue/feature, short-lived
```

- Branch off `main`, name it after the work: `feature/pdf-ingestion`, `fix/citation-offsets`, `chore/add-ci`.
- Keep branches small and short-lived — merge within a day or two, not a week. Long-lived branches cause painful merge conflicts; avoiding that is the lesson.
- Pull `main` into your branch regularly to stay current.

## Commit conventions
Small, focused commits with messages that explain *why*. Use Conventional Commits prefixes:

```
feat: add PDF chunking to ingestion pipeline
fix: correct top-k ordering in similarity search
chore: configure GitHub Actions test workflow
docs: document embedding model choice in README
test: add tests for the retrieval function
refactor: extract Ollama calls behind a generate() interface
```

Rule of thumb: if the commit message needs the word "and," it's probably two commits.

## Pull request workflow
Every change reaches `main` through a reviewed PR. Use the PR template (`.github/PULL_REQUEST_TEMPLATE.md`).

- **No one merges their own PR without a review.** Everyone authors *and* reviews PRs during the project — reviewing is a skill, not a chore.
- Reviewers check: does it work, is it readable, are there tests, **are any secrets leaked**, and are edge cases handled (empty document, no chunks found, Ollama timeout).
- Keep PRs small — ideally under ~400 lines changed. Giant PRs get rubber-stamped, which defeats the purpose.
- Resolve review comments with follow-up commits, then re-request review.
- Link the PR to its issue with `Closes #12` so merging auto-closes it.

## Code review norms
- Be kind and specific. Critique the code, not the person. "What happens if retrieval returns zero chunks?" beats "this is wrong."
- Distinguish blocking comments from suggestions (a `nit:` prefix helps).
- Authors: don't take it personally — the reviewer caught it before a user did.
- Review within a few hours during work time so nobody is blocked.

## Issue tracking & the board
- Every meaningful piece of work is an issue before it's a branch. Use the issue template.
- Board columns: **Backlog → To Do → In Progress → In Review → Done.**
- One owner per issue at a time; the board reflects reality at standup.

## Continuous Integration
- A GitHub Actions workflow runs on every PR: install deps, run the linter, run the tests.
- **A red build blocks the merge.** This is the safety net that makes fast iteration safe.
- **Mock the model and tool calls in CI** — assert your agent builds the right tool call and parses results correctly. CI shouldn't need a running model or a live AnythingLLM.
- Start tiny: one workflow that runs `pytest` and `npm test` is enough to teach the concept.

## Testing expectations
Aiming for the *habit*, not exhaustive coverage:
- **Backend:** tests for tool functions, argument validation, and the agent loop's stop conditions (with a stubbed model + stubbed tools). Test that the loop terminates and that a malformed tool call is caught — not that the model says a specific thing.
- **Frontend:** a few component tests (React Testing Library) for the chat and upload flows.
- A manual QA checklist for the demo path, run before presenting.

## Definition of Done
A task is done when **all** of these are true:
- Code is merged to `main` via a reviewed PR
- It runs correctly following the README setup steps (local dev servers)
- Tests for it pass in CI
- It introduces no known regressions in existing features
- No secrets committed; README/docs updated as needed

## Ceremonies (keep them short)
- **Daily standup (10 min):** yesterday / today / blockers.
- **Sprint planning (start of each week):** move issues into the week's column, assign owners.
- **Retro (end of weeks 2 and 3):** what went well, what didn't, one change to try.

## Branching cheat-sheet
```bash
# start a new piece of work
git checkout main
git pull
git checkout -b feature/pdf-ingestion

# ...make changes, commit in small chunks...
git add .
git commit -m "feat: parse and chunk uploaded PDFs"
git push -u origin feature/pdf-ingestion

# open a PR on GitHub, get a review, merge, then:
git checkout main
git pull
git branch 