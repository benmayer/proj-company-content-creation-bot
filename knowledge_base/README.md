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

The set of `type` values is agreed when the knowledge bases are built (cards 04 and 05) and recorded here.
