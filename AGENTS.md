# AGENTS.md

Working agreement for any AI agent (Claude or otherwise) operating on this repository. This
captures the standing instructions given for the current initiative — the RAG/pgvector search
upgrade — and the process to follow for every phase of it, until the user says otherwise.

## Role

The agent acts as **tech lead** for this initiative. That means:

- Own the system architecture and data-flow design decisions.
- Do not implement everything solo — delegate implementation and verification to subagents (see
  below), and use your own time to review, verify, and integrate their output rather than
  duplicate it.
- Stay accountable for the end result: a subagent's claim is not "done" until you have spot-checked
  it against the actual repo state (diffs, test output, running the checks yourself when cheap
  enough to do so).

## Subagent delegation

- Every iteration must involve **at minimum one backend subagent** (implementation) and **one
  testing/QA subagent** (independent verification). The QA subagent must not simply trust the
  backend subagent's report — it re-runs the checks itself, greps the code itself, and flags any
  discrepancy between what was claimed and what it actually observed.
- Additional subagents (reviewer, security, docs, etc.) are the tech lead's call — add them when
  the phase's risk profile warrants it.
- Sequence backend → QA when a step depends on the previous one's output; don't parallelize steps
  that have a real dependency.

## Reporting

At the end of every iteration, report back in clear, plain language (not just raw subagent
transcripts):

- What changed (files, versions, schema, endpoints — whatever applies).
- Recommendations — things worth doing that weren't explicitly asked for.
- Open questions for the human dev team — anything that needs a product/architecture decision
  before continuing.

## Code language

All code, comments, docstrings, and commit messages in this repository must be written in
**English**, regardless of what language the working conversation happens in. When touching a
file that has stray non-English text near the edit, translate it while you're there. Do not do a
speculative full-repo sweep for this on its own — clean it up incrementally as files are touched
for other reasons.

## Documentation hygiene

- Keep project docs (README.md, this file, PRODUCT.md/DESIGN.md when present) in sync with the
  actual state of the code. A stale badge, version number, or test count is a bug in the same
  sense a failing test is — fix it when you notice it, don't leave it for later.
- Delete documentation that no longer reflects reality instead of leaving it to rot. Don't delete
  something without understanding why it was there first.

## Escalation model — work phase by phase

This initiative follows the plan described in the reference document `informe_equipo_django.md`
(RAG pipeline for semantic product search, delivered by the `Chatbot-Engine-Gateway` team). Do not
jump ahead to a later phase before the current one is verified done. Summary of phases, for
continuity across sessions:

- **Phase 0 — Django upgrade (blocking, done):** Django 4.1.2 → 4.2 → 5.2 LTS, plus dependency
  bumps needed to stay compatible (djangorestframework, asgiref). No feature work happens on top
  of an unpatched Django version.
- **Phase 1 — New database schema:** enable the `pgvector` Postgres extension, add an
  `ItemEmbedding` model (separate table, HNSW index, cosine similarity) and a `ProductAttribute`
  model (structured `name`/`value` pairs — the actual fix for queries like "red sneakers", which
  embeddings alone don't reliably capture), widen `Item.title`/`Item.description`, and provision a
  dedicated least-privilege Postgres role (`chatbot_readonly_role`) for the chatbot's read path.
- **Phase 2 — Data ingestion:** import real catalog data from the Amazon Reviews'23 dataset
  (title/description/attributes/category/brand) while keeping Faker for everything the dataset
  doesn't cover (suppliers, users, orders); generate synthetic reviews informed by the dataset's
  real rating distribution instead of pure randomness.
- **Phase 3 — Internal API contract:** new internal endpoints under the existing
  `X-Internal-Secret`-protected pattern for vector search, similar-item lookup, an embedding
  outbox (pending/upsert/mark-error), stock/price verification, and category/brand facets — this
  is the contract the separate Gateway team's chatbot consumes.
- **Phase 4 — Defense in depth:** database-level column restrictions on the dedicated read-only
  role, as a second layer of protection behind the Gateway's own access control for its raw-SQL
  sandbox tool.

Out of scope for this repo/team in every phase: LLM prompts, function-calling tool definitions,
SSE streaming, and the Gemini client itself — those belong to the `Chatbot-Engine-Gateway` service.

## Environment notes

- Windows + Git Bash. Activate the venv with `source venv/Scripts/activate` before any
  `python`/`pip`/`pytest` command.
- Tests run against SQLite via `config.settings.testing` (`python -m pytest -q` from the repo
  root) — fast, no live Postgres needed, safe to run freely.
- The real database is Neon-hosted Postgres (production). Treat it as shared infrastructure:
  don't run destructive or exploratory SQL against it without the user's explicit go-ahead.
