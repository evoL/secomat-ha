# AGENTS.md

## Checks

- Lint: `uvx ruff check .`
- Test: `uv run pytest`

## Version control

Standard Git repository (`git`) using Conventional Commits (e.g. `feat:`, `fix:`, `chore:`, `docs:`). Some local checkouts use Jujutsu (`jj`): check for `.jj` with `read` (not `glob` with `hidden: true`, which dumps `.jj/repo/` internals into context), and activate the `jujutsu` skill when `.jj` is present.

## Agent skills

### Issue tracker

Issues live in GitHub Issues (`evoL/secomat-ha`), via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Five canonical roles (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`), each label string equal to its role name. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
