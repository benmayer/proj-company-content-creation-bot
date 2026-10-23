# AGENTS.md

Instructions for any coding agent (Claude Code, Cursor, Copilot, Codex, …) working in this repo. Team: **Nico** and **Ben**.

## Purpose

An AI Content Creator for a company (Ryanair — see the Trello board name) built as a 2-day Ironhack group project (Module 2). It ingests two markdown knowledge bases — **primary** (company: brand voice, products, past content, strategy) and **secondary** (industry: market trends, competitors, customer feedback) — and runs the pipeline **document → monitor → brief → publish → iterate** to produce on-brand content that is demonstrably different from generic ChatGPT output ("AI-slop").

Scope, Must IDs and the Won't list live in [`project_structure.md`](project_structure.md). The retrieve-vs-inject choice is defended in [`rag_decision.md`](rag_decision.md). If a request isn't covered by a Must, ask before building it.

## Stack & how to run

- Python 3.8+, dependencies in `requirements.txt`
- LLM provider: OpenAI, via the `openai` SDK, called only from `src/llm_integration.py`
- Markdown parsing: `markdown` / `mistune` (or similar); YAML frontmatter via `PyYAML`
- Hosting: the final UI is deployed on **Render** (card 20). On Render, secrets are set as dashboard environment variables, never committed.
- Secrets in `.env` (never committed; it is in `.gitignore`). Copy `.env.example` to `.env` and fill it in. Expected vars: `OPENAI_API_KEY`, `LLM_MODEL` (plus `TRELLO_API_KEY` / `TRELLO_TOKEN` for the Trello MCP)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python src/main.py
python -m unittest tests.test_llm_integration tests.test_knowledge_base   # tests use unittest; no key or network needed
```

## Repo map

| Path | What lives there |
|---|---|
| `app.py` | Streamlit local UI |
| `src/document_processor.py` | Markdown ingestion and parsing |
| `src/knowledge_base.py` | Loads / selects from primary and secondary KBs |
| `src/prompt_templates.py` + `templates/` | Reusable prompt templates (style variants) |
| `src/content_pipeline.py` | document → monitor → brief → publish → iterate |
| `src/feedback_store.py` | Approved/declined drafts in `outputs/feedback.jsonl` (or `FEEDBACK_STORE_PATH`), selected per channel + type as learned feedback |
| `src/llm_integration.py` | The only module that calls the LLM API |
| `evidence/` | Graded proof: `self_learning_demo.py` and `self_learning/comparison.md` (before/after feedback) |
| `src/main.py` | CLI entry point |
| `knowledge_base/primary/` | Company docs (brand guidelines, product specs, `past_content/`) |
| `knowledge_base/secondary/` | Industry research (market trends, competitor analysis) |
| `project_structure.md`, `rag_decision.md` | Required PM / RAG docs |

## Conventions

- Knowledge-base content is **markdown with OKF v0.2 frontmatter** (`type` required; `title`, `description`, `tags` recommended — see [`knowledge_base/README.md`](knowledge_base/README.md)), in the right folder (`primary/` = about the company, `secondary/` = about the market). `snake_case.md` filenames. No RAG: selected docs are injected into the prompt, see [`rag_decision.md`](rag_decision.md).
- Python: `snake_case` modules and functions, type hints on public functions, no new top-level folders without agreeing first.
- Prompts live in templates, not as inline strings scattered through the code.
- All LLM calls go through `llm_integration.py` so the provider can be swapped in one place.
- Keep generated content samples and ChatGPT comparisons in the repo — they are graded evidence of uniqueness.

## How we work with agents

- **One Trello card at a time.** Paste the card (title, Must ID, verify step) into the agent prompt.
- Trello board: https://trello.com/b/6Br1zrqp/ryanairproject. Kanban flow **Backlog → In progress (WIP: 2) → Review → Done**. Don't pull a third card into In progress.
- Branch names are `NN-short-description`: the card number, then kebab-case words, with no `ticket-` prefix (e.g. `06-document-processor`, `20-render-hosting-docs`). One branch per card, never work directly on `main`.
- Commit small, with messages that reference the card number (e.g. `03 — add KB loader`).
- Claude Code: create tickets with the `/create-ticket` skill (`.claude/skills/create-ticket/`). Trello is connected via the `trello` MCP server, defined in the committed `.mcp.json`. Each person supplies their own credentials: put `TRELLO_API_KEY` and `TRELLO_TOKEN` in your `.env` (see `.env.example`; get them at https://trello.com/power-ups/admin), then start Claude Code with `set -a; source .env; set +a; claude`, because Claude Code only reads variables from the launching shell, not from `.env`. On first launch it asks you to approve the project server. If its tools fail, check the variables are set in that shell, then run `/mcp`.
- No test or lint tooling exists yet — don't claim a check passed unless you actually ran it.

## UI

The local front end uses Streamlit. Run it with `streamlit run app.py`; use the sidebar to choose the channel/type, generate a draft, request feedback, or approve and save it. Uploaded assets stay in memory and are not committed.

## Definition of Done (same as the Kanban board)

1. Code/docs are in the repo (committed on the branch).
2. The Must's **verify** step from `project_structure.md` passes.
3. The Trello card notes what changed.
4. No secrets committed.

## Never

- Commit `.env`, API keys or any credentials.
- Invent APIs, library functions, model names or KB facts — check the docs or ask.
- Build anything on the Won't list in `project_structure.md`, or add features no Must asks for.
- Put made-up company facts into `knowledge_base/` — KB content must come from real sources.
- Rewrite or delete another teammate's work without asking.
