# 🎫 Support Ticket Management System & Agentic CRUD Architecture

## Overview

The **Support Ticket System** provides a complete enterprise ticketing desk for users and AI Chatbot agents. It combines a full-stack REST API, a dedicated frontend management UI, and 4 agentic CRUD tools integrated into the LLM function-calling pipeline.

---

## 🏗️ Architecture & Component Design

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Client UI Surface (React)                         │
├──────────────────────┬─────────────────────────────┬────────────────────────┤
│       💬 Chat        │         🎫 Tickets          │        📊 Audit        │
│   (Agentic Engine)   │     (Ticket Desk UI)        │  (Observability Runs)  │
└──────────┬───────────┴──────────────┬──────────────┴────────────────────────┘
           │                          │
           ▼                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Flask Backend REST API (`/api/*`)                     │
├──────────────────────────────────────┬──────────────────────────────────────┤
│  Agent Engine (`server/agent.py`)    │  Ticket REST API (`server/routes.py`)│
│  - `list_tickets` (auto)             │  - `GET /api/tickets`                │
│  - `create_ticket` (pause ⏸️)        │  - `POST /api/tickets`               │
│  - `update_ticket` (pause ⏸️)        │  - `PATCH /api/tickets/<id>`         │
│  - `delete_ticket` (pause ⏸️)        │  - `DELETE /api/tickets/<id>`        │
└──────────────────────────────────────┴──────────────────────────────────────┘
                                      │
                                      ▼
                      SQLite Database (`server/models.py`)
```

---

## 🗄️ Database Model (`Ticket`)

Defined in [`server/models.py`](file:///Users/daniel/code/flatiron/RAG-Agentic-Project/server/models.py):

| Attribute | Type | Constraints / Defaults | Description |
| :--- | :--- | :--- | :--- |
| `id` | `Integer` | Primary Key | Unique ticket ID |
| `user_id` | `Integer` | Foreign Key (`users.id`) | Ticket owner |
| `title` | `String(120)` | Non-nullable | Short summary of issue |
| `description` | `Text` | Non-nullable | Full problem details |
| `status` | `String(20)` | Default `"open"` | `"open"`, `"in_progress"`, `"resolved"`, `"closed"` |
| `priority` | `String(20)` | Default `"medium"` | `"low"`, `"medium"`, `"high"`, `"urgent"` |
| `category` | `String(50)` | Default `"General"` | `"IT"`, `"HR"`, `"Billing"`, `"Facilities"`, `"General"` |
| `created_at` | `DateTime` | UTC Timestamp | Creation timestamp |
| `updated_at` | `DateTime` | UTC Timestamp | Last update timestamp |

---

## ⚙️ Agentic CRUD Tools (`server/tools/ticket_tools.py`)

Registered in [`server/tools/__init__.py`](file:///Users/daniel/code/flatiron/RAG-Agentic-Project/server/tools/__init__.py):

### 1. `list_tickets`
- **Confirmation Required:** ❌ `False` (Direct execution)
- **Description:** Allows the agent to query open/filtered tickets when the user asks about existing issues.
- **Parameters:** `status` (optional), `priority` (optional), `category` (optional).

### 2. `create_ticket`
- **Confirmation Required:** 🟢 `True` (Human-in-the-Loop Confirmation Pause ⏸️)
- **Description:** Creates a ticket when the user instructs the chatbot to log an issue.
- **Parameters:** `title`, `description`, `priority`, `category`.

### 3. `update_ticket`
- **Confirmation Required:** 🟢 `True` (Human-in-the-Loop Confirmation Pause ⏸️)
- **Description:** Updates ticket status or priority (e.g. marking a ticket as resolved or urgent).
- **Parameters:** `ticket_id`, `status` (optional), `priority` (optional), `title` (optional), `description` (optional).

### 4. `delete_ticket`
- **Confirmation Required:** 🟢 `True` (Human-in-the-Loop Confirmation Pause ⏸️)
- **Description:** Deletes a ticket record upon explicit user request.
- **Parameters:** `ticket_id`.

---

## 🔒 Security & Human-in-the-Loop Policies

To prevent AI hallucination risks or unwanted database modifications:
1. **User Isolation:** All ticket operations are strictly scoped to `g.user.id`. A user cannot read, update, or delete another user's tickets.
2. **Confirmation Boundary:** All state-modifying tools (`create_ticket`, `update_ticket`, `delete_ticket`) set `requires_confirmation = True`. The agent pauses execution, creates a `PendingAction` record, and waits for explicit user approval (via the UI **Approve / Reject** buttons).

---

## 🤖 Floating AI Triage Assistant Widget

Integrated into the **Tickets Page** ([`client/src/tickets/TicketChatWidget.tsx`](file:///Users/daniel/code/flatiron/RAG-Agentic-Project/client/src/tickets/TicketChatWidget.tsx)):
- **Floating Action Button (🤖):** Fixed in the bottom-right corner of the Tickets Desk.
- **Interactive Assistant Panel:** Opens a 380px popover widget overlaying the page, allowing users to ask the AI agent to list, update, resolve, or delete tickets directly from the Tickets surface.
- **"Ask AI" Ticket Card Button:** Every ticket card features a **"🤖 Ask AI"** button. Clicking it launches the assistant pre-loaded with a prompt targeting that specific ticket.
- **Auto-Refresh Sync:** When the AI agent executes a ticket tool (e.g. `update_ticket`), the widget automatically refreshes the Ticket Desk grid in real time!


---

## 🧪 Sample Prompts for Testing

Try these prompts in the **Chat** tab to test agentic ticket CRUD operations:

1. **Create Ticket:**  
   *"Can you file a high priority IT support ticket for my broken external monitor?"*  
   *(Verify the run pauses for Approve / Reject confirmation!).*

2. **List Tickets:**  
   *"What support tickets do I currently have open?"*

3. **Update Ticket Status:**  
   *"Please update ticket #1 to resolved."*  
   *(Verify the confirmation pause triggers before updating).*
