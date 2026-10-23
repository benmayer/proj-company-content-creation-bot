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

Primary documents currently use these `type` values: `company_profile`, `brand_voice`, `promotion_pattern`, `editorial_guardrails`, and `past_content_examples`. Secondary-document types will be added when the industry knowledge base is built (card 05).

## Secondary KB conventions (card 05)

- Every file in `secondary/` carries `source_kind: secondary` plus `retrieved` (date) and `confidence`. The loader can tell the two KBs apart by folder and by this key.
- `type` values used so far in `secondary/`: `market_trends`, `competitor_analysis`, `customer_feedback`, `source_register`.
- `secondary/sources.md` records provenance for all secondary content. Ryanair's own facts (results, brand quotes) belong in `primary/`, not here.

Primary `type` values are recorded here when card 04 is done.

## Channel and content-type profiles (card 15)

`src/channel_profiles.py` turns the platform cues in `primary/brand_voice.md`
into four selectable profiles: LinkedIn, Instagram, X, and internal Slack. The
four composable content templates are `reply`, `press_release`, `post_update`,
and `meme`. Channel and type rules are injected separately from the selected
primary and secondary context so industry material cannot become a company fact.
