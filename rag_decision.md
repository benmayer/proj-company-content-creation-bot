# RAG decision

**Decision: no RAG.** We inject selected knowledge-base documents directly into the prompt. There is no embedding model, vector store or similarity search.

**The knowledge bases are structured as [OKF v0.2](https://github.com/GoogleCloudPlatform/open-knowledge-format)** (Open Knowledge Format): markdown files with YAML frontmatter instead of loose notes.

## Why not RAG

- **The corpus is small.** Two knowledge bases (primary: company, secondary: industry) built for a 2-day MVP fit comfortably in an LLM's context window. Retrieval solves a "too much to fit" problem we don't have.
- **Retrieval adds moving parts for no gain.** Chunking, embeddings, a vector store and tuning are extra work and extra failure modes, and they make output harder to explain. With injection, what the model saw is exactly what we selected.
- **Brand voice must not be chunked away.** Tone-of-voice rules work as a whole document. Similarity search can return fragments that miss them.

## Retrieve vs inject

| Criterion | Retrieve (RAG) | Inject selected documents (chosen) |
|---|---|---|
| Fit to corpus size | Pays off when the corpus exceeds the context window. Ours does not. | Two small knowledge bases fit in context. |
| Build effort in a 2-day MVP | Chunking, embeddings, a vector store and tuning. | Read files and filter on frontmatter. |
| Traceability | The model sees whichever chunks scored highest, which is hard to explain. | The prompt contains exactly the documents we selected, so we can log and inspect them. |
| Brand-voice fidelity | Chunks can drop part of the voice rules. | Whole documents stay intact. |
| Dependencies and cost | Embedding model, vector store, extra API calls. This conflicts with WON'T-02 in `project_structure.md`. | None beyond the one LLM call per draft. |

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

## Voice rules and examples per channel and type (card 22)

Channel tone, per-type rules and real past examples are also injected, not retrieved. They are looked up by the request's channel and content type (`src/channel_profiles.py`), never by topic similarity, because the right example for an X reply is "a real X reply", not "a passage that shares words with the topic". With 4 channels × at most 3 types the lookup is a fixed table, and each example file is a few hundred words, so it fits the prompt easily. The examples are verbatim, sourced posts in `knowledge_base/primary/past_content/examples_<channel>.md`; showing the model real posts changed the output far more than adjectives did (see `evidence/voice/`).

## Self-learning from approved and declined drafts (card 19)

**Decision: learning is injection, not training.** There is no fine-tuning and no embeddings, so WON'T-02 still holds.

- Every approval and decline is stored as one JSON line (outcome, channel, type, topic, draft, reason, timestamp) by `src/feedback_store.py`.
- When a prompt is built, the latest 2 approved drafts and 3 decline reasons for the **same channel and type** are selected deterministically and injected as a separate `LEARNED FEEDBACK` block.
- Learned feedback is style guidance only. It is labelled "NOT company facts", stays out of the primary and secondary blocks, and the system prompt tells the model not to take claims from it.
- Only the decline *reason* is fed back, not the declined text, so a rejected draft's wording is not reused.

**Where it is stored.** Locally: `outputs/feedback.jsonl`. Render's disk is ephemeral, so for the hosted app attach a Render persistent disk (paid instances only, billed per GB per month) mounted at `/var/data` and set `FEEDBACK_STORE_PATH=/var/data/feedback.jsonl`. No extra service or dependency is needed. On a free instance, feedback resets on every deploy; that is the documented trade-off for card 20.
