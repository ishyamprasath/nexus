# Autonomous AI Agent System — Requirements Document

## 1. Overview

### 1.1 Project Title

Autonomous AI Agent System (Codename: **Nexus**)

### 1.2 Goal

Build a production-grade, hybrid autonomous AI agent system capable of accepting high-level goals from users, decomposing them into executable subtasks, reasoning about execution order, leveraging external tools, recovering from failures, and improving over time.

This orchestration platform leverages a cloud-hosted reasoning brain interacting seamlessly with a local computer-use agent (CUA) and a browser-use agent (BUA). It features planning, centralized relational and vector memory, multi-agent coordination, strict safety controls with human-in-the-loop UI interceptors, and observability built from the ground up.

### 1.3 Target Users

* Individual operators automating local desktop and browser tasks
* Internal engineering teams needing automated task execution
* Operations teams monitoring agent behavior and safety via customized UI dashboards

### 1.4 Timeline

* **Duration:** 14 Days (2-Week Sprint)
* **Sprint Cadence:** 2 days per major architectural module
* **Team Size:** 2 engineers

---

## 2. Functional Requirements

### 2.1 Planning & Reasoning Engine

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-01 | System shall accept a natural language goal and decompose it into an ordered list of subtasks | P0 |
| FR-02 | System shall support hierarchical task decomposition (subtasks can have sub-subtasks) | P0 |
| FR-03 | System shall dynamically re-plan when a subtask fails or produces unexpected results | P0 |
| FR-04 | System shall support multiple reasoning strategies: ReAct (reason-act-observe loop), Plan-then-Execute, and Reflexion (self-critique) | P1 |
| FR-05 | System shall enforce constraints on plans (max steps, time budget, token budget) | P1 |
| FR-06 | System shall support backtracking — abandoning a failing path and trying an alternative | P0 |

### 2.2 Memory System

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-07 | System shall maintain working memory (current task context) within JSONB columns alongside the execution state | P0 |
| FR-08 | System shall implement long-term and episodic memory via `pgvector` embeddings for semantic retrieval of past executions | P0 |
| FR-09 | System shall consolidate memory natively within PostgreSQL, removing the need for external vector databases | P1 |
| FR-10 | System shall perform memory consolidation (summarization, pruning stale entries) | P1 |
| FR-11 | System shall retrieve relevant memories via cosine similarity search before planning to inform strategy selection | P0 |

### 2.3 Tool Use & Environment Interaction

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-12 | System shall support a dynamic tool registry where tools can be added/removed at runtime using the Model Context Protocol (MCP) | P0 |
| FR-13 | System shall execute web-based browsing actions via Playwright MCP | P0 |
| FR-14 | System shall execute local desktop and shell operations via the OpenClaw Computer Use Agent (CUA) daemon | P0 |
| FR-15 | System shall communicate between the cloud backend and the local OpenClaw client via persistent WebSockets | P0 |
| FR-16 | System shall validate tool outputs before incorporating them into the task state | P1 |
| FR-17 | System shall retry failed tool calls with exponential backoff (max 3 retries) | P1 |

### 2.4 Multi-Agent Orchestration

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-18 | System shall implement a message-passing protocol between the planning backend and local agent clients | P1 |
| FR-19 | System shall support parallel execution of independent subtasks where environment limits allow | P2 |
| FR-20 | System shall implement dependency-aware scheduling (task B waits for task A) | P1 |
| FR-21 | System shall resolve conflicts when multiple tool outcomes produce contradictory results | P2 |

### 2.5 Safety & Control

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-22 | System shall classify every action as low-risk (auto-execute), medium-risk, or high-risk | P0 |
| FR-23 | System shall intercept high-risk actions (e.g., shell commands, filesystem changes) and stream them to the React frontend for explicit human approval before execution | P0 |
| FR-24 | System shall enforce custom JWT authentication to secure the frontend UI and WebSocket connections | P0 |
| FR-25 | System shall maintain a complete audit trail of all reasoning steps, decisions, and actions in Neon DB | P0 |
| FR-26 | System shall support an emergency stop mechanism that severs the WebSocket and halts all local OpenClaw activity | P0 |
| FR-27 | System shall never execute destructive operations without a frontend webhook confirmation | P0 |

### 2.6 Self-Improvement

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-28 | System shall evaluate task outcomes (success, partial success, failure) after completion | P1 |
| FR-29 | System shall embed and write execution strategies to `pgvector` to improve future success rates | P2 |
| FR-30 | System shall expose a benchmark suite to measure agent capability over time | P1 |

---

## 3. Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-01 | Latency for plan generation | < 10 seconds for goals with ≤ 10 subtasks |
| NFR-02 | End-to-end task completion (simple tasks) | < 2 minutes |
| NFR-03 | System availability | 99.5% uptime on Render |
| NFR-04 | Worker persistence | Keep-alive mechanism to prevent Render spin-down and WebSocket drops |
| NFR-05 | Memory retrieval latency | < 500ms for top-k vector search in Neon DB |
| NFR-06 | Audit log completeness | 100% of actions logged with timestamps |
| NFR-07 | Cloud/Local isolation | Cloud LLM cannot execute directly; must pass strictly formatted payloads to the local client |
| NFR-08 | Observability | Full OpenTelemetry tracing for every reasoning step |

---

## 4. Architecture Overview

```text
┌─────────────────────────────────────────────────────┐
│                 Render (Cloud)                      │
│                                                     │
│  ┌─────────────────┐       ┌────────────────────┐   │
│  │   React/Next.js │       │ FastAPI Web Service│   │
│  │   Static Site   │◄─JWT─►│   (Orchestrator)   │   │
│  └─────────────────┘       └──────┬─────┬───────┘   │
└───────────────────────────────────┼─────┼───────────┘
                                    │     │
                 ┌───WebSockets─────┘     └──HTTP──┐
                 ▼                                 ▼
┌──────────────────────────────────┐      ┌────────────────┐
│         Local Machine            │      │ External APIs  │
│                                  │      │                │
│  ┌────────────┐   ┌───────────┐  │      │ ┌────────────┐ │
│  │ OpenClaw   │   │ Playwright│  │      │ │ Gemma 4 31B│ │
│  │ Daemon     │   │ MCP Server│  │      │ └────────────┘ │
│  └────────────┘   └───────────┘  │      │ ┌────────────┐ │
│         CUA             BUA      │      │ │ Neon DB    │ │
└──────────────────────────────────┘      │ │ (pgvector) │ │
                                          │ └────────────┘ │
                                          └────────────────┘

```

---

## 5. Tech Stack

| Component | Technology |
| --- | --- |
| **Frontend** | React / Next.js |
| **Backend** | Python / FastAPI |
| **LLM** | `gemma-4-31b-it` via API |
| **Database / Memory** | Neon DB (PostgreSQL + `pgvector`) |
| **Cache / Queue** | Redis + Celery |
| **Browser Automation (BUA)** | Playwright MCP |
| **Desktop Automation (CUA)** | OpenClaw (Local Headless Daemon) |
| **Authentication** | Custom JWT |
| **Deployment** | Render (Web Service for API, Static Site for UI) |
| **Observability** | Langfuse / OpenTelemetry |

---

## 6. Acceptance Criteria

### 6.1 Core Agent Loop

* [ ] Given a natural language goal, the FastAPI backend produces a valid multi-step plan within 10 seconds via Gemma.
* [ ] The agent executes each step sequentially, streaming commands via WebSockets to the local tools.
* [ ] If a local step fails, the backend receives the error, re-plans, and attempts an alternative path.
* [ ] The full execution trace is available in the React UI audit log.

### 6.2 Memory

* [ ] The agent queries Neon DB with `pgvector` to retrieve relevant past context when starting a new task.
* [ ] Episodic memory correctly records task outcomes into PostgreSQL vector columns.

### 6.3 Tool Use

* [ ] System correctly routes browser tasks to Playwright MCP and native tasks to OpenClaw.
* [ ] Tool output validation catches malformed responses and triggers a backend retry.

### 6.4 Safety

* [ ] High-risk local actions (like `rm` or registry edits) are blocked in the OpenClaw execution queue until the JWT-authenticated React frontend sends an approval webhook.
* [ ] Budget exceeded → execution halts gracefully with a summary of work completed.
* [ ] Emergency stop halts the WebSocket stream within 2 seconds.

---

## 7. The 14-Day Implementation Plan

### Phase 1: Infrastructure & Auth (Days 1–2)

* **Goal:** Initialize repositories, database connections, and secure authentication.
* **Backend:** Initialize FastAPI. Connect to Neon DB. Build `SQLAlchemy` schemas for generic `jsonb` working memory. Write custom JWT generation and validation middleware.
* **Frontend:** Bootstrap Next.js. Build login screen, JWT storage logic, and the main dashboard layout shell.

### Phase 2: Core Brain & Vector Memory (Days 3–4)

* **Goal:** Integrate LLM reasoning and pgvector memory storage.
* **Backend:** Integrate the `gemma-4-31b-it` API. Write the core ReAct while-loop.
* **Database:** Enable `pgvector` in Neon DB. Write embedding logic for episodic task summaries and the cosine similarity search function.

### Phase 3: The Browser-Use Agent (Days 5–6)

* **Goal:** Enable web automation capabilities.
* **Integration:** Install Playwright MCP server. Map MCP tools (navigate, click, extract) to the Gemma tool registry in FastAPI.
* **Testing:** Ensure the backend successfully parses web goals and triggers Playwright sequences.

### Phase 4: The Computer-Use Agent (Days 7–8)

* **Goal:** Connect cloud brain to the local desktop.
* **Integration:** Set up WebSocket endpoints in FastAPI. Initialize local OpenClaw Node.js daemon and ensure a persistent connection.
* **Safety Rules:** Define strict Low/Medium/High risk classifications mapping local shell commands to the "High Risk" bucket in the orchestration layer.

### Phase 5: Orchestration & Delegation (Days 9–10)

* **Goal:** Seamlessly shift between BUA and CUA.
* **Logic:** Upgrade the planner to decompose complex prompts, handing web tasks to Playwright and local file tasks to OpenClaw within the same execution run.
* **State Management:** Ensure execution state streams accurately to Neon DB, handling cross-agent dependencies gracefully.

### Phase 6: The Safety Dashboard (Days 11–12)

* **Goal:** Build the human-in-the-loop interceptor.
* **Backend:** Expose `/approve` and `/reject` webhook endpoints to unpause the execution loop.
* **Frontend:** Build the React UI intercept components. Apply strong product design principles to visually render the exact shell command clearly, ensuring the user understands the blast radius before executing approvals.

### Phase 7: Deployment & Demo Polish (Days 13–14)

* **Goal:** Ship and harden the platform.
* **Deployment:** Push Next.js to Render Static Site and FastAPI to Render Web Service. Add an uptime ping (via cron-job.org or similar) to prevent the backend spin-down.
* **Validation:** Run E2E tests, verify JWT handling, test WebSocket latency, and record the final demo.

---

## 8. Ownership & Workstream Split

With a 2-person team executing a 14-day sprint, strict division of labor is required:

| Engineer | Primary Ownership | Secondary / Shared |
| --- | --- | --- |
| **Engineer 1** | Planning engine, Gemma orchestration, OpenClaw WebSocket worker, Playwright MCP integration | Integration tests, pgvector tuning |
| **Engineer 2** | React/Next.js Frontend, custom JWT implementation, UI design for safety dashboard, Neon DB schemas | Render deployment configs, FastAPI Gateway |

Both engineers share responsibility for:

* Architecture decisions and code review
* Local vs Cloud security boundaries
* Final end-to-end testing and recorded demo

---

## 9. Final Output Deliverables

The delivered system at the end of Day 14 shall include:

1. **Source code** — Python backend and React/Next.js frontend.
2. **API documentation** — OpenAPI spec for the FastAPI gateway.
3. **Database Schema** — SQLAlchemy/SQLModel definitions for Neon DB and `pgvector`.
4. **Deployment Configuration** — Render configurations and Keep-Alive cron job setup.
5. **Local Worker Runbook** — Instructions for initializing the OpenClaw Node.js daemon locally.
6. **System Demo** — Recorded walkthrough of the agent alternating between web browsing and local desktop manipulation, with a successful UI safety intervention.
