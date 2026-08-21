# ApexCare: Enterprise Support Triage Agent & RAG Knowledge Service

[![CI Build](https://img.shields.io/github/actions/workflow/status/freeleons/RAG-Agentic-Project/ci.yml?branch=main&style=for-the-badge&logo=github)](https://github.com/freeleons/RAG-Agentic-Project/actions)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?style=for-the-badge&logo=python)](https://python.org)
[![Flask](https://img.shields.io/badge/Backend-Flask-000000?style=for-the-badge&logo=flask)](https://flask.palletsprojects.com/)
[![React](https://img.shields.io/badge/Frontend-React_18_--_Vite-61DAFB?style=for-the-badge&logo=react)](https://react.dev/)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL_16-336791?style=for-the-badge&logo=postgresql)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](./LICENSE)

> **💡 The Problem:** In enterprise IT and HR operations, support specialists spend up to **40% of their workday** manually hunting down fragmented policy documents across wikis and PDFs. This friction leads to inconsistent answers, slow ticket resolution times, and agent burnout.
> 
> **🎯 The Solution:** **ApexCare** is a production-grade, multi-tenant **Autonomous AI Support Triage Agent** and **RAG Knowledge Service** built from first principles using Python/Flask and React (TypeScript). It automates policy retrieval, drafts grounded responses with an embedded copilot (**Pip**), and keeps specialists firmly in control through a **bounded reasoning loop**, **stateful Human-in-the-Loop (HITL) safety**, **prompt injection defense boundaries**, and comprehensive **observability & audit telemetry**.

<details>
  <summary><b>📑 Table of Contents (Click to expand)</b></summary>

  - [🎥 Demos & Visual Showcase](#-demos--visual-showcase)
  - [🏗️ System Architecture](#️-system-architecture)
  - [🌟 Key Engineering Highlights](#-key-engineering-highlights)
  - [🛡️ AI Safety & Prompt Injection Protection](#️-ai-safety--prompt-injection-protection)
  - [🛠️ Tech Stack](#️-tech-stack)
  - [🧭 Claude Code Harness (`.claude/`)](#-claude-code-harness-claude)
  - [🚀 Quick Start & Installation](#-quick-start--installation)
  - [🧪 Testing & Validation](#-testing--validation)
  - [👥 Authors & Team](#-authors--team)
  - [📄 License](#-license)
</details>

---

## 🎥 Demos & Visual Showcase

> [!TIP]
> **Core Concept:** Rather than leaving the support specialist in a generic chat interface, ApexCare introduces a unified **Ticket Triage Workbench** dashboard. The agent acts as an embedded assistant directly grounding replies with policy retrieval and compiling draft responses, with every reasoning step audited and trace-logged.

### 🎬 Live Demo: Copilot Policy Grounding & Reply Drafting
<div align="center">
  <img src="./assets/draft-with-pip-demo.webp" alt="Draft with Pip Live Demo" width="92%" style="border-radius: 10px; border: 1px solid #e2e8f0; box-shadow: 0 4px 10px rgba(0,0,0,0.08);" />
  <p><i>Live demonstration: Triggering "Draft with Pip" on an active ticket, retrieving grounded policy knowledge via RAG, streaming intermediate reasoning steps, and copying the generated draft directly into the reply editor.</i></p>
</div>

<br/>

### 🤖 Pip Assistant: 3-in-1 Copilot Capabilities
<div align="center">
  <img src="./assets/pip_chat.webp" alt="Pip Assistant Copilot" width="48%" style="border-radius: 10px; border: 1px solid #e2e8f0; box-shadow: 0 4px 10px rgba(0,0,0,0.08);" />
</div>

The embedded **Pip Assistant** serves as an intelligent sidekick equipped with three primary operational modes:
* **💬 1. General HR/IT Q&A:** Direct conversational reasoning to answer specialist queries and troubleshoot edge cases.
* **🔍 2. Autonomous Knowledge Base Search:** Triggers the `search_knowledge` tool to semantically retrieve relevant sections from indexed policy documents with live execution traces.
* **✍️ 3. Grounded Reply Drafting:** Synthesizes policy constraints into polite, structured customer responses with one-click **"Copy"** and direct workbench integration.

<br/>

### 📚 Policy Knowledge Base & RAG Retrieval
<div align="center">
  <img src="./assets/knowledge_base.webp" alt="Policy Knowledge Base Viewer" width="92%" style="border-radius: 10px; border: 1px solid #e2e8f0; box-shadow: 0 4px 10px rgba(0,0,0,0.08);" />
  <p><i>Interactive Knowledge Base viewer displaying company policies (Markdown & PDFs) synchronized and indexed into the AnythingLLM vector engine.</i></p>
</div>

<br/>

### 📊 System Analytics & Observability Dashboard
<div align="center">
  <img src="./assets/audit_logs.webp" alt="Observability & Audit Dashboard" width="92%" style="border-radius: 10px; border: 1px solid #e2e8f0; box-shadow: 0 4px 10px rgba(0,0,0,0.08);" />
  <p><i>Real-time observability panel monitoring agent execution latency distributions, token volume consumption, success rates, and granular step-by-step traces.</i></p>
</div>

<br/>

### 🔐 Authentication & Recruiter 1-Click Demo Mode
<div align="center">
  <img src="./assets/auth.webp" alt="Sign In & Recruiter Demo Mode" width="92%" style="border-radius: 10px; border: 1px solid #e2e8f0; box-shadow: 0 4px 10px rgba(0,0,0,0.08);" />
  <p><i>Authentication portal equipped with an instant "Recruiter Demo Mode" button to launch the live demo environment immediately with pre-loaded tickets.</i></p>
</div>

<br/>

### 🧭 Interactive Guided Tour & Onboarding
<div align="center">
  <img src="./assets/tutorial.webp" alt="Guided Interactive Tutorial" width="92%" style="border-radius: 10px; border: 1px solid #e2e8f0; box-shadow: 0 4px 10px rgba(0,0,0,0.08);" />
  <p><i>Interactive walkthrough modal guiding new specialists through ticket selection, Pip Copilot drafting, and knowledge exploration.</i></p>
</div>

---

## 🏗️ System Architecture

The application is structured into decoupled, stateless service layers backed by a PostgreSQL database and connected to AnythingLLM via a REST vector index connector:

```mermaid
flowchart TD
    subgraph Client ["Client Layer (React + Vite + TS)"]
        UI["Triage Workbench\n(Sidebar Queue + Central Editor)"]
        Copilot["AICopilotWidget\n(Handbook Policy Q&A Widget)"]
        AuditUI["Observability Dashboard\n(Token Metrics + Traces)"]
    end

    subgraph Backend ["Agent Engine Layer (Flask + SQLAlchemy)"]
        API["REST API Endpoints\n(/api/tickets, /api/chat, /api/runs)"]
        Guard["Guardrail Validator\n(HITL Guard, Timeout, Schema Validator)"]
        Engine["Agent Bounded Loop\n(server/agent.py decide-act-observe)"]
        LLM_Adapter["LLM Provider Interface\n(Ollama / OpenAI API Adapter)"]
        Obs["Observability Logger\n(server/observability.py decorator)"]
    end

    subgraph Data ["Data & Storage Layer"]
        PG[("PostgreSQL Database\n(Users, Runs, RunSteps, Tickets)")]
    end

    subgraph Services ["External Services & Tools"]
        KB["AnythingLLM Vector DB\n(RAG Policy Knowledge Service)"]
        Tools["Helpdesk Actions\n(list_tickets, update_ticket, escalate)"]
    end

    UI -->|User action approval / patch| API
    Copilot -->|Direct message query| API
    AuditUI -->|View real-time trace telemetry| API
    API --> Guard
    Guard --> Engine
    Engine <-->|Next Action Inference| LLM_Adapter
    Engine -->|Record execution step| Obs
    Obs -->|Write step latencies & logs| PG
    Engine -->|Execute RAG fetch| KB
    Engine -->|Execute ticket updates| Tools
    Engine -->|Stateful suspension| API
```

---

## 🌟 Key Engineering Highlights

### 1. Custom Bounded Agent Loop (No Framework Lock-in)
* **First-Principles Design:** Built directly in [`server/agent.py`](file:///Users/daniel/code/flatiron/RAG-Agentic-Project/server/agent.py) without heavy black-box orchestrators (e.g. LangChain or AutoGen) to ensure complete transparency.
* **Deterministic Bounds:** Governed by strict step limits (`MAX_AGENT_STEPS = 6`) and tool timeouts (`TOOL_TIMEOUT_SECONDS = 30`) to prevent runaway recursive reasoning loops, hallucinated cycles, or API cost overruns.
* **Schema Validation & Self-Correction:** Model tool calls are checked against JSON schemas before execution. Schema mismatches trigger a structured error response back to the agent with a 1-retry self-correction cap.
* **Transient LLM retries:** Timeouts and 429s retry inside [`generate()`](./server/llm.py) with exponential backoff and jitter, capped so retries cannot stall a run for ~60s.

### 2. Human-in-the-Loop (HITL) Execution Safety
* **Consequential Actions Guarded:** Critical actions (like writing ticket drafts or routing escalations) are marked as `requires_confirmation = True`. 
* **Stateful Resumption:** On identifying a consequential action, the loop halts, saves its state to database logs as a `PendingAction`, and enters a `needs_confirmation` status. It resumes cleanly once the support specialist clicks approve or reject in the UI.

### 3. Decoupled RAG Knowledge Integration
* Implements a vector-index retrieval query via AnythingLLM API behind a clean `search_knowledge` tool interface. This decouples the core reasoning engine from vendor-specific vector store architectures.

### 4. Telemetry & Analytics Dashboard
* **Decorator Telemetry:** Logging decorators in [`server/observability.py`](file:///Users/daniel/code/flatiron/RAG-Agentic-Project/server/observability.py) capture completion/prompt tokens, model info, execution latency (in milliseconds), tool parameters, and raw JSON logs.
* **Provider and error type:** Each run records `provider` (`ollama` or `openai_compatible`); failed steps store `error_type` (`Timeout`, `ConnectionError`, …) so traces can tell which backend served the run and why a call failed.
* **Analytical UI:** The Audit Dashboard visualizes token volume trends, failure statistics, trace trees, and latency buckets (20%, 50%, 90% latency percentiles).

---

## 🛡️ AI Safety & Prompt Injection Protection

| Protection Layer | Strategy |
| :--- | :--- |
| **XML Data Isolation** | Retrieval and tool responses are wrapped inside `<tool_result>` XML tags. The system prompt instructs the agent to treat this content strictly as untrusted data, neutralizing instructions inside documents. |
| **Strict Read-Only Queue** | Ticket queue operations are read-only from the user interface; ticket creation and deletion are disabled to preserve the queue as a strict, un-compromised system of record. |
| **Session Isolation** | Token-based session authentication separates workspaces; users are partitioned and cannot access or audit runs from other specialists. |

---

## 🛠️ Tech Stack

| Component | Technology | Role |
| :--- | :--- | :--- |
| **Frontend** | React 18, TypeScript, Vite, Vanilla CSS | Dashboard UI, trace panel, audit graphs |
| **Backend** | Python 3.11+, Flask, SQLAlchemy | Bounded reasoning loop, tool router, state management, REST endpoints |
| **Database** | PostgreSQL 16 / SQLite | Run logs, users, runs, steps, and tickets |
| **LLM Provider** | Ollama (`llama3.1:8b`) / OpenAI | Swap reasoning models via a unified LLM interface |
| **Knowledge Engine** | AnythingLLM (Dockerized) | Vector database, semantic retrieval, indexing |
| **Testing** | Pytest, Vitest | Parallel unit & integration testing |

---

## 🧭 Claude Code Harness (`.claude/`)

This repo ships a small, honest agentic harness under [`.claude/`](./.claude/) so teammates can explore and explain the codebase the same way. Counts match what is actually checked in:

| Kind | Count | Location |
| :--- | :---: | :--- |
| **Hooks** | 1 config (`SessionStart`, `PostToolUse`) | [`.claude/hooks.json`](./.claude/hooks.json) |
| **Skills** | 2 | [`.claude/skills/`](./.claude/skills/) |
| **Subagent** | 1 | [`.claude/agents/`](./.claude/agents/) |
| **Settings** | permissions + default plan mode | [`.claude/settings.json`](./.claude/settings.json) |

* **Hooks** — `SessionStart` opens an exploration-mode notes file; `PostToolUse` on `Read` appends a timestamped line to `./notes/exploration-log.txt`.
* **Skills**
  * [`explain-feature`](./.claude/skills/explain-feature/SKILL.md) — explain a feature with exact file/line citations
  * [`trace-data-flow`](./.claude/skills/trace-data-flow/SKILL.md) — walk a request from entry point to output in runtime order
* **Subagent** — [`code-explorer`](./.claude/agents/code-explorer.md) (Read / Grep / Glob only) returns a structured module summary to the parent agent.

---

## 🚀 Quick Start & Installation

### Prerequisites
* **Docker** (for Postgres and AnythingLLM)
* **Python 3.11+**
* **Node.js 18+** & `npm`
* **Ollama** (for local reasoning model execution)

### 1. Spin up Services (Docker)
```bash
# 1. Spin up AnythingLLM RAG Service (Port 3001)
#    Create a developer API key inside AnythingLLM settings once active.
docker run -d -p 3001:3001 \
  -e STORAGE_DIR="/app/server/storage" \
  -v anythingllm_storage:/app/server/storage \
  --name anythingllm mintplexlabs/anythingllm

# 2. Spin up PostgreSQL DB (Port 5432)
docker run -d -p 5432:5432 \
  -e POSTGRES_PASSWORD=agent \
  -e POSTGRES_DB=agentdb \
  -v agentdb_data:/var/lib/postgresql/data \
  --name agentdb postgres:16
```

### 2. Configure Environment
```bash
# Download the local reasoning model via Ollama
ollama serve
ollama pull llama3.1:8b

# Setup environment variables
cp .env.example .env
# Edit .env with your ANYTHINGLLM_API_KEY, ANYTHINGLLM_WORKSPACE, and DATABASE_URL
```

### 3. Backend Setup (Flask API)
```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# Install requirements
pip install -r server/requirements.txt

# Run migrations and start backend API (Port 5000)
flask --app server.app db upgrade
flask --app server.app run --debug
```

### 4. Frontend Setup (React App)
```bash
cd client
npm install
npm run dev # Launches at http://localhost:5173
```

---

## 🧪 Testing & Validation

Automated testing enforces code validity on both ends before merge pipelines execute.

```bash
# Run backend python unit/integration tests
.venv/bin/pytest

# Run frontend UI tests
cd client
npm test -- --run
```

### 🎯 Agent Evaluation & Golden Task Set
In addition to automated unit and integration tests, end-to-end agent decision-making, tool routing, and grounded policy retrieval are measured against a concrete 9-task golden set (covering factual policy lookups and graceful out-of-scope refusals). See [`docs/eval.md`](./docs/eval.md) for the benchmark task matrix, scoring criteria, and run logs.

---

## 👥 Authors & Team

<table align="center">
  <tr>
    <td align="center" width="33%">
      <a href="https://github.com/freeleons">
        <img src="./assets/jue.webp" width="120" alt="Jameson Wang" /><br />
        <sub><b>Jameson Wang</b></sub>
      </a>
      <br />
      <a href="https://github.com/freeleons"><img src="https://img.shields.io/badge/GitHub-181717?style=flat-square&logo=github&logoColor=white" alt="GitHub" /></a>
      <a href="https://www.linkedin.com/in/freeleons/"><img src="https://img.shields.io/badge/LinkedIn-0077B5?style=flat-square&logo=linkedin&logoColor=white" alt="LinkedIn" /></a>
    </td>
    <td align="center" width="33%">
      <a href="https://github.com/shuziyoshi">
        <img src="./assets/shuzi.webp" width="120" alt="Wendy Gong" /><br />
        <sub><b>Wendy Gong</b></sub>
      </a>
      <br />
      <a href="https://github.com/yoshi182023"><img src="https://img.shields.io/badge/GitHub-181717?style=flat-square&logo=github&logoColor=white" alt="GitHub" /></a>
      <a href="https://www.linkedin.com/in/yoshi-gong/"><img src="https://img.shields.io/badge/LinkedIn-0077B5?style=flat-square&logo=linkedin&logoColor=white" alt="LinkedIn" /></a>
    </td>
    <td align="center" width="33%">
      <a href="https://github.com/ddgiovinazzo">
        <img src="./assets/daniel.webp" width="120" alt="Daniel Giovinazzo" /><br />
        <sub><b>Daniel Giovinazzo</b></sub>
      </a>
      <br />
      <a href="https://github.com/ddgiovinazzo"><img src="https://img.shields.io/badge/GitHub-181717?style=flat-square&logo=github&logoColor=white" alt="GitHub" /></a>
      <a href="https://www.linkedin.com/in/ddgiovinazzo/"><img src="https://img.shields.io/badge/LinkedIn-0077B5?style=flat-square&logo=linkedin&logoColor=white" alt="LinkedIn" /></a>
    </td>
  </tr>
</table>

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](./LICENSE) for details.

