# Agent Apprentice Project — 4-Week Full-Stack Build

> A starter repo and project brief for apprentice teams building an **AI agent** on top of a running RAG service. You **run** a production-grade RAG app (AnythingLLM) as a knowledge service, then **build** a Flask + React agent that uses it as a tool — adding tool use, guardrails, an agent trace, and observability. The skills here (agents + LLM observability) are the dominant AI-engineering hiring trends for 2025/2026.

**Who this is for:** Apprentices who have just finished the Software Engineering program and are about to start the AI Data Science program or who have SE experience. This four-week group project is a visible way to show you're integrating AI into your learning, while practicing a professional software development lifecycle (SDLC) and Git workflow.

**How to use this repo:** This is a *starter template*. Once your team is formed, create your own copy to work in (see [Set up your team's repo](#set-up-your-teams-repo-do-this-first)) — don't commit to this shared starter. The README is your requirements doc and definition of "done." [`CONTRIBUTING.md`](./CONTRIBUTING.md) is your Git and team workflow. [`docs/anythingllm-setup.md`](./docs/anythingllm-setup.md) tells you how to stand up the RAG service you'll build against.

---

## Table of contents
1. [What you're building](#1-what-youre-building)
2. [Why an agent, and how it works](#2-why-an-agent-and-how-it-works)
3. [Tech stack (recommended)](#3-tech-stack-recommended)
4. [Quick start](#4-quick-start)
5. [Project menu — pick one](#5-project-menu--pick-one)
6. [Requirements / definition of done](#6-requirements--definition-of-done)
7. [Evaluating your agent](#7-evaluating-your-agent)
8. [Four-week timeline](#8-four-week-timeline)
9. [Team roles](#9-team-roles)
10. [Deployment & demo](#10-deployment--demo)
11. [Git & team workflow](#11-git--team-workflow)

---

## 1. What you're building

Two projects that talk to each other:

- **Project 1 — the knowledge service (you *run* it, you don't write it).** [AnythingLLM](https://github.com/Mintplex-Labs/anything-llm) is a production-grade, open-source RAG app. You'll run it locally, load documents into a workspace, and use its developer API. This is where your "retrieval" comes from — you operate it, you don't rebuild it.
- **Project 2 — the agent (you *build* this).** A Flask + React app where a user gives a goal, and your agent decides which **tools** to call — one of which is "search the knowledge base" (a call to Project 1's API) — loops until the task is done, shows its work, and is wired up with guardrails and observability.

The app idea is the vehicle, not the destination. Nobody expects a polished product in four weeks. What we expect is evidence you can work like a real engineering team: a clean Git history, reviewed pull requests, a backlog that maps to what you built, tests in CI, a running app anyone can spin up, and a demo with an honest retro. A modest agent that's well-engineered and observable beats an ambitious one that only works once on one laptop.

> **Why this shape?** Consuming a RAG service and building an agent on top of it is closer to real AI-engineering work than hand-rolling retrieval — and it puts your four weeks where the job market is: agents and observability.

### Skills & outcomes

By the end, you'll have practiced:

- **AI engineering:** building a real AI agent — tool calling, the reasoning loop, guardrails, and the habit of *evaluating and observing* an AI system instead of vibe-checking it.
- **Teamwork:** collaborating on a shared codebase with rotating roles and agile ceremonies (standups, planning, retros).
- **SDLC:** running a full development lifecycle — scoped issues, a definition of done, CI with tests, and shipping a working MVP under a deadline.
- **Git:** a professional workflow — feature branches, small reviewed pull requests, and giving and receiving code review.
- **Career/portfolio:** a demonstrable project — repo, demo recording, and observability logs — plus the stories to speak to it credibly in interviews.

---

## 2. Why an agent, and how it works

A plain chatbot answers once. An **agent** is given a goal and a set of **tools**, and it *loops*: it decides which tool to call, sees the result, and keeps going until the task is done. That loop is the skill.

```
  User goal
     │
     ▼
  ┌───────────────── AGENT LOOP (bounded by a max-step cap) ─────────────────┐
  │  LLM decides: which tool + what arguments?                               │
  │        │                                                                  │
  │        ▼                                                                  │
  │  call a tool ──▶  [ search_knowledge (→ AnythingLLM API) | calculator |  │
  │        │            run_sql | create_ticket | … ]                        │
  │        ▼                                                                  │
  │  observe result ──▶ enough to answer?  ──no──▶ loop again                 │
  │        │ yes                                                              │
  └────────┼──────────────────────────────────────────────────────────────┘
           ▼
  final answer + the full trace (every thought, tool call, and result) ─▶ React UI
```

Key concepts you'll learn: **tool/function calling**, the **observe→act loop**, **task decomposition**, **guardrails** (so a confused agent can't run forever or do damage), the **agent trace** (transparency = the agentic version of citations), and **observability** (logging every step so you can debug and improve the system).

---

## 3. Tech stack (recommended)

The stack is flexible, but this is what we recommend and support. Don't burn three days choosing a framework.

| Layer | Choice | Notes |
|-------|--------|-------|
| Knowledge service (Project 1) | **AnythingLLM** (run via Docker) | Open-source RAG app. You run it, load docs, and call its developer API. See [`docs/anythingllm-setup.md`](./docs/anythingllm-setup.md). |
| Agent backend (Project 2) | **Python + Flask** | Hosts the agent loop, the tools, and the observability log. |
| Frontend (Project 2) | **React (Vite)** | Chat UI **plus an agent-trace panel** showing each step. |
| Agent's reasoning model | **Ollama → `llama3.1:8b`** (default, free, local) | Must support **function/tool calling**. See the note below on reliability. |
| Database | **Postgres or SQLite** | Persist users, conversations, and the observability/trace log. |
| Auth | **Flask-Bcrypt** + sessions/JWT | Hash passwords; users see only their own conversations. |
| Running it | **Local dev servers** | Run AnythingLLM (Docker), then Flask + React. Docker Compose for Project 2 is an optional stretch. |

> **Architecture rule:** put your model calls behind a single `generate(messages, tools)` interface and your knowledge lookups behind a `search_knowledge(query)` function. Swapping the model or pointing at a deployed RAG service then becomes a one-file change.

> **About tool-calling reliability (read this).** Local models like `llama3.1:8b` *can* do function calling, but they are less reliable at it than frontier models — they'll sometimes pick the wrong tool or malform arguments. Mitigate with a **small, well-described tool set**, a **max-step cap**, and **argument validation with one retry**. If reliability is blocking you, a hosted frontier model with an Anthropic/OpenAI-compatible endpoint (for example MiniMax's Token Plan) is a one-line swap behind your `generate()` interface and dramatically improves tool use. Keep it free/local by default; treat hosted as an upgrade your mentors can enable.

---

## 4. Quick start

### Set up your team's repo (do this first)

Before anyone clones anything, **one teammate creates the repository your team will actually work in** — you don't all commit to this shared starter.

1. **One person creates the team repo from this starter.** Easiest path: on this repo's GitHub page click **"Use this template" → Create a new repository**. If that button isn't there, ask your mentor to enable it (note below) or **Fork** this repo instead. Name it for your team/project.
2. **Add your teammates as collaborators** — the new repo's **Settings → Collaborators**.
3. **Protect `main`** — **Settings → Branches → Add branch protection rule**: require a pull request with at least one approving review before merging. (Full rationale in [`CONTRIBUTING.md`](./CONTRIBUTING.md).)
4. **Everyone else clones the team repo** — that's the `git clone` in step 1 below.

> **Mentors:** to give students the "Use this template" button, open this starter repo's **Settings** and tick **Template repository**.

> Prerequisites: [Docker](https://www.docker.com/) (for AnythingLLM), [Node.js](https://nodejs.org/) (18+), [Python](https://www.python.org/) (3.11+), and [Ollama](https://ollama.com/download) — installed locally.

```bash
# 0. Start the knowledge service (Project 1) — full guide in docs/anythingllm-setup.md
#    Runs AnythingLLM at http://localhost:3001. Load the docs in knowledge_base/,
#    then create a developer API key inside its settings.
docker run -d -p 3001:3001 \
  -e STORAGE_DIR="/app/server/storage" \
  -v anythingllm_storage:/app/server/storage \
  --name anythingllm mintplexlabs/anythingllm

# 1. Clone your team's repo (the one you created above) (Project 2)
git clone <your-team-repo-url>
cd <your-team-repo>

# 2. Make sure Ollama is running (connection refused on 11434 means it isn't)
ollama serve
ollama pull llama3.1:8b       # agent reasoning model (supports tool calling)
ollama pull llama3.2:1b       # tiny model for fast local iteration

# 3. Configure env (paste your AnythingLLM API key + workspace here)
cp .env.example .env

# 4. Start Postgres + the agent backend (terminal 1)
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=agent -e POSTGRES_DB=agentdb \
  -v agentdb_data:/var/lib/postgresql/data --name agentdb postgres:16
python -m venv .venv && source .venv/bin/activate
pip install -r server/requirements.txt
flask --app server.app db upgrade   # create/update the schema
flask --app server.app run --debug  # http://localhost:5000

# 5. Start the frontend (terminal 2)
cd client
npm install
npm run dev                     # http://localhost:5173
```

> The agent backend, tools, and UI are **yours to build** — start from [`docs/seed-issues.md`](./docs/seed-issues.md). AnythingLLM is the only piece you run as-is.

### Suggested repo structure
```
.
├── README.md            ← this file (requirements & brief)
├── CONTRIBUTING.md      ← Git & team workflow — read this
├── .env.example         ← copy to .env; documents required config
├── .gitignore
├── client/              ← React app (Vite): chat UI + agent-trace panel
├── server/              ← Flask API
│   ├── app.py
│   ├── agent.py         ← the agent loop (decide → call tool → observe → repeat)
│   ├── tools/           ← one file per tool (search_knowledge, calculator, …)
│   ├── llm.py           ← generate(messages, tools) behind one interface
│   ├── observability.py ← decorator that logs each LLM/tool call
│   └── tests/
├── docs/
│   ├── AGENT_INSTRUCTIONS.md ← system prompts & tool calling instructions
│   ├── DESIGN_SYSTEM.md     ← UI design system & styling rules
│   ├── TICKET_SYSTEM.md     ← support triage agent specification
│   ├── anythingllm-setup.md ← how to run the RAG service (provided)
│   ├── eval.md              ← task-based eval template (provided; fill it in)
│   ├── seed-issues.md       ← starter backlog (provided)
│   └── plans/               ← implementation plans & progress trackers
├── knowledge_base/          ← docs to load into AnythingLLM (provided)
└── tests/fixtures/sample-data/ ← legacy test fixture data
```

### Common setup errors

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Agent's `search_knowledge` returns 401/403 | AnythingLLM API key missing/wrong | Create a key in AnythingLLM settings; put it in `.env` |
| `Connection refused` on `localhost:3001` | AnythingLLM container not running | `docker ps`; start it (see `docs/anythingllm-setup.md`) |
| `Connection refused` on `localhost:11434` | Ollama isn't running | `ollama serve` (or open the Ollama app) |
| Agent picks wrong tool / malformed args | Local model tool-calling is shaky | Fewer/clearer tools, validate args + retry once, or use a hosted model |
| Agent never stops | No max-step cap | Enforce a step limit in the loop (e.g. 6) |
| `port already in use` (3001/5000/5173) | Another process on that port | Stop it or change the port |
| `ModuleNotFoundError` at launch | Wrong Python version / venv not active | Python 3.11+ and `source .venv/bin/activate` |

---

## 5. Project menu — pick one

Every option is the *same agent backbone* (a bounded loop over a small tool set, where **one tool is `search_knowledge` calling your AnythingLLM service**) pointed at a different goal. That shared shape keeps teams comparable at presentations. **Each team picks a different one.**

### Option A — Knowledge Concierge
Answers questions from the knowledge base, and when it can't, takes an action.
*Tools:* `search_knowledge`, `create_ticket` (mock), `calculator`.
*Hook:* decides per question whether to answer, escalate, or "I don't know."

### Option B — Research Aide
Answers a multi-part question by combining the internal knowledge base with the open web.
*Tools:* `search_knowledge`, `web_search` (free/no-key source), `save_note`.
*Hook:* a written brief that cites both internal and external sources.

### Option C — Data + Docs Analyst
Answers questions that need both the documents and a dataset.
*Tools:* `search_knowledge`, `run_sql` (read-only SQLite), `calculator`.
*Hook:* "what does the policy say, and what do the numbers show?" in one answer. Great bridge to the data program.

### Option D — Support Triage Agent
Given an incoming ticket, looks up relevant articles, drafts a reply, and routes/escalates by priority.
*Tools:* `search_knowledge`, `create_draft`, `escalate`.
*Hook:* confirmation step before a draft is "sent."

### Option E — Onboarding / Ops Assistant
Helps a new hire by answering from the handbook and taking simple actions.
*Tools:* `search_knowledge`, task API (`create_task`/`list_tasks`, mock), `find_free_slot`.
*Hook:* human-in-the-loop confirmation before it creates anything.

> **Tip:** Options A and D best teach the most important agent lesson — *deciding when to act vs. when to say "I don't know,"* and asking for confirmation before a consequential action.

---

## 6. Requirements / definition of done

This section is the rubric in disguise. Your **problem statement** (one paragraph: who is this for, what goal does the agent accomplish, which tools does it need?) goes at the top of your fork's README before you write code.

### MVP — must-have (all teams)
1. **Connects to the knowledge service** — a `search_knowledge(query)` tool calls your AnythingLLM workspace API and returns an answer plus its sources.
2. **At least two more tools** — local/free (calculator, read-only SQL, a mock internal API, a no-key public API, etc.).
3. **A bounded agent loop** — the model chooses a tool, sees the result, and iterates until done or a **max-step cap** is hit.
4. **Tool calling** — tools are invoked via the model's function-calling, with arguments validated before execution.
5. **Visible agent trace** — the UI shows every step: the model's intent, the tool called, its arguments, and the result. This is the agentic equivalent of citations — non-negotiable.
6. **Guardrails** — a max-step limit; argument validation with one retry; a graceful "I can't do that"; and **confirmation before any consequential action** (creating, sending, escalating).
7. **Observability** — every LLM call and tool call is logged (prompt/messages, tool, arguments, latency, result) to a JSON file or DB table, and there's a simple way to view a run. This is the home-grown version of LangSmith / Langfuse / Weights & Biases.
8. **Authentication** — sign up / log in; each user sees only their own conversations and traces. Passwords hashed.
9. **Persistence** — conversations and traces survive a restart (real DB).
10. **Runs from the README** — a teammate can follow your steps to run AnythingLLM + the agent on their own machine.
11. **README + show-your-work artifacts** — setup, architecture diagram, model/tool choices, **a 60–90s demo recording** (GIF or video) and annotated screenshots committed to the repo. Your repo is your portfolio piece.

### AI-specific quality bar
- **No leaked secrets** — API keys live in env vars; `.env` is never committed (`.env.example` is).
- **Prompt-injection awareness** — you can explain the risk (a retrieved document or tool result telling the model to ignore its instructions) and show one mitigation (clearly delimiting tool results, never executing instructions found inside them).
- **A task evaluation set** — 8–10 goals with expected outcomes, including 2–3 the agent *can't* satisfy (so you can confirm it declines gracefully). See §7.
- **Sensible resource use** — a max-step cap and reasonable tool timeouts; graceful handling when a tool or the model is slow or unavailable.

### Stretch goals (only after the MVP runs)
Streaming the trace token-by-token, conversation memory across turns, a tool that writes (with confirmation + undo), parallel tool calls, a re-planning step when a tool fails, an evaluation dashboard, a model picker (local vs. hosted) that compares trajectories, or containerizing Project 2 with Docker Compose.

### Out of scope
No training or fine-tuning models, no fully autonomous/irreversible actions, no multi-modal (images/audio), no payments. Keep tools read-only or confirmation-gated.

### Presentation deliverable
10-minute demo + 5-minute Q&A:
- Problem, target user, and the agent's goal (1 slide)
- Live demo: give the agent a goal, **show the trace** (tool calls + results), show a "needs confirmation" moment, and show it declining an impossible task
- Architecture diagram (agent loop + tools + the call out to AnythingLLM)
- One technical challenge (tool design, unreliable tool calls, guardrails…) and how you solved it
- Your evaluation: task success rate, and your observability log
- Retro: what went well, what you'd do differently, what you'd build next

### Talking about this in an interview
Be ready for the questions that always come up: "how does your agent decide what to do?" (the loop + tool calling), "how do you stop it from doing something bad or looping forever?" (guardrails, max steps, confirmation), and "how do you know it works / how would you debug it?" (your task eval set + the observability log). Point at the trace and the logs — that's what separates a real agent from a demo.

---

## 7. Evaluating your agent

Agents are multi-step and stochastic, so "it worked once" is not evaluation. The lightweight version that fits four weeks:

- **Build a task set:** 8–10 goals with a known correct outcome, including 2–3 the agent *shouldn't* be able to complete (no tool for it, or out of scope) so you can confirm it declines instead of flailing. Keep it in `docs/eval.md`.
- **Score the outcome and the path:** for each task, did it reach the right result (success / partial / fail), and how many steps did it take? Fewer steps and the right tools = a healthier agent.
- **Use your observability log:** when a task fails, the trace tells you *where* — wrong tool, bad arguments, or a bad final answer.
- **Re-run after changes:** when you change the prompt, the tool descriptions, or the model, re-run the set and watch success rate and step count move.

The app's **Audit tab** (client) is the built-in run viewer: per-run traces, success rate, latency and token stats — use it when scoring eval runs.

Record every run in `docs/eval.md` so you can show progress over time — that "we changed X and success went from 5/10 to 9/10" story is the best thing you can show in a demo and an interview.

---

## 8. Four-week timeline

~20 working days, with a hard **"get it looping end-to-end early"** bias so the agent plumbing is debugged while it's cheap. Full Git ceremonies are in [`CONTRIBUTING.md`](./CONTRIBUTING.md).

### Week 1 — Foundations & a "walking skeleton" agent
*Run the RAG service; get a one-tool agent looping end-to-end.*

| Day | Focus | Outcome |
|-----|-------|---------|
| 1 | Kickoff, team norms, **create your team repo from this template + protect `main`**, pick project, problem statement | Team repo created with branch protection; roles assigned |
| 2 | Stand up AnythingLLM, load `knowledge_base/`, get an API key, explore its API; **start from `docs/seed-issues.md`** | RAG service answers a test query via curl; backlog on the board |
| 3 | Scaffold Flask + React; implement `search_knowledge` calling AnythingLLM | Backend returns a grounded answer from the knowledge service |
| 4 | First agent loop: model picks `search_knowledge`, calls it, answers (single tool, single step ok) | Goal in → tool call → answer, locally |
| 5 | Minimal React UI showing the answer **and a basic trace**; CI green | App answers one goal end-to-end, with a visible tool call |

> **The most important milestone is end of Week 1: a goal goes in, your agent calls the knowledge tool, and you can see the step it took.** Teams that defer the loop/tool plumbing to the final week lose the demo to a malformed-tool-call bug at 11pm.

### Week 2 — Tools, the loop & auth
*A real multi-step loop with more than one tool.*

| Day | Focus | Outcome |
|-----|-------|---------|
| 6 | Add a second and third tool (per your project); design clear tool schemas | Agent has a small, well-described toolbox |
| 7 | Real agent loop: iterate across multiple tool calls until done, with a **max-step cap** | Multi-step tasks complete; the loop always terminates |
| 8 | Argument validation + one retry on bad tool calls | Malformed calls are caught, not crashed |
| 9 | Authentication + per-user conversations | Users register/login; see only their own runs |
| 10 | Internal demo + feedback; backlog grooming; retro | Feedback logged as issues |

### Week 3 — Trace, guardrails, evaluation & observability
*Make it trustworthy — and prove it.*

| Day | Focus | Outcome |
|-----|-------|---------|
| 11 | Full agent-trace panel in the UI (intent, tool, args, result per step) | Anyone can see exactly what the agent did |
| 12 | Guardrails: "I can't do that," and **confirmation before consequential actions** | Agent asks before it creates/sends/escalates |
| 13 | Observability: log every LLM/tool call (prompt, tool, args, latency, result); a simple run viewer | Runs are inspectable after the fact |
| 14 | Build the 8–10 task eval set; capture a baseline; tune prompts/tool descriptions | Baseline recorded in `docs/eval.md`; measurable improvement |
| 15 | Testing pass (mock the model + tools in CI); fix top bugs; **mid-project demo** | Tests green; no leaked secrets |

### Week 4 — Polish, document & present
*Stop adding, start finishing.*

| Day | Focus | Outcome |
|-----|-------|---------|
| 16 | README polish + model/tool rationale; annotated screenshots | README accurate on a fresh checkout |
| 17 | Architecture diagram (agent loop + tools + AnythingLLM) | Diagram committed to `docs/ARCHITECTURE.md` |
| 18 | Record the demo (60–90s GIF or video) | Show-your-work artifacts committed |
| 19 | **Feature freeze** EOD; build slides; rehearse on the running app | Dry-run done, timing under 10 min |
| 20 | **Presentations + final retro** | Demos delivered; retros written up |

---

## 9. Team roles

Rotate these at the **start of each week — all four hats at once** — so over the four weeks everyone holds a different role and nobody owns all the Git/setup work. Post the current week's assignments at the top of your board:
- **Scrum lead** — runs standup, keeps the board honest.
- **Repo/DevOps owner** — guards `main`, owns CI, and keeps AnythingLLM + the README setup steps working on a fresh checkout.
- **Frontend lead** — owns the chat UI and the agent-trace panel.
- **Agent/backend lead** — owns the agent loop, tools, guardrails, and observability.

Everyone writes code, reviews PRs, and presents.

---

## 10. Deployment & demo

**The MVP bar is "runs from the README":** a teammate or mentor can clone the repo, start AnythingLLM, follow your setup steps, and run the full agent on their own machine. Keep your instructions accurate and test them on a fresh checkout — "works on my machine" is the bug this requirement exists to catch.

Since the demo is local, **your repo is your portfolio piece** (see requirement #11): a committed demo recording and the agent trace/observability log are what you point a recruiter to.

**Optional — Docker Compose (stretch):** wrap Project 2 (Flask + React + DB) in a `docker-compose.yml` so it comes up with one command alongside AnythingLLM.

**Optional — cloud deploy (stretch):** deploy the React frontend and Flask API to free tiers for a public URL. The agent's model and AnythingLLM still run on a team machine (or swap to a hosted model + hosted RAG endpoint behind your interfaces). A bonus, not the bar.

Whichever path: **get the loop running end-to-end in week 1.**

---

## 11. Git & team workflow

The Git workflow, branching strategy, PR process, code review norms, CI expectations, and definition of done all live in **[`CONTRIBUTING.md`](./CONTRIBUTING.md)**. Read it on day one — this part is graded as much as the app.

This repo is itself an example of the hygiene we're asking for: a clear README, a contributing guide, a `.gitignore`, an `.env.example` (never a real `.env`), PR and issue templates. Keep it that way as you build.

---

*This is a starting template — mentors should adjust the menu, timeline, model choice, and rigor to match the cohort's strength and available support.*
