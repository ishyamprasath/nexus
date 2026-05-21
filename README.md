# Autonomous AI Agent System — Comprehensive Requirements Document

## 1. Overview

### 1.1 Project Title

Autonomous AI Agent System (Codename: **Nexus**)

### 1.2 Goal

Build a production-grade, hybrid autonomous AI agent system capable of accepting high-level goals from users, decomposing them into executable subtasks, reasoning about execution order, leveraging external tools, recovering from failures, and improving over time.

This orchestration platform leverages a cloud-hosted reasoning brain interacting seamlessly with a visual, desktop-native computer-use agent (CUA) and a browser-use agent (BUA). It features planning, centralized relational and vector memory, multi-agent coordination, strict safety controls with human-in-the-loop UI interceptors, and observability built from the ground up.

### 1.3 Target Users

* Individual operators automating local desktop and browser tasks.
* Internal engineering teams needing automated task execution.
* Operations teams monitoring agent behavior and safety via customized UI dashboards.

### 1.4 Timeline

* **Duration:** 8 Days (Sprint)
* **Sprint Cadence:** 1 day per major architectural module
* **Team Size:** 1 engineer

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
| FR-14 | System shall execute visual local desktop operations via a forked UI-TARS desktop client | P0 |
| FR-15 | System shall route desktop screenshots from UI-TARS to a hosted Hugging Face VLM to retrieve click/keyboard coordinates | P0 |
| FR-16 | System shall communicate between the cloud backend and the local UI-TARS client via persistent WebSockets | P0 |
| FR-17 | System shall validate tool outputs before incorporating them into the task state | P1 |
| FR-18 | System shall retry failed tool calls with exponential backoff (max 3 retries) | P1 |

### 2.4 Multi-Agent Orchestration

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-19 | System shall implement a message-passing protocol between the cloud planning backend and local agent clients | P1 |
| FR-20 | System shall support parallel execution of independent subtasks where environment limits allow | P2 |
| FR-21 | System shall implement dependency-aware scheduling (task B waits for task A) | P1 |
| FR-22 | System shall resolve conflicts when multiple tool outcomes produce contradictory results | P2 |

### 2.5 Safety & Control

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-23 | System shall classify every action as low-risk (auto-execute), medium-risk, or high-risk | P0 |
| FR-24 | System shall intercept high-risk actions (e.g., terminal commands, system settings) and pause execution in the local React/Electron UI for explicit human approval | P0 |
| FR-25 | System shall enforce custom JWT authentication to secure the frontend UI and WebSocket connections | P0 |
| FR-26 | System shall maintain a complete audit trail of all reasoning steps, decisions, and actions in Neon DB | P0 |
| FR-27 | System shall support an emergency stop mechanism that severs the WebSocket and halts all local activity | P0 |
| FR-28 | System shall never execute destructive operations without a frontend webhook confirmation | P0 |

### 2.6 Self-Improvement

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-29 | System shall evaluate task outcomes (success, partial success, failure) after completion | P1 |
| FR-30 | System shall embed and write execution strategies to `pgvector` to improve future success rates | P2 |
| FR-31 | System shall expose a benchmark suite to measure agent capability over time | P1 |

---

## 3. Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-01 | Latency for plan generation | < 10 seconds for goals with ≤ 10 subtasks |
| NFR-02 | End-to-end task completion (simple tasks) | < 2 minutes |
| NFR-03 | System availability | 99.5% uptime on Render |
| NFR-04 | Worker persistence | Keep-alive cron mechanism to prevent Render spin-down and WebSocket drops |
| NFR-05 | Memory retrieval latency | < 500ms for top-k vector search in Neon DB |
| NFR-06 | Cloud/Local isolation | Cloud LLM cannot execute directly; must pass strictly formatted payloads to the local client |
| NFR-07 | VLM Cold Start | System must gracefully handle 15-30s cold starts from the ZeroGPU space |

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
│  │ UI-TARS    │   │ Playwright│  │      │ │ Gemma 4 31B│ │
│  │ Desktop    │   │ MCP Server│  │      │ └────────────┘ │
│  └──────┬─────┘   └───────────┘  │      │ ┌────────────┐ │
│         │         BUA            │      │ │ Neon DB    │ │
└─────────┼────────────────────────┘      │ │ (pgvector) │ │
          │                               │ └────────────┘ │
          │                               │ ┌────────────┐ │
          └───────Screenshots────────────►│ │ HF ZeroGPU │ │
          ◄───────Coordinates─────────────│ │ VLM Space  │ │
                                          │ └────────────┘ │
                                          └────────────────┘

```

---

## 5. Tech Stack

| Layer | Technology |
| --- | --- |
| **Frontend Dashboard** | React / Next.js |
| **Backend Orchestrator** | Python / FastAPI |
| **Cloud Brain (Text)** | `gemma-4-31b-it` via API |
| **Database / Memory** | Neon DB (PostgreSQL + `pgvector`) |
| **Browser Automation (BUA)** | Playwright MCP |
| **Desktop Automation (CUA)** | UI-TARS Desktop (Forked Tauri App) |
| **Vision Model (CUA Brain)** | UI-TARS-7B or Qwen2.5-VL via Hugging Face Gradio Space |
| **Authentication** | Custom JWT |
| **Deployment** | Render (Web Service for API, Static Site for UI) |
| **Observability** | OpenTelemetry |

---

## 6. Acceptance Criteria

### 6.1 Core Agent Loop

* [ ] Given a natural language goal, the FastAPI backend produces a valid multi-step plan within 10 seconds via Gemma.
* [ ] The agent streams commands via WebSockets to the local tools.
* [ ] The full execution trace is available in the React UI audit log.

### 6.2 Memory

* [ ] The agent queries Neon DB with `pgvector` to retrieve relevant past context when starting a new task.
* [ ] Episodic memory correctly records task summaries into PostgreSQL vector columns.

### 6.3 Tool Routing & CUA Vision

* [ ] System correctly routes browser tasks to Playwright MCP and native graphical tasks to UI-TARS.
* [ ] The UI-TARS client successfully sends a screenshot to the HF Gradio Space, receives coordinates, and clicks the correct local UI element.

### 6.4 Safety

* [ ] High-risk local actions trigger a visual pause in the UI-TARS React/Tauri shell, showing the user the intended click/action and requiring a manual JWT-authenticated approval.
* [ ] Budget exceeded → execution halts gracefully with a summary of work completed.

---

## 7. The 8-Day Implementation Plan

* **Day 1 | Phase 1: Core App Design & Architecture**
  Initialize React/Next.js frontend and FastAPI backend. Integrate Neon DB (`pgvector`) and establish the LLM connection (`gemma-4-31b-it`) for the core reasoning loop.
* **Day 2 | Phase 2: Browser-Use Agent**
  Integrate Playwright MCP. Map web automation tools to the LLM and verify headless browser task execution.
* **Day 3 | Phase 3: Vision Model Hosting & Skills**
  Deploy UI-TARS-7B/Qwen2.5-VL to a Hugging Face ZeroGPU Gradio Space. Define the strict GUI interaction schemas.
* **Day 4 | Phase 4: Computer-Use Agent**
  Fork the UI-TARS Tauri desktop client. Establish WebSocket communication with FastAPI and wire up the local screenshot-to-VLM execution pipeline.
* **Day 5 | Phase 5: Safety Layer**
  Define risk classifications. Build the React/Tauri visual interceptor to pause high-risk GUI actions for explicit human approval.
* **Day 6 | Phase 6: BUA & CUA Orchestration Testing**
  Conduct frictionless, unauthenticated testing of task delegation. Debug complex workflows that require seamless handoffs between Playwright web tasks and UI-TARS local desktop tasks.
* **Day 7 | Phase 7: Auth & Deployment**
  Implement custom JWT authentication across the frontend, API, and WebSockets. Deploy to Render (Static Site for UI, Web Service for API) and configure keep-alive cron jobs.
* **Day 8 | Phase 8: Final System Validation**
  Conduct complete end-to-end bug bashes using the live deployed application with JWT auth fully enforced. Record the final system demo.
  
---


## 8. Ownership & Workstream Split

| Engineer | Primary Ownership | Secondary / Shared |
| --- | --- | --- |
| **Engineer 1** | FastAPI Orchestrator, Gemma planning logic, Playwright MCP, HF Gradio Space deployment | Vector DB tuning, E2E benchmarks | UI-TARS Desktop fork (React/Electron), Next.js Cloud Dashboard, Safety Intercept UI, Custom JWT | Render deployment, Neon DB schemas |


---

## 9. Final Output Deliverables

The delivered system at the end of Day 14 shall include:

1. **Source code** — Python FastAPI backend, Next.js dashboard, and forked UI-TARS desktop client.
2. **Database Schema** — SQLAlchemy definitions for Neon DB and `pgvector`.
3. **Deployment Configuration** — Render configurations and Keep-Alive cron job setup.
4. **VLM Infrastructure** — Hugging Face Gradio Space configuration for the vision model.
5. **Local Worker Runbook** — Instructions for initializing the customized UI-TARS local client.
6. **System Demo** — Recorded walkthrough of the agent alternating between web browsing and local graphical desktop manipulation, with a successful visual UI safety intervention.
