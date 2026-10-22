# RAG decision

**Decision: no RAG.** We inject selected knowledge-base documents directly into the prompt. There is no embedding model, vector store or similarity search.

**The knowledge bases are structured as [OKF v0.2](https://github.com/GoogleCloudPlatform/open-knowledge-format)** (Open Knowledge Format): markdown files with YAML frontmatter instead of loose notes.

## Why not RAG

- **The corpus is small.** Two knowledge bases (primary: company, secondary: industry) built for a 2-day MVP fit comfortably in an LLM's context window. Retrieval solves a "too much to fit" problem we don't have.
- **Retrieval adds moving parts for no gain.** Chunking, embeddings, a vector store and tuning are extra work and extra failure modes, and they make output harder to explain. With injection, what the model saw is exactly what we selected.
- **Brand voice must not be chunked away.** Tone-of-voice rules work as a whole document. Similarity search can return fragments that miss them.

## How documents are selected instead

Selection is deterministic and based on frontmatter metadata (`type`, `tags`), implemented in `src/knowledge_base.py` (card 07). For example: always load the brand-voice document, plus competitor documents tagged for the topic of the brief.

## Why OKF

- It stays plain markdown, so the `primary/` vs `secondary/` convention and git review still work.
- The frontmatter gives us structure to select on, which replaces what retrieval would have done.
- It is an open spec, not something we invent. Consumers must tolerate unknown keys and types, so extending it is safe.

## What we use from OKF

Only a small subset, because the spec is young (v0.2; v0.2 made breaking changes from v0.1):

| Key | Use |
|---|---|
| `type` | Required by OKF. Our value set is listed in `knowledge_base/README.md`. |
| `title`, `description` | Recommended. Human-readable name and one-line summary. |
| `tags` | YAML list. Used for selection. |

We do not use the provenance, attested-computation or `index.md`/`log.md` features for now. Field names beyond these should be checked against [SPEC.md](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md) before use.

## Consequences

- The document processor (card 06) parses YAML frontmatter, so `requirements.txt` includes `PyYAML`.
- If a knowledge base ever outgrows the context window, revisit this decision. Until then, injection stays.
