# AGENTS.md

Instructions for any coding agent (Claude Code, Cursor, Copilot, Codex, …) working in this repo. Team: **Nico** and **Ben**.

## Purpose

An AI Content Creator for a company (Ryanair — see the Trello board name) built as a 2-day Ironhack group project (Module 2). It ingests two markdown knowledge bases — **primary** (company: brand voice, products, past content, strategy) and **secondary** (industry: market trends, competitors, customer feedback) — and runs the pipeline **document → monitor → brief → publish → iterate** to produce on-brand content that is demonstrably different from generic ChatGPT output ("AI-slop").

Scope, Must IDs and the Won't list live in [`project_structure.md`](project_structure.md). The retrieve-vs-inject choice is defended in [`rag_decision.md`](rag_decision.md). If a request isn't covered by a Must, ask before building it.

## Stack & how to run

- Python 3.8+, dependencies in `requirements.txt`
- LLM provider: _TBD (OpenAI or Anthropic) — update this line once decided_
- Markdown parsing: `markdown` / `mistune` (or similar)
- Secrets in `.env` (never committed). Expected vars: _TBD — list each key here when added_

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python src/main.py
```

## Repo map

| Path | What lives there |
|---|---|
| `src/document_processor.py` | Markdown ingestion and parsing |
| `src/knowledge_base.py` | Loads / selects from primary and secondary KBs |
| `src/prompt_templates.py` + `templates/` | Reusable prompt templates (style variants) |
| `src/content_pipeline.py` | document → monitor → brief → publish → iterate |
| `src/llm_integration.py` | The only module that calls the LLM API |
| `src/main.py` | Entry point |
| `knowledge_base/primary/` | Company docs (brand guidelines, product specs, `past_content/`) |
| `knowledge_base/secondary/` | Industry research (market trends, competitor analysis) |
| `project_structure.md`, `rag_decision.md` | Required PM / RAG docs |

## Conventions

- Knowledge-base content is **markdown only**, in the right folder (`primary/` = about the company, `secondary/` = about the market). `snake_case.md` filenames.
- Python: `snake_case` modules and functions, type hints on public functions, no new top-level folders without agreeing first.
- Prompts live in templates, not as inline strings scattered through the code.
- All LLM calls go through `llm_integration.py` so the provider can be swapped in one place.
- Keep generated content samples and ChatGPT comparisons in the repo — they are graded evidence of uniqueness.

## How we work with agents

- **One Trello card at a time.** Paste the card (title, Must ID, verify step) into the agent prompt.
- Trello board: https://trello.com/b/6Br1zrqp/ryanairproject. Kanban flow **Backlog → Ready → In progress (WIP: 2) → Review → Done**. Don't pull a third card into In progress.
- Commit small, with messages that reference the card number (e.g. `03 — add KB loader`).
- Claude Code: create tickets with the `/create-ticket` skill (`.claude/skills/create-ticket/`). Trello is connected via the `trello` MCP server; if its tools fail, re-authenticate with `/mcp`.
- No test or lint tooling exists yet — don't claim a check passed unless you actually ran it.

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
