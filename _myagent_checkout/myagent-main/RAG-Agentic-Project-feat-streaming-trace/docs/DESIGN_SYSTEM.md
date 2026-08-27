# 🎨 Our Company Name — Design System & Brand Key

Welcome to the **Design System**, a standardized UI/UX framework built for the **Support Triage Agent & Observability Surface**.


---

## 🎯 Design Philosophy & Core Principles

1. **Enterprise Technical Authority:** Deep Slate (`#0F172A`) header tones combined with vibrant Indigo (`#4F46E5`) and Electric Cyan (`#06B6D4`) accents create a sleek, corporate-grade AI platform experience.
2. **Visual Transparency & Observability:** Agent tool executions are color-coded to provide instant visual feedback on what the agent is doing (RAG Search, Ticket Creation, IT Escalations, or LLM Reasoning).
3. **Consistency Token Architecture:** All components reference centralized tokens from [`client/src/theme.ts`](file:///Users/daniel/code/flatiron/RAG-Agentic-Project/client/src/theme.ts) rather than ad-hoc inline styles.

---

## 🎨 Color Palette & Tokens

| Token Name | Hex Code | Purpose / Usage |
| :--- | :--- | :--- |
| **`BRAND_TOKENS.darkSlate`** | `#0F172A` | Top Navigation Header, Deep Surfaces |
| **`BRAND_TOKENS.primary`** | `#4F46E5` | Primary Indigo Actions, User Chat Bubbles, Active Navigation |
| **`BRAND_TOKENS.secondary`** | `#06B6D4` | Electric Cyan Accent, AI Agent Badges, Highlights |
| **`BRAND_TOKENS.canvasBg`** | `#F8FAFC` | App Canvas Background |
| **`BRAND_TOKENS.borderLight`** | `#E2E8F0` | Subtle Card & Divider Borders |

---

## 🛠️ Tool Observability Color Key (`TOOL_COLOR_KEY`)

When inspecting agent execution traces in the **Trace Panel** or **Audit Surface**, tools are categorized with distinct visual badges:

| Tool Action | Icon & Label | Background | Text / Icon Color |
| :--- | :--- | :--- | :--- |
| **`search_knowledge`** | 🔍 Knowledge Search | `#E0F2FE` (Sky Blue) | `#0284C7` |
| **`escalate_it_issue`** | 🚨 IT Escalation | `#FFE4E6` (Rose Red) | `#E11D48` |
| **`create_ticket`** | 📝 Ticket Creation | `#FEF3C7` (Amber Gold) | `#D97706` |
| **`model_call`** | 🧠 LLM Reasoning | `#F3E8FF` (Violet) | `#7C3AED` |

---

## 📱 Components Overview

- **AppBar & Header:** Glassmorphic navigation header featuring enterprise title *"Acme Intelligence Hub"*, version chip *"Support Triage v1.0"*, and real-time status pill `🟢 KB Online`.
- **Chat Bubbles:** Distinct avatars (🤖 for Support Agent, 👤 for User) with gradient user bubbles (`#4F46E5` → `#3730A3`) and clean white assistant bubbles with 1px border elevation.
- **Trace Panel Accordions:** Dark syntax blocks (`#0F172A`) for tool arguments and model input payloads with color-coded status chips.
