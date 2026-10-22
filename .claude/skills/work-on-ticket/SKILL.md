---
name: work-on-ticket
description: Work on an existing Ryanair_project Trello ticket from Ready or another authorized list, validating its requirements first and stopping for user feedback when blocked or when review is complete.
---

# Work on a Trello ticket

Use this skill when asked to work on, implement, complete, or progress an existing ticket on the **Ryanair_project** Trello board.

## Workflow

1. **Finish existing In progress work before pulling new work.**
   - Before starting a ticket from **Backlog** or **Ready**, inspect the board for cards already in **In progress**.
   - Resume and finish those cards first, one at a time, using the same ticket-reading, readiness, implementation, and verification rules below.
   - Do not pull a new backlog/Ready ticket while an existing In progress card can be completed or moved to **Review**.
   - After each In progress card passes its Deliverables and Definition of Done checks, move it to **Review**. Never move it directly to **Done**.
   - If an In progress card is blocked, follow the blocked-ticket procedure and stop for user feedback rather than starting another backlog ticket.

2. **Read the ticket.**
   - Fetch the card, its description, labels, checklists, comments, and current list.
   - Read the board's **Definition of Done** card before progressing work.
   - Treat the ticket description and Deliverables checklist as the source of truth.

3. **Prepare the repository before starting.**
   - Check the current branch and working tree before making changes.
   - Make sure the repository is up to date with its remote base branch. Use a safe fast-forward update; never discard or overwrite uncommitted work.
   - If the working tree contains changes, the base branch cannot be updated safely, or the repository state is unclear, ask the user before proceeding.
   - Create and switch to a dedicated branch for the ticket after the base branch is up to date. Use a clear name such as `01-content-scope` or `06-document-processor`.
   - Do not start ticket implementation on the shared base branch.

4. **Check readiness before starting.**
   - Confirm that the goal, required inputs, acceptance checks, deliverables, and relevant project context are clear.
   - Do not invent missing requirements, data, credentials, design choices, owners, or expected behavior.
   - If information is missing or ambiguous, ask the user and stop. Do not begin implementation until the user provides the missing information.

5. **Work on the ticket.**
   - Make only the changes required by the ticket and the user's instructions.
   - Keep the ticket's deliverables and Definition of Done in view while working.
   - Add useful progress or verification notes to the card when appropriate, without putting secrets or private data in Trello.

6. **If blocked, stop and request feedback.**
   - When progress depends on missing information, an unavailable resource, an unresolved decision, or an external failure that cannot be safely resolved, move the card to the list named **Blocked**.
   - Add a concise comment stating the blocker, what was checked, and the exact decision or input needed.
   - If the board has no **Blocked** list, do not create one or move the card to another list without user approval; ask the user how to proceed.
   - Stop work and wait for the user's feedback.

7. **Before review, verify completion.**
   - Check every item in the ticket's **Deliverables** checklist.
   - Check every applicable requirement in **Definition of Done**, including peer review expectations, verification, repository consistency, and secret safety.
   - Run the relevant tests or verification and record the result.
   - Do not move the card to Review if any deliverable or required Definition of Done condition is incomplete.

8. **When finished, move to Review.**
   - Move the completed card to the list named **Review**.
   - Report what was completed, how it was verified, and any remaining caveats.
   - Stop and wait for the user's green light. Do not continue to Done automatically.

## Done-list restriction

Only Ben and the user are allowed to move tickets to **Done**. This agent must never move a ticket to Done, mark it complete, or treat moving it to Review as approval. A ticket remains in Review until Ben or the user gives explicit approval and moves it themselves.

## Safety and scope

- Do not change unrelated cards, lists, labels, members, or board settings.
- Do not infer ownership from card text or assign members unless the user explicitly asks.
- Do not expose API keys, `.env` contents, credentials, or private data in card comments or descriptions.
