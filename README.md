# Nexus - Autonomous AI Agent System

> **Status: Core system built and tested.** Backend orchestrator, Chrome extension sidebar, multi-agent ReACT pipeline, safety dashboard, and Neo4j graph memory all implemented.

## Quick Start

### 1. Start Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
python main.py  # Starts on http://localhost:8001
```

### 2. Start Neo4j (optional - falls back to in-memory mode)
```bash
docker-compose up -d
# UI: http://localhost:7474 | Bolt: bolt://localhost:7687
# Auth: neo4j / nexus123
```

### 3. Load Chrome Extension
1. Open `chrome://extensions`
2. Enable **Developer Mode**
3. Click **Load unpacked** → select `chrome-extension/` folder
4. Press `Ctrl+Shift+N` to toggle sidebar

### 4. Start Chrome with Remote Debugging (for browser automation)
```bash
chrome.exe --remote-debugging-port=9222
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat` | POST | Quick Gemini chat (no orchestration) |
| `/api/agent` | POST | Start multi-agent task (returns immediately) |
| `/api/vision` | POST | Image analysis with Gemini vision |
| `/api/dashboard` | GET | Safety dashboard stats + active executions |
| `/api/execution/{id}` | GET | Get execution details + sub-tasks |
| `/api/execution/{id}/graph` | GET | Neo4j graph visualization data |
| `/api/safety/events` | GET | Safety audit log |
| `/api/ws/agent/{id}` | WS | Real-time execution updates |

## Architecture

```
Chrome Extension (Sidebar UI)
    │
    ├── Chat Input ──► /api/chat (direct Gemini)
    ├── Task Input ──► /api/agent (multi-agent orchestrator)
    ├── Image Upload ─► /api/vision (Gemini vision)
    ├── Dashboard  ──► /api/dashboard (stats + safety)
    └── WebSocket  ──► /api/ws/agent/{id} (real-time updates)

Backend (FastAPI)
    │
    ├── MultiAgentOrchestrator
    │   ├── Planner Agent (breaks task into sub-tasks)
    │   ├── Researcher Agent (finds info)
    │   ├── Executor Agent (performs actions)
    │   └── Critic Agent (verifies results)
    │
    ├── TaskQueue (dependency resolution, priority ordering)
    ├── SafetyPolicy (deny-by-default, user approval hooks)
    ├── Neo4jMemory (graph storage for execution traces)
    └── ReACTAgent (think → act → observe loop)

Gemini API (gemma-4-31b-it - free tier)
    ├── Text generation
    ├── Multimodal (image + text)
    └── Task planning + synthesis
```

## Project Structure

```
nexus/
├── backend/
│   ├── main.py                    # FastAPI entry point
│   ├── .env                       # GEMINI_API_KEY, GEMINI_MODEL
│   ├── requirements.txt
│   └── nexus/
│       ├── config.py              # Environment configuration
│       ├── models.py              # Pydantic data models
│       ├── agent/
│       │   ├── react_agent.py     # ReACT reasoning loop
│       │   ├── orchestrator.py    # Multi-agent coordinator
│       │   ├── task_queue.py      # Sub-task queue + dependencies
│       │   ├── safety.py          # Deny-by-default safety
│       │   └── memory.py          # Neo4j graph memory
│       └── api/
│           └── routes.py          # REST + WebSocket endpoints
├── chrome-extension/
│   ├── manifest.json              # Manifest V3
│   ├── background.js              # Service worker
│   ├── content.js                 # Sidebar injection
│   ├── sidebar.html/js/css        # Main UI
│   ├── popup.html/js              # Settings popup
│   └── icons/                     # Extension icons
└── docker-compose.yml             # Neo4j container
```

---

# Comprehensive Requirements Document

## 1. Overview

### 1.1 Project Title

Autonomous AI Agent System (Codename: **Nexus**)

### 1.2 Goal

Build a production-grade, web-native autonomous AI agent system capable of accepting high-level goals from users, decomposing them into executable subtasks, reasoning about execution order, leveraging external tools, recovering from failures, and improving over time.

This orchestration platform leverages a cloud-hosted reasoning brain interacting seamlessly with a highly capable Browser-Use Agent (BUA) and deep research engines. It features planning, centralized relational and vector memory, multi-agent coordination, strict safety controls with human-in-the-loop UI interceptors, and observability built from the ground up to automate complex web-based workflows, data extraction, and research.

### 1.3 Target Users

* Individual operators automating browser tasks and deep research.
* Internal engineering teams needing automated web execution and dynamic data aggregation.
* Operations teams monitoring agent behavior and safety via customized UI dashboards.

### 1.4 Timeline

* **Duration:** 6 Days (Hyper-Accelerated Sprint)
* **Sprint Cadence:** 1 day per major architectural module
* **Team Size:** 1 engineer

---

## 2. Functional Requirements

### 2.1 Planning & Reasoning Engine

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-01 | System shall accept a natural language goal and decompose it into an ordered list of subtasks | P0 |
| FR-02 | System shall support hierarchical task decomposition (subtasks can have sub-subtasks) | P0 |
| FR-03 | System shall dynamically re-plan when a subtask fails or produces unexpected web results (e.g., 404 errors, changed DOMs) | P0 |
| FR-04 | System shall support multiple reasoning strategies: ReAct (reason-act-observe loop), Plan-then-Execute, and Reflexion (self-critique) | P1 |
| FR-05 | System shall enforce constraints on plans (max steps, time budget, token budget) | P1 |

### 2.2 Memory System

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-06 | System shall maintain working memory (current task context) within JSONB columns alongside the execution state | P0 |
| FR-07 | System shall implement long-term and episodic memory via `pgvector` embeddings for semantic retrieval of past executions | P0 |
| FR-08 | System shall retrieve relevant memories via cosine similarity search before planning to inform strategy selection | P0 |
| FR-09 | System shall perform memory consolidation (summarization, pruning stale entries) natively within PostgreSQL | P1 |

### 2.3 Tool Use & Environment Interaction

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-10 | System shall support a dynamic tool registry mapped to the Model Context Protocol (MCP) | P0 |
| FR-11 | System shall execute complex web-based browsing actions via Playwright MCP | P0 |
| FR-12 | System shall integrate Deepsearch capabilities for exhaustive, multi-step web research, document parsing, and data synthesis | P0 |
| FR-13 | System shall validate tool outputs (e.g., ensuring a scraped JSON is well-formed) before incorporating them into the task state | P1 |
| FR-14 | System shall retry failed tool calls (e.g., broken web links, timeouts) with exponential backoff (max 3 retries) | P1 |

### 2.4 Multi-Agent Orchestration

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-15 | System shall implement a message-passing protocol between the orchestrator and specialized sub-agents (e.g., Search Agent, UI Navigation Agent) | P1 |
| FR-16 | System shall support parallel execution of independent subtasks (e.g., querying three different APIs simultaneously) | P2 |
| FR-17 | System shall implement dependency-aware scheduling (task B waits for task A's web extraction) | P1 |

### 2.5 Safety & Control

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-18 | System shall classify every action as low-risk (auto-execute), medium-risk, or high-risk | P0 |
| FR-19 | System shall intercept high-risk actions (e.g., submitting web forms, purchasing, cloud infrastructure changes) and pause execution in the React UI for explicit human approval | P0 |
| FR-20 | System shall enforce custom JWT authentication to secure the frontend UI and API connections | P0 |
| FR-21 | System shall maintain a complete audit trail of all reasoning steps, decisions, and actions in Neon DB | P0 |
| FR-22 | System shall support an emergency stop mechanism that halts all active agent instances and headless browsers immediately | P0 |

---

## 3. Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-01 | Latency for plan generation | < 10 seconds for goals with ≤ 10 subtasks |
| NFR-02 | End-to-end task completion | < 2 minutes for standard web extraction |
| NFR-03 | System availability | 99.5% uptime on Render |
| NFR-04 | Worker persistence | Keep-alive cron mechanism to prevent Render spin-down during active deep searches |
| NFR-05 | Memory retrieval latency | < 500ms for top-k vector search in Neon DB |

---

## 4. Architecture Overview

```text
┌─────────────────────────────────────────────────────┐
│                 Render (Cloud)                      │
│                                                     │
│  ┌─────────────────┐       ┌────────────────────┐   │
│  │   React/Next.js │       │ FastAPI Web Service│   │
│  │   Static Site   │◄─JWT─►│   (Orchestrator)   │   │
│  └──────┬──────────┘       └──────┬─────┬───────┘   │
└─────────┼─────────────────────────┼─────┼───────────┘
          │                         │     │
          │                         │     └──HTTP──┐
          ▼                         ▼              ▼
┌───────────────────┐     ┌────────────────┐ ┌────────────────┐
│ Dashboard & Queue │     │ Playwright MCP │ │ External APIs  │
│                   │     │     (BUA)      │ │                │
│ ┌───────────────┐ │     └───────┬────────┘ │ ┌────────────┐ │
│ │ Auth & Safety │ │             │          │ │ Gemma 4 31B│ │
│ │ Interceptors  │ │             ▼          │ └────────────┘ │
│ └───────────────┘ │     ┌────────────────┐ │ ┌────────────┐ │
└───────────────────┘     │ Target Websites│ │ │ Neon DB    │ │
                          │ & Deepsearch   │ │ │ (pgvector) │ │
                          └────────────────┘ │ └────────────┘ │
                                             └────────────────┘

```

---

## 5. Tech Stack

| Layer | Technology |
| --- | --- |
| **Frontend Dashboard** | React / Next.js |
| **Backend Orchestrator** | Python / FastAPI |
| **Cloud Brain** | `gemma-4-31b-it` via API |
| **Database / Memory** | Neon DB (PostgreSQL + `pgvector`) |
| **Browser Automation (BUA)** | Playwright MCP |
| **Deep Research Tools** | Custom Deepsearch integrations / Web scrapers / LangChain |
| **Authentication** | Custom JWT |
| **Deployment** | Render (Web Service for API, Static Site for UI) |

---

## 6. Acceptance Criteria

### 6.1 Core Agent Loop

* [ ] Given a natural language goal, the FastAPI backend produces a valid multi-step plan within 10 seconds via Gemma.
* [ ] The system accurately delegates web navigation and deep search subtasks to the respective tools.
* [ ] The full execution trace is available in the React UI audit log.

### 6.2 Memory & Orchestration

* [ ] The agent queries Neon DB with `pgvector` to retrieve relevant past context when starting a new task.
* [ ] System correctly routes basic navigation and extraction to Playwright MCP and complex multi-source research to the Deepsearch module.
* [ ] System handles captchas or broken selectors gracefully by re-planning.

### 6.3 Safety & Authentication

* [ ] High-risk web actions trigger a visual pause in the React dashboard, showing the user the intended action and requiring manual JWT-authenticated approval.
* [ ] Budget exceeded → execution halts gracefully with a summary of work completed.

---

## 7. The Detailed 6-Day Implementation Plan

A highly aggressive sprint utilizing a full-stack Python and Node.js architecture.

### Day 1 | Chatbot + Multi-Agent Orchestration & Sub-tasks

* **Backend Skeleton:** Initialize the FastAPI orchestrator. Connect to Neon DB and configure SQLAlchemy models for standard state and `jsonb` working memory. Enable the `pgvector` extension.
* **Frontend Skeleton:** Bootstrap the React/Next.js dashboard. Set up the basic layout (navigation, main chat area, empty state for logs).
* **AI Core:** Connect the `gemma-4-31b-it` API. Build the core ReAct (Reason-Act-Observe) while-loop. Write the system prompt that forces Gemma to decompose complex user goals into an ordered list of JSON sub-tasks.
* **Outcome:** You can type a prompt in the UI, it hits the API, Gemma breaks it down, and returns a structured plan.

### Day 2 | Browser-Use Agent (BUA) + Deepsearch

* **Playwright MCP:** Install and configure the Playwright MCP server. Map foundational web tools (`Maps`, `click`, `extract_text`, `fill_form`) into the Gemma tool registry within FastAPI.
* **Deepsearch Integration:** Build the deep research module. This involves setting up multi-query generation (so the agent searches 3-4 variations of a query at once), scraping the resulting pages, and passing the raw text through a summarization chain before returning it to the main agent loop.
* **Outcome:** The backend can now autonomously open headless browsers, read documentation, search the web, and aggregate data.

### Day 3 | Safety Dashboard + Queue System

* **UI Engineering:** Build the React Kanban-style queue management system. Subtasks generated on Day 1 will now flow visually from `Backlog` -> `In Progress` -> `Done`.
* **The Safety Interceptor:** Crafting an intuitive, high-tech interface for the human-in-the-loop system requires a strong product design approach. Build the visual intercept modal. When the backend flags an action as "High Risk" (e.g., clicking a submit button), it pauses the loop and triggers this modal, displaying the exact DOM element or URL the agent intends to interact with.
* **Outcome:** The frontend accurately visualizes the complex, multi-agent concurrency happening in the backend, with full manual override capabilities.

### Day 4 | Testing Orchestration

* **Frictionless Debugging:** Run rigorous, unauthenticated testing of task delegation.
* **Complex Workflows:** Feed the system a highly complex prompt: *"Research the latest Next.js 15 routing changes, cross-reference them with the React 19 documentation, and write a comprehensive markdown guide."*
* **Refinement:** Debug the handoffs. Ensure the orchestrator correctly uses Deepsearch for the broad research, Playwright for specific page extraction, and memory to synthesize the final markdown without dropping the context window.

### Day 5 | Auth + Deployment

* **Security:** Implement custom JWT authentication. Write the middleware in FastAPI to protect all routes. Build the login screen and JWT storage logic (HTTP-only cookies or local storage) in Next.js.
* **Infrastructure:** Push the codebase to the cloud. Deploy the Next.js frontend as a Render Static Site (backed by a CDN) and the FastAPI orchestrator as a Render Web Service.
* **Persistence:** Configure a keep-alive cron job (using a service like cron-job.org) to ping a `/health` endpoint on your FastAPI server every 14 minutes, preventing the Render free tier from spinning down during long deep-search tasks.

### Day 6 | Final Testing & Polish

* **Bug Bash:** Conduct complete end-to-end testing using the live, deployed Render URLs with JWT authentication fully enforced.
* **Memory Validation:** Test the `pgvector` episodic memory. Ask the agent to perform a task it failed at earlier in the week to ensure it retrieves the memory of the failure and alters its strategy.
* **Final Output:** Record the final system demonstration showcasing the seamless integration of planning, browser automation, safety intercepts, and web research.
