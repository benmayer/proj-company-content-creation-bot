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
