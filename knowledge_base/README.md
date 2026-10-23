# Knowledge base

Markdown files following the subset of [OKF v0.2](https://github.com/GoogleCloudPlatform/open-knowledge-format) described in [`rag_decision.md`](../rag_decision.md).

- `primary/`: about the company (brand voice, products, `past_content/`, strategy)
- `secondary/`: about the market (trends, competitors, customer feedback)
- `snake_case.md` filenames. Content must come from real sources, never made up.

## File format

```markdown
---
type: <what kind of document this is>
title: <human-readable name>
description: <one-line summary>
tags: [<tag>, <tag>]
---

Body in markdown.
```

`type` is required. `title`, `description` and `tags` are recommended; `tags` is a YAML list. Other keys are allowed and must be preserved.

Primary documents currently use these `type` values: `company_profile`, `brand_voice`, `promotion_pattern`, `editorial_guardrails`, `past_content_examples`, `product_policy` (`fares_and_extras.md`: what each fare includes and which extras are paid), plus the profile and example types below. Secondary-document types will be added when the industry knowledge base is built (card 05).

## Secondary KB conventions (card 05)

- Every file in `secondary/` carries `source_kind: secondary` plus `retrieved` (date) and `confidence`. The loader can tell the two KBs apart by folder and by this key.
- `type` values used so far in `secondary/`: `market_trends`, `competitor_analysis`, `customer_feedback`, `public_perception`, `source_register`.
- `secondary/sources.md` records provenance for all secondary content. Ryanair's own facts (results, brand quotes) belong in `primary/`, not here.

Primary `type` values are recorded here when card 04 is done.

## Channel and content-type profiles

Where the writing rules live. Templates in `templates/` carry only structure and output constraints; the wording comes from these primary documents.

| File | `type` | Required keys | Sections used |
| --- | --- | --- | --- |
| `primary/channel_<name>.md` | `channel_profile` | `channel`, `content_types` (list) | `## Tone`, `## Format`, and one section per offered type: `## Post`, `## Reply`, `## Meme`, `## Press release` |
| `primary/content_type_<name>.md` | `content_type_profile` | `content_type`; optional `label`, `temperature` | `## Voice rules` (optional), `## Format rules` |
| `primary/past_content/examples_<channel>.md` | `channel_examples` | `channel` | one section per type, same headings as the channel profile |

- `content_types` in a channel profile decides which types the UI offers for that channel. `content_type_labels` can rename a type for one channel (internal Slack calls a press release "press release (internal)").
- Profiles carry `source_kind: team_direction`: they are the team's editorial decisions about how to write, not sourced company facts.
- Example files hold **real, verbatim** posts with a source link and date. Never write invented examples: if none have been collected for a channel and type, leave the section out and the prompt says so.
- All three are looked up by channel and content type (`src/channel_profiles.py`), never selected by topic. Files are read on every draft, so edits apply without a restart.

How the prompt is assembled (facts first, voice last, because the end of a prompt weighs most):

1. `PRIMARY CONTEXT`, `SECONDARY CONTEXT`: topic-selected documents. Replies and memes on public channels always include the background pair `primary/fares_and_extras.md` (the product as it really is) and `secondary/public_perception.md` (how passengers see it); press releases and internal Slack never do; other drafts get them only when the topic matches (e.g. cabin bags). Sections only useful to a human reviewer (`Sources`, `Review questions`, …) are left out, and Markdown link URLs are dropped.
2. `GUARDRAILS`: `editorial_guardrails.md`.
3. `REQUEST`: the topic, or the post to reply to (text and/or an attached screenshot).
4. `VOICE RULES`, most specific first: the channel profile's section for this type, the content type's `## Voice rules`, the channel's `## Tone`, then `brand_voice.md`.
5. `EXAMPLES`: the matching section of `examples_<channel>.md`.
6. `LEARNED FEEDBACK`, then `FORMAT LIMITS` (the channel's `## Format` and the type's `## Format rules`).

To add a content type: one template in `templates/`, one `content_type_<name>.md`, its name in `CONTENT_TYPES`, and the type listed under `content_types` with a section in each channel profile that should offer it. To change a style rule, edit the Markdown file.
