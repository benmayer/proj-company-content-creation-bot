# Project structure and work breakdown

## 1. Identity and purpose

| Field | Decision |
| --- | --- |
| Project | Company content creation bot |
| Company | Ryanair |
| Primary user | A company social-media/content team member who needs a reviewable draft quickly |
| MVP output | A short, public-facing company post produced from approved knowledge-base context |
| Content scope | Social posts and one reusable campaign/content brief format; the final channel and length are request inputs |
| MVP boundary | Documented ingestion, deterministic context selection, prompt rendering, one LLM boundary, human review, and saved outputs |
| Source-of-truth rule | Company facts and brand rules come from `knowledge_base/primary/`; market context comes from `knowledge_base/secondary/` |

The product is intentionally a small content assistant, not an autonomous publishing system. It must make the source context and review step visible so that a teammate can correct a draft before it is used publicly.

## 2. Quality, time, and cost constraints

### Quality targets

- **Traceability:** every generated draft records the request and the selected source documents.
- **Brand fit:** prompts include the primary brand-voice guidance and do not ask the model to invent unsupported company facts.
- **Separation:** primary company knowledge and secondary industry knowledge remain separate in storage, selection, and prompt context.
- **Reviewability:** a draft is presented for approval before it is saved as an approved output.
- **Reproducibility:** a fresh clone can run the documented command using environment configuration, without committed secrets.

### Time and cost constraints

- **Timebox:** two-day Ironhack MVP. Prefer deterministic markdown selection and direct prompt injection over infrastructure that needs tuning.
- **Runtime cost:** one model call per draft request in the normal path; no embeddings, vector database, crawler, or always-on service.
- **Build cost:** use the existing Python 3.8+ stack and small, swappable modules. Provider-specific code belongs only in `src/llm_integration.py`.
- **Operational cost:** human approval remains required; publishing to a live company account is outside this MVP.

## 3. Stakeholders and responsibilities

| Stakeholder | Need or responsibility |
| --- | --- |
| Content team/user | Supplies the content request, reviews the draft, and approves or requests an iteration |
| Nico and Ben | Define scope, curate source material, implement the MVP, and peer-review the result |
| Company/brand owner | Owns the accuracy of company facts and brand guidance supplied to the primary KB |
| Marketing/social audience | Receives the eventual public content; needs clear, appropriate, non-misleading copy |
| Project reviewer | Checks the Must requirements, evidence of uniqueness, setup, and secret safety |
| LLM provider | Generates a draft from the supplied prompt; is an interchangeable implementation detail |

## 4. Traceable requirements

There are eight Must requirements. Each one has a concrete artifact and a verification that can be run or inspected during review.

| ID | Must requirement | Shipped artifact | Explicit verification |
| --- | --- | --- | --- |
| MUST-01 | Define the Ryanair content-creator scope, user, inputs, output, and MVP boundary. | `project_structure.md` | Read §1 and confirm the identity table defines all six fields and the boundary paragraph. |
| MUST-02 | Maintain separate, sourced primary company and secondary industry knowledge bases using the agreed markdown/frontmatter convention. | `knowledge_base/README.md`, `knowledge_base/primary/`, `knowledge_base/secondary/` | Inspect both directories and run the document-processor check: each KB document has required `type` frontmatter and non-empty headed content; confirm no company facts are stored in `secondary/`. |
| MUST-03 | Ingest markdown into headed sections while preserving source metadata. | `src/document_processor.py` | Run the representative markdown ingestion check and verify every returned section has a heading, non-empty body, and source path/metadata. |
| MUST-04 | Select relevant context deterministically while keeping primary and secondary context distinguishable. | `src/knowledge_base.py` | Run representative requests for company facts and industry context; inspect that returned documents are non-empty, come from the expected root, and are labelled by source kind. |
| MUST-05 | Render complete, content-type-specific prompts that enforce fact-only generation and reviewable output constraints. | `src/prompt_templates.py`, `templates/` | Render every supported template with a representative request and assert there are no unresolved placeholders and that the prompt contains the selected context and output constraints. |
| MUST-06 | Route all model calls through one secure, provider-swappable boundary with actionable configuration errors. | `src/llm_integration.py`, `.env.example` | Run the missing-configuration check and a mocked client check; confirm no API key is hard-coded and only `llm_integration.py` imports/calls the provider. |
| MUST-07 | Connect document → monitor → brief → publish → iterate with human approval before an approved output is saved. | `src/content_pipeline.py`, `src/main.py`, `outputs/` | Run the documented end-to-end demo with a mocked LLM; confirm the draft pauses for approval, an approved output is timestamped and saved, and rejection requests an iteration. |
| MUST-08 | Demonstrate concrete value beyond generic AI and provide reproducible setup/evidence. | `evidence/`, `README.md` | Inspect the side-by-side comparison for facts, brand fit, style, and iteration; follow README setup and demo commands from a clean environment without secrets. |

## 5. Won't list

The following are deliberately excluded from the two-day MVP:

- **WON'T-01:** autonomous posting to a live Ryanair social account or automatic scheduling.
- **WON'T-02:** embeddings, vector search, a vector database, or a general-purpose RAG service.
- **WON'T-03:** web crawling, live trend ingestion, or unsourced company facts.
- **WON'T-04:** multi-tenant accounts, analytics dashboards, billing, or a production web UI.

## 6. Work breakdown structure (WBS)

The level-2 work packages below are the implementation sequence for the MVP. Cards 01–03 establish scope, planning, and the no-RAG/OKF decision; cards 04–12 deliver and evidence the product.

### 6.1 Build primary company knowledge base (card 04)

Collect and cite company brand guidance, product facts, and past-content examples in `knowledge_base/primary/`. Do not invent facts.

### 6.2 Build secondary industry knowledge base (card 05)

Add sourced industry, competitor, and customer-feedback material under `knowledge_base/secondary/`, clearly separate from company facts.

### 6.3 Implement the Markdown document processor (card 06)

Parse OKF v0.2-style frontmatter and return non-empty headed sections with source metadata.

### 6.4 Implement knowledge-base selection (card 07)

Select documents by request and metadata, preserving the primary/secondary distinction and injecting selected context directly into prompts.

### 6.5 Create reusable prompt templates (card 08)

Render content-type-specific prompts with brand, fact, format, and review constraints in `templates/`.

### 6.6 Integrate the LLM client securely (card 09)

Read provider configuration from `.env`, keep the provider boundary in one module, and expose clear failures.

### 6.7 Connect the end-to-end content pipeline (card 10)

Wire document, monitor, brief, publish, and iterate stages; save only approved, timestamped drafts.

### 6.8 Prove uniqueness against generic AI (card 11)

Keep a side-by-side sample and analysis showing differences in facts, brand fit, style, and iteration.

### 6.9 Finish README, tests, demo, presentation, and screenshots (card 12)

Document setup and verification, run the demo, capture evidence, and check the Must/Won't boundary before handoff.

## 7. Risks and mitigations

| Risk | Impact | Mitigation / owner |
| --- | --- | --- |
| Source material is incomplete or unsourced | Drafts may be inaccurate or generic | Nico/Ben curate provenance and reject unsupported facts; enforce MUST-02 and MUST-05. |
| Brand voice is reduced to a stereotype | Output may be off-brand or repetitive | Preserve complete voice guidance, include past examples, and compare against generic output in card 11. |
| LLM provider/API configuration fails during demo | End-to-end flow cannot run | Keep one boundary, validate configuration early, provide a mocked verification path, and document `.env` setup. |
| Scope expands beyond the timebox | Core flow remains unfinished | Use the Won't list, one model call per request, and the 9 WBS packages above. |
| Human review is bypassed | Unsuitable copy could be treated as publish-ready | Make approval a pipeline state transition and save only approved output. |
| Secrets or private data enter git or evidence | Security and grading failure | Use `.env.example`, keep `.env` ignored, inspect `git diff`/tracked files before review, and use sourced public material only. |

## 8. RAG bridge and implementation contract

The project uses **no RAG**. The two small markdown knowledge bases are selected deterministically by metadata and injected into the prompt as complete documents or sections. This is the implementation contract for cards 06–10 and is explained in detail in [`rag_decision.md`](rag_decision.md).

| Planning decision | Consequence for implementation |
| --- | --- |
| No embeddings or vector store | No retrieval service, index, or chunk-ranking dependency may be added. |
| OKF v0.2-style frontmatter | `type` is required; recommended metadata such as `title`, `description`, `tags`, and `resource` is preserved. Unknown metadata must not be discarded. |
| Primary/secondary separation | Selection APIs and prompts must identify the source kind so market context cannot be presented as a company fact. |
| Direct injection | Prompt templates receive selected documents explicitly; tests can inspect the exact context used for a draft. |
| Swappable model provider | Only `src/llm_integration.py` may call the LLM API; templates and pipeline code remain provider-agnostic. |

This document is the scope boundary for implementation. Any feature not covered by a Must or needed by the WBS requires team agreement before it is built.
