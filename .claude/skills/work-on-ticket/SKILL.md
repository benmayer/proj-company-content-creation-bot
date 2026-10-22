---
name: work-on-ticket
description: Work on an existing Ryanair_project Trello ticket from Ready or another authorized list, validating its requirements first and stopping for user feedback when blocked or when review is complete.
---

# Work on a Trello ticket

Use this skill when asked to work on, implement, complete, or progress an existing ticket on the **Ryanair_project** Trello board.

## Workflow

1. **Read the ticket.**
   - Fetch the card, its description, labels, checklists, comments, and current list.
   - Read the board's **Definition of Done** card before progressing work.
   - Treat the ticket description and Deliverables checklist as the source of truth.

2. **Check readiness before starting.**
   - Confirm that the goal, required inputs, acceptance checks, deliverables, and relevant project context are clear.
   - Do not invent missing requirements, data, credentials, design choices, owners, or expected behavior.
   - If information is missing or ambiguous, ask the user and stop. Do not begin implementation until the user provides the missing information.

3. **Work on the ticket.**
   - Make only the changes required by the ticket and the user's instructions.
   - Keep the ticket's deliverables and Definition of Done in view while working.
   - Add useful progress or verification notes to the card when appropriate, without putting secrets or private data in Trello.

4. **If blocked, stop and request feedback.**
   - When progress depends on missing information, an unavailable resource, an unresolved decision, or an external failure that cannot be safely resolved, move the card to the list named **Blocked**.
   - Add a concise comment stating the blocker, what was checked, and the exact decision or input needed.
   - If the board has no **Blocked** list, do not create one or move the card to another list without user approval; ask the user how to proceed.
   - Stop work and wait for the user's feedback.

5. **Before review, verify completion.**
   - Check every item in the ticket's **Deliverables** checklist.
   - Check every applicable requirement in **Definition of Done**, including peer review expectations, verification, repository consistency, and secret safety.
   - Run the relevant tests or verification and record the result.
   - Do not move the card to Review if any deliverable or required Definition of Done condition is incomplete.

6. **When finished, move to Review.**
   - Move the completed card to the list named **Review**.
   - Report what was completed, how it was verified, and any remaining caveats.
   - Stop and wait for the user's green light. Do not continue to Done automatically.

## Done-list restriction

Only Ben and the user are allowed to move tickets to **Done**. This agent must never move a ticket to Done, mark it complete, or treat moving it to Review as approval. A ticket remains in Review until Ben or the user gives explicit approval and moves it themselves.

## Safety and scope

- Do not change unrelated cards, lists, labels, members, or board settings.
- Do not infer ownership from card text or assign members unless the user explicitly asks.
- Do not expose API keys, `.env` contents, credentials, or private data in card comments or descriptions.
