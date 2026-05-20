# Nexus: A Hybrid Autonomous AI Agent System

## Overview

**Nexus** is an autonomous AI agent system designed to interpret high-level goals, decompose them into executable subtasks, and execute them across both cloud-hosted and local environments. It is a highly orchestrated and modular solution ideal for individual operators, engineering teams, and operations personnel.

The Nexus platform is built to provide planning, reasoning, memory, safety, and observability capabilities, enabling human-in-the-loop interactions, task automation, and more.

## Core Features

### Planning and Reasoning
- **Hierarchical Task Decomposition**: Convert natural language goals into structured, executable subtasks.
- **Dynamic Re-planning**: Adapt tasks dynamically in response to unexpected failures.
- **Multiple Reasoning Strategies**: Choose from ReAct, Plan-then-Execute, and Reflexion.

### Robust Memory System
- Powered by **`pgvector`** for semantic information storage and retrieval.
- Stores long-term episodic memory for execution optimization.
- Cosine similarity-based search to fetch contextual memory for better planning decisions.

### Tool Use and Environment Interaction
- Supports a **dynamic tool registry**, Playwright browser automation, and the OpenClaw desktop execution daemon.
- Tools validate outputs to ensure robustness, with retries using exponential backoff.

### Safety Mechanisms
- Human-in-the-loop safety interceptor ensures high-risk tasks require explicit approval.
- Complete audit trail for actions, decisions, and outputs.
- Emergency stop mechanism for halt and rollback.

### Multi-Agent Coordination
- Supports multiple sub-agents for delegated tasks.
- Parallel execution and dependency-aware scheduling capabilities.

### Self-Improvement
- Benchmark suite for performance measurement and recurring failure pattern learning.
- Strategy embedding for improving future executions.

## Technical Architecture

Nexus integrates the following components:

1. **Frontend**: React/Next.js UI for human-in-the-loop interaction.
2. **Backend**: Python (FastAPI) orchestrator for task decomposition, memory retrieval, and inter-agent messaging.
3. **Database**: Neon DB (PostgreSQL with `pgvector`) for task state, working memory, and semantic embedding storage.
4. **Local Execution**: OpenClaw daemon for desktop tasks and Playwright MCP for browser automation.
5. **Safety Layer**: Intercepts high-risk actions and enforces budgetary and operational constraints.

![System Architecture](https://raw.githubusercontent.com/ishyamprasath/nexus-diagrams/main/architecture-overview.png)

## Stack

| **Component**                 | **Technology**          |
|--------------------------------|-------------------------|
| Frontend                       | React / Next.js         |
| Backend                        | Python / FastAPI        |
| LLM                            | `gemma-4-31b-it`        |
| Database/Memory                | Neon DB (PostgreSQL + `pgvector`) |
| Local Automation (CUA)         | OpenClaw               |
| Browser Automation (BUA)       | Playwright MCP          |
| Authentication                 | Custom JWT             |
| Deployment                     | Render (Static/UI)      |
| Observability                  | Langfuse / OpenTelemetry |

## Milestones and Timeline

### Week 1 - Core API and Database
- Implement FastAPI and integrate NeonDB; enable JWT-based authentication.

### Week 2 - Memory System
- Build out short- and long-term memory retrieval using `pgvector`.

### Week 3 - Local Execution with OpenClaw
- Establish WebSocket communication with the OpenClaw daemon.

### Week 4 - Multi-Agent Orchestration
- Enable multi-agent orchestration with dependency scheduling.

### Week 5 - Safety and Observability
- Implement React-based safety UI, human intervention workflows, and observability tooling.

### Week 6 - Final Tests and Benchmarks
- Run acceptance tests, prepare demos, and deliver the system.

## Installation and Setup

### Prerequisites

- **Python 3.9+**, **Node.js 16+**, and **PostgreSQL 14+**.
- Redis for task queues.
- Render account for deployment.

### Local Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/ishyamprasath/nexus.git
   ```
2. Navigate to the project directory:
   ```bash
   cd nexus
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the API server:
   ```bash
   uvicorn app.main:app --reload
   ```
5. Navigate to the frontend directory and install Node.js dependencies:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

## Testing and Development
- Unit Tests: `pytest` suites for backend task orchestration and memory operations.
- Integration Tests: Mock LLM calls and verify end-to-end workflows.
- End-to-End Tests: Validate real-world tasks using OpenClaw and Playwright.

## Contributing
We welcome contributors! Please create an issue or submit a detailed pull request.

---

## License
Nexus is licensed under the **MIT License**. See `LICENSE` for details.