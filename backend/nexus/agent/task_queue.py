"""Task queue with sub-task splitting and dependency management."""
import uuid
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional
from nexus.models import AgentRole, SubTask, TaskStatus, ThoughtStep


class TaskQueue:
    """Priority queue for sub-tasks with dependency resolution."""

    def __init__(self):
        self._tasks: Dict[str, SubTask] = {}
        self._queue: deque = deque()
        self._completed: List[str] = []
        self._failed: List[str] = []

    def add_task(self, description: str, agent_role: AgentRole = AgentRole.EXECUTOR,
                 dependencies: Optional[List[str]] = None, parent_id: Optional[str] = None) -> str:
        """Add a sub-task to the queue."""
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        task = SubTask(
            id=task_id,
            parent_id=parent_id,
            description=description,
            status=TaskStatus.PENDING,
            agent_role=agent_role,
            dependencies=dependencies or [],
            created_at=datetime.utcnow()
        )
        self._tasks[task_id] = task
        self._queue.append(task_id)
        return task_id

    def split_task(self, parent_id: str, sub_descriptions: List[str],
                   agent_roles: Optional[List[AgentRole]] = None) -> List[str]:
        """Split a parent task into multiple sub-tasks."""
        if parent_id not in self._tasks:
            raise ValueError(f"Parent task {parent_id} not found")

        parent = self._tasks[parent_id]
        parent.status = TaskStatus.IN_PROGRESS

        ids = []
        prev_id = None
        for i, desc in enumerate(sub_descriptions):
            role = agent_roles[i] if agent_roles and i < len(agent_roles) else AgentRole.EXECUTOR
            deps = [prev_id] if prev_id else []
            tid = self.add_task(
                description=desc,
                agent_role=role,
                dependencies=deps,
                parent_id=parent_id
            )
            ids.append(tid)
            prev_id = tid

        return ids

    def get_next_executable(self) -> Optional[SubTask]:
        """Get next task whose dependencies are all completed."""
        executable = []
        for task_id in list(self._queue):
            task = self._tasks.get(task_id)
            if not task or task.status != TaskStatus.PENDING:
                continue

            # Check if all dependencies are completed
            deps_satisfied = all(
                self._tasks.get(dep_id, SubTask(id="", description="")).status == TaskStatus.COMPLETED
                for dep_id in task.dependencies
            )

            if deps_satisfied:
                executable.append(task)

        if not executable:
            return None

        # Sort by role priority: planner first, then researcher, executor, critic
        priority = {
            AgentRole.PLANNER: 0,
            AgentRole.RESEARCHER: 1,
            AgentRole.EXECUTOR: 2,
            AgentRole.CRITIC: 3
        }
        executable.sort(key=lambda t: priority.get(t.agent_role, 99))
        return executable[0]

    def start_task(self, task_id: str):
        """Mark a task as in-progress."""
        if task_id in self._tasks:
            self._tasks[task_id].status = TaskStatus.IN_PROGRESS

    def complete_task(self, task_id: str, result: str):
        """Mark a task as completed with result."""
        if task_id in self._tasks:
            task = self._tasks[task_id]
            task.status = TaskStatus.COMPLETED
            task.result = result
            task.completed_at = datetime.utcnow()
            self._completed.append(task_id)
            if task_id in self._queue:
                self._queue.remove(task_id)

    def fail_task(self, task_id: str, error: str):
        """Mark a task as failed."""
        if task_id in self._tasks:
            task = self._tasks[task_id]
            task.status = TaskStatus.FAILED
            task.error = error
            task.completed_at = datetime.utcnow()
            self._failed.append(task_id)
            if task_id in self._queue:
                self._queue.remove(task_id)

    def block_task(self, task_id: str):
        """Block a task (e.g., waiting for user input)."""
        if task_id in self._tasks:
            self._tasks[task_id].status = TaskStatus.BLOCKED

    def add_thinking(self, task_id: str, step: int, thought: str,
                     action: Optional[str] = None, observation: Optional[str] = None):
        """Add a thinking step to a task."""
        if task_id in self._tasks:
            self._tasks[task_id].thinking_trace.append(
                ThoughtStep(
                    step=step,
                    thought=thought,
                    action=action,
                    observation=observation
                )
            )

    def get_tasks(self) -> List[SubTask]:
        """Get all tasks."""
        return list(self._tasks.values())

    def get_pending(self) -> List[SubTask]:
        """Get pending tasks."""
        return [t for t in self._tasks.values() if t.status == TaskStatus.PENDING]

    def get_current_task(self) -> Optional[SubTask]:
        """Get the currently executing task."""
        in_progress = [t for t in self._tasks.values() if t.status == TaskStatus.IN_PROGRESS]
        return in_progress[0] if in_progress else None

    def get_next_task(self) -> Optional[SubTask]:
        """Get the next task that will execute."""
        pending = self.get_pending()
        if not pending:
            return None
        # Same priority logic as get_next_executable
        priority = {AgentRole.PLANNER: 0, AgentRole.RESEARCHER: 1, AgentRole.EXECUTOR: 2, AgentRole.CRITIC: 3}
        pending.sort(key=lambda t: priority.get(t.agent_role, 99))
        for task in pending:
            deps_satisfied = all(
                self._tasks.get(dep_id, SubTask(id="", description="")).status == TaskStatus.COMPLETED
                for dep_id in task.dependencies
            )
            if deps_satisfied:
                return task
        return None

    def is_complete(self) -> bool:
        """Check if all tasks are done."""
        return all(t.status in [TaskStatus.COMPLETED, TaskStatus.FAILED] for t in self._tasks.values())

    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        total = len(self._tasks)
        pending = sum(1 for t in self._tasks.values() if t.status == TaskStatus.PENDING)
        in_progress = sum(1 for t in self._tasks.values() if t.status == TaskStatus.IN_PROGRESS)
        completed = sum(1 for t in self._tasks.values() if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in self._tasks.values() if t.status == TaskStatus.FAILED)
        blocked = sum(1 for t in self._tasks.values() if t.status == TaskStatus.BLOCKED)

        return {
            "total": total,
            "pending": pending,
            "in_progress": in_progress,
            "completed": completed,
            "failed": failed,
            "blocked": blocked,
            "progress_pct": round((completed / total * 100) if total > 0 else 0, 1)
        }
