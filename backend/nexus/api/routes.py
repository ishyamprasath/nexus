"""FastAPI routes for Nexus agent framework."""
import asyncio
import base64
import io
import json
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PIL import Image

from nexus.models import (
    AgentRequest, AgentResponse, DashboardStats,
    SafetyEvent, VisionRequest, VisionResponse
)
from nexus.agent.orchestrator import MultiAgentOrchestrator
from nexus.agent.memory import Neo4jMemory
from nexus.agent.safety import SafetyPolicy
from nexus import config

router = APIRouter(prefix="/api")

# Global instances
orchestrator = MultiAgentOrchestrator()
memory = Neo4jMemory()
safety = SafetyPolicy()

# Active WebSocket connections for real-time updates
websocket_connections: List[WebSocket] = []


@router.post("/agent")
async def run_agent(request: AgentRequest):
    """Run the multi-agent orchestrator on a task. Returns immediately with execution_id."""
    if not config.GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")

    import asyncio
    from fastapi import BackgroundTasks
    exec_id = f"exec_{uuid.uuid4().hex[:12]}"

    # Start orchestrator in background
    async def _run_bg():
        try:
            result = await orchestrator.run(request)
            # Broadcast completion via WebSocket
            await broadcast_update({
                "type": "execution_complete",
                "execution_id": result.execution_id,
                "status": result.status.value,
                "result": result.result
            })
        except Exception as e:
            await broadcast_update({
                "type": "execution_error",
                "execution_id": exec_id,
                "error": str(e)
            })

    asyncio.create_task(_run_bg())

    return {
        "execution_id": exec_id,
        "status": "started",
        "ws_url": f"/api/ws/agent/{exec_id}",
        "message": "Agent started. Connect to WebSocket for real-time updates."
    }


@router.post("/agent/stream")
async def run_agent_stream(request: AgentRequest):
    """Run agent with streaming updates (for WebSocket fallback)."""
    # Return initial response; client should connect to WebSocket for updates
    exec_id = f"exec_{uuid.uuid4().hex[:12]}"
    return {"execution_id": exec_id, "status": "started", "ws_url": f"/ws/agent/{exec_id}"}


@router.post("/chat")
async def quick_chat(request: dict):
    """Quick chat endpoint - direct Gemini response without full orchestration."""
    if not config.GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")

    message = request.get("message", "")
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    try:
        from google import genai
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=message
        )
        return {"text": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@router.post("/vision", response_model=VisionResponse)
async def vision_analysis(request: VisionRequest):
    """Analyze an image with Gemini vision."""
    if not config.GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")

    try:
        from google import genai
        client = genai.Client(api_key=config.GEMINI_API_KEY)

        # Decode base64 image
        image_data = base64.b64decode(request.image.split(",")[1] if "," in request.image else request.image)
        image = Image.open(io.BytesIO(image_data))

        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=[request.prompt, image]
        )
        return VisionResponse(text=response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vision analysis failed: {str(e)}")


@router.get("/execution/{execution_id}")
async def get_execution(execution_id: str):
    """Get execution details including sub-tasks and thinking traces."""
    execution = orchestrator.get_execution(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return execution


@router.get("/execution/{execution_id}/graph")
async def get_execution_graph(execution_id: str):
    """Get Neo4j graph data for visualization."""
    graph = memory.get_execution_graph(execution_id)
    return graph


@router.get("/executions/active")
async def get_active_executions():
    """Get currently active executions."""
    active = memory.get_active_executions()
    return active


@router.get("/dashboard")
async def get_dashboard():
    """Get safety dashboard statistics."""
    stats = orchestrator.get_dashboard_stats()

    # Add recent safety events
    recent_events = safety.get_events(limit=50)
    stats["recent_events"] = [
        {
            "id": e.id,
            "tool": e.tool,
            "allowed": e.allowed,
            "reason": e.reason,
            "timestamp": e.timestamp.isoformat()
        }
        for e in recent_events
    ]

    # Add active executions with queue stats
    active_execs = []
    for exec_id, execution in orchestrator.executions.items():
        if execution.status.value in ["pending", "in_progress"]:
            queue_stats = {
                "total": len(execution.sub_tasks),
                "completed": sum(1 for t in execution.sub_tasks if t.status.value == "completed"),
                "pending": sum(1 for t in execution.sub_tasks if t.status.value == "pending"),
                "in_progress": sum(1 for t in execution.sub_tasks if t.status.value == "in_progress"),
                "failed": sum(1 for t in execution.sub_tasks if t.status.value == "failed")
            }
            active_execs.append({
                "id": exec_id,
                "task": execution.task,
                "status": execution.status.value,
                "queue_stats": queue_stats,
                "current_task": next((t.description for t in execution.sub_tasks if t.status.value == "in_progress"), None),
                "next_task": next((t.description for t in execution.sub_tasks if t.status.value == "pending"), None)
            })

    stats["active_executions_detail"] = active_execs
    return stats


@router.get("/browser/status")
async def browser_status():
    """Check Chrome CDP connection status."""
    from nexus.agent.browser import get_browser
    browser = get_browser()
    connected = browser.is_connected()
    targets = browser.get_targets() if connected else []
    return {
        "connected": connected,
        "debug_port": config.CHROME_DEBUG_PORT,
        "targets": len(targets),
        "target_list": [
            {"id": t.get("id"), "title": t.get("title", ""), "url": t.get("url", ""), "type": t.get("type")}
            for t in targets[:10]
        ] if connected else []
    }


@router.get("/safety/events")
async def get_safety_events(limit: int = 100):
    """Get safety audit log."""
    events = safety.get_events(limit=limit)
    return {
        "events": [
            {
                "id": e.id,
                "tool": e.tool,
                "action": e.action,
                "allowed": e.allowed,
                "reason": e.reason,
                "timestamp": e.timestamp.isoformat()
            }
            for e in events
        ],
        "stats": safety.get_stats()
    }


# WebSocket for real-time agent updates
async def broadcast_update(data: Dict[str, Any]):
    """Broadcast update to all connected WebSocket clients."""
    disconnected = []
    for ws in websocket_connections:
        try:
            await ws.send_json(data)
        except:
            disconnected.append(ws)
    for ws in disconnected:
        if ws in websocket_connections:
            websocket_connections.remove(ws)


@router.websocket("/ws/agent/{execution_id}")
async def websocket_agent(websocket: WebSocket, execution_id: str):
    """WebSocket for real-time agent execution updates."""
    await websocket.accept()
    websocket_connections.append(websocket)

    try:
        # Send initial state
        execution = orchestrator.get_execution(execution_id)
        if execution:
            await websocket.send_json({
                "type": "execution_state",
                "execution_id": execution_id,
                "status": execution.status.value,
                "task": execution.task,
                "sub_tasks": [
                    {
                        "id": t.id,
                        "description": t.description,
                        "status": t.status.value,
                        "agent_role": t.agent_role.value,
                        "thinking_trace": [
                            {"step": ts.step, "thought": ts.thought}
                            for ts in t.thinking_trace
                        ]
                    }
                    for t in execution.sub_tasks
                ]
            })

        # Keep connection alive and listen for pings
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        if websocket in websocket_connections:
            websocket_connections.remove(websocket)
    except Exception:
        if websocket in websocket_connections:
            websocket_connections.remove(websocket)


def setup_cors(app: FastAPI):
    """Configure CORS for the app."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
