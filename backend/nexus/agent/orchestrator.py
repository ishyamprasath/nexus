"""Multi-agent orchestrator with sub-task planning and queue management."""
import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from google import genai
from nexus.models import AgentExecution, AgentRole, AgentRequest, AgentResponse, SubTask, TaskStatus
from nexus.agent.react_agent import ReACTAgent
from nexus.agent.task_queue import TaskQueue
from nexus.agent.safety import SafetyPolicy
from nexus.agent.memory import Neo4jMemory
from nexus import config


class MultiAgentOrchestrator:
    """Orchestrates multiple specialized agents to complete complex tasks."""

    def __init__(self):
        self.safety = SafetyPolicy()
        self.memory = Neo4jMemory()
        self.executions: Dict[str, AgentExecution] = {}
        self._client = None
        if config.GEMINI_API_KEY:
            self._client = genai.Client(api_key=config.GEMINI_API_KEY)

    async def run(self, request: AgentRequest) -> AgentResponse:
        """Execute a user task through the multi-agent pipeline."""
        exec_id = f"exec_{uuid.uuid4().hex[:12]}"

        execution = AgentExecution(
            id=exec_id,
            task=request.task,
            image=request.image,
            current_url=request.current_url,
            status=TaskStatus.IN_PROGRESS
        )
        self.executions[exec_id] = execution

        # Step 1: Planning - Use Planner agent to break task into sub-tasks
        queue = TaskQueue()
        planner = ReACTAgent(role=AgentRole.PLANNER, safety_policy=self.safety)

        plan_task = SubTask(
            id=f"{exec_id}_plan",
            description=f"Plan: Break down '{request.task}' into sub-tasks",
            agent_role=AgentRole.PLANNER
        )
        plan_task.status = TaskStatus.IN_PROGRESS

        sub_tasks = self._plan_sub_tasks(request.task, request.image)
        plan_task.status = TaskStatus.COMPLETED
        plan_task.result = f"Created {len(sub_tasks)} sub-tasks"
        queue._tasks[plan_task.id] = plan_task

        # Add sub-tasks to queue
        for desc, role in sub_tasks:
            queue.add_task(description=desc, agent_role=role, parent_id=exec_id)

        execution.sub_tasks = queue.get_tasks()
        self.memory.store_execution(execution)

        # Step 2: Execution - Process tasks from queue
        context = {
            "user_id": request.user_id,
            "execution_id": exec_id,
            "current_url": request.current_url,
            "image": request.image,
            "history": []
        }

        while not queue.is_complete():
            task = queue.get_next_executable()
            if not task:
                # Check if any tasks are still in progress
                if queue.get_current_task():
                    await asyncio.sleep(0.5)
                    continue
                break

            queue.start_task(task.id)
            execution.sub_tasks = queue.get_tasks()
            self.memory.store_execution(execution)

            # Create appropriate agent for the task role
            agent = self._create_agent(task.agent_role)

            # Execute the task in a thread pool to avoid blocking
            result = await asyncio.to_thread(agent.execute, task, context)
            context["history"].append(f"{task.agent_role}: {result}")

            if task.status == TaskStatus.COMPLETED:
                queue.complete_task(task.id, result)
            else:
                queue.fail_task(task.id, task.error or "Execution failed")

            execution.sub_tasks = queue.get_tasks()
            self.memory.store_execution(execution)

        # Step 3: Synthesis
        execution.status = TaskStatus.COMPLETED if queue.is_complete() else TaskStatus.FAILED
        execution.completed_at = datetime.utcnow()
        execution.final_result = self._synthesize_results(execution)
        self.memory.store_execution(execution)

        return AgentResponse(
            execution_id=exec_id,
            status=execution.status,
            result=execution.final_result,
            sub_tasks=execution.sub_tasks,
            thinking_trace=execution.thinking_trace
        )

    def _plan_sub_tasks(self, task: str, image: Optional[str] = None) -> List[tuple]:
        """Use LLM to break down a task into sub-tasks."""
        if not self._client:
            # Default plan for browser tasks
            return [
                (f"Research: Find URLs and information for '{task}'", AgentRole.RESEARCHER),
                (f"Execute: Perform main action for '{task}'", AgentRole.EXECUTOR),
                (f"Verify: Check results of '{task}'", AgentRole.CRITIC)
            ]

        prompt = f"""Break down the following task into 3-5 sub-tasks. Each sub-task should have a clear description and an agent role (planner, researcher, executor, or critic).

Task: {task}

Return as a JSON array:
[
  {{"description": "...", "role": "researcher"}},
  {{"description": "...", "role": "executor"}}
]
"""
        try:
            response = self._client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt
            )
            text = response.text

            # Extract JSON
            import json, re
            json_match = re.search(r'\[[\s\S]*\]', text)
            if json_match:
                plans = json.loads(json_match.group(0))
                return [(p["description"], AgentRole(p["role"])) for p in plans]
        except Exception as e:
            print(f"[Planner] Error: {e}")

        # Fallback plan
        return [
            (f"Research: Find information for '{task}'", AgentRole.RESEARCHER),
            (f"Execute: {task}", AgentRole.EXECUTOR),
            (f"Verify: Check results", AgentRole.CRITIC)
        ]

    def _create_agent(self, role: AgentRole) -> ReACTAgent:
        """Create a specialized agent for a role."""
        return ReACTAgent(role=role, safety_policy=self.safety, max_steps=10)

    def _synthesize_results(self, execution: AgentExecution) -> str:
        """Synthesize all sub-task results into a final answer."""
        results = []
        for task in execution.sub_tasks:
            if task.result:
                results.append(f"[{task.agent_role}] {task.description}: {task.result}")

        if not results:
            return "No results were generated."

        if self._client:
            prompt = f"""Synthesize these agent results into a coherent final response for the user:

Task: {execution.task}

Results:
{chr(10).join(results)}

Provide a clear, concise final answer."""
            try:
                response = self._client.models.generate_content(
                    model=config.GEMINI_MODEL,
                    contents=prompt
                )
                return response.text
            except:
                pass

        return "\n\n".join(results)

    def get_execution(self, exec_id: str) -> Optional[AgentExecution]:
        """Get an execution by ID."""
        return self.executions.get(exec_id)

    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get dashboard statistics."""
        total = len(self.executions)
        active = sum(1 for e in self.executions.values() if e.status == TaskStatus.IN_PROGRESS)
        completed = sum(1 for e in self.executions.values() if e.status == TaskStatus.COMPLETED)
        failed = total - active - completed

        total_tools = sum(
            len(t.tool_calls)
            for e in self.executions.values()
            for t in e.sub_tasks
        )

        safety_stats = self.safety.get_stats()

        return {
            "total_executions": total,
            "active_executions": active,
            "completed_executions": completed,
            "failed_executions": failed,
            "total_tool_calls": total_tools,
            "total_safety_events": safety_stats["total_events"],
            "blocked_actions": safety_stats["blocked"],
            "allowed_actions": safety_stats["allowed"],
            "safety_stats": safety_stats
        }
