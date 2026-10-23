---
name: create-ticket
description: Create a new ticket (card) on the Ryanair_project Trello board using the team's ticket format — numbered title, Must/Should/Could label, Context/Goal body and a Deliverables checklist. Use when the user asks to create, add or open a Trello ticket, card or task for this project.
---

# Create a Trello ticket

Creates a card on the **Ryanair_project** board via the Trello MCP tools (`mcp__trello__*`).

- Board URL: https://trello.com/b/6Br1zrqp/ryanairproject
- Board ARI: `ari:cloud:trello::board/workspace/6ad9be769691534d7d099ec8/6ad9cdaa6bc428ef6dfa7192`

If the Trello tools are missing or return an auth error, tell the user to run `/mcp` and re-authenticate `trello`, then stop.

## 1. Gather the inputs

From the user's request, work out:

- **Title**: short, action-oriented (e.g. "Set up content calendar").
- **Importance**: `Must`, `Should` or `Could`. If the user didn't say and it isn't obvious from context, ask — never guess.
- **Context**, **Goal** and **Deliverables** (see the body format below). If the request is too thin to write a concrete goal and deliverables, ask the user before creating anything.
- **Owner**: only if the user names them explicitly (see step 5).
- **List**: `To Do` unless the user says otherwise.

## 2. Work out the ticket number

Numbers are chronological across the whole board, including archived cards.

1. Call `trelloReadCard` with `action: "list_by_board"`, the board ARI, `filter: "all"`, and paginate until `hasNextPage` is false.
2. Find every card name starting with a number (pattern `^\d+\s*—`). Take the highest and add 1. If none exist, start at 1.
3. Zero-pad to two digits: `01`, `02`, … `10`, `11`.

## 3. Build the card

**Name:** `NN — Title` — number, space, em dash (`—`), space, title. No quotes around the title.

**Description** (markdown, exactly this structure):

```markdown
## Context
<1–3 sentences: what this ticket is about and why it matters.>

## Goal
<One clearly stated end goal — what "done" looks like.>

## Deliverables
See the **Deliverables** checklist below.
```

Do **not** put owners, assignees or "Owner:" lines in the description.

## 4. Create it

1. Look up the list ARI with `trelloReadList` (`action: "list_by_board"`) and pick the list by name.
2. Look up label ARIs with `trelloReadBoard` (`action: "list_labels"`) and pick the one whose name matches the importance exactly (`Must`, `Should`, `Could`). If the label is missing, tell the user instead of creating one.
3. `trelloWriteCard` `action: "create"` with `listId`, `name`, `desc`, `pos: "bottom"`.
4. `trelloWriteCard` `action: "attach_label"` with the new card's ARI and the label ARI.
5. `trelloWriteChecklist` `action: "create"` with `name: "Deliverables"` on the card, then `action: "add_item"` once per deliverable, in order. Each item is one concrete, verifiable output (a file, a document, a working feature) — not a vague activity.

## 5. Owners

- Assign an owner **only** if you are 100% certain who it is — the user named them explicitly for this ticket. Never infer from topic, past tickets or who usually does what.
- Resolve the name with `trelloReadMember` `action: "list_by_board"`. Assign only if exactly one board member clearly matches; if zero or several match, ask.
- Assign via the card's **members**, never in the description.
- If the Trello tools offer no way to add a member to a card, say so in the summary and name the person the user should assign by hand.

## 6. Report back

Reply with the card name, its label, the list it's in, the card URL, and any owner that still needs assigning manually.
