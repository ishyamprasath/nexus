"""Pydantic models for Nexus agent framework."""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class AgentRole(str, Enum):
    PLANNER = "planner"
    RESEARCHER = "researcher"
    EXECUTOR = "executor"
    CRITIC = "critic"
    ORCHESTRATOR = "orchestrator"


class ToolCall(BaseModel):
    tool: str
    arguments: Dict[str, Any]
    result: Optional[str] = None
    success: bool = False
    duration_ms: Optional[int] = None


class ThoughtStep(BaseModel):
    step: int
    thought: str
    action: Optional[str] = None
    observation: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SubTask(BaseModel):
    id: str
    parent_id: Optional[str] = None
    description: str
    status: TaskStatus = TaskStatus.PENDING
    agent_role: AgentRole = AgentRole.EXECUTOR
    dependencies: List[str] = Field(default_factory=list)
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    thinking_trace: List[ThoughtStep] = Field(default_factory=list)
    tool_calls: List[ToolCall] = Field(default_factory=list)


class AgentExecution(BaseModel):
    id: str
    task: str
    image: Optional[str] = None
    current_url: Optional[str] = None
    sub_tasks: List[SubTask] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    thinking_trace: List[ThoughtStep] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    final_result: Optional[str] = None


class SafetyEvent(BaseModel):
    id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tool: str
    action: str
    allowed: bool
    reason: str
    user_id: Optional[str] = None
    execution_id: Optional[str] = None


class DashboardStats(BaseModel):
    total_executions: int
    active_executions: int
    completed_executions: int
    failed_executions: int
    total_tool_calls: int
    total_safety_events: int
    blocked_actions: int
    allowed_actions: int
    avg_execution_time_ms: Optional[int] = None


class AgentRequest(BaseModel):
    task: str
    image: Optional[str] = None
    current_url: Optional[str] = None
    user_id: Optional[str] = None


class AgentResponse(BaseModel):
    execution_id: str
    status: TaskStatus
    result: Optional[str] = None
    sub_tasks: List[SubTask] = Field(default_factory=list)
    thinking_trace: List[ThoughtStep] = Field(default_factory=list)


class VisionRequest(BaseModel):
    image: str
    prompt: str


class VisionResponse(BaseModel):
    text: str
