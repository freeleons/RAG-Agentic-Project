The agent does not invoke every available tool immediately. Instead, it follows a structured decision-making workflow.

User
 │
 ▼
Agent
 │
 ├── Determine the issue type: Billing Issue
 │
 ▼
Skill Router
 │
 ▼
load_skill("billing_issue")
 │
 │   The Skill instructs the agent to:
 │   1. Confirm that this is a billing-related issue.
 │   2. Search the knowledge base (KB).
 │   3. If a documented solution exists, respond to the user.
 │   4. If no solution is found, escalate by creating a support ticket.
 │
 ▼
Agent
 │
 ▼
Select Tool: search_knowledge
 │
 ▼
Permission Check: ALLOW
 │
 ▼
search_knowledge()
 │
 ▼
AnythingLLM (RAG)
 │
 ▼
Retrieve the refund policy from the knowledge base.

If the RAG system cannot find a solution:

Agent
 │
 ▼
Skill determines that escalation is required.
 │
 ▼
Select Tool: create_ticket()
 │
 ▼
Permission Check: ASK
 │
 ▼
"Would you like me to create a support ticket?"
 │
 ├── Yes  → Create the support ticket.
 │
 └── No   → Stop the workflow.
