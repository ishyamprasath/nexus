import os
import json
import re
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from the parent directory
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

app = FastAPI(title="Nexus Backend Orchestrator")

# Allow the Next.js frontend to talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure Gemini AI using the .env variables you provided
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("MODEL", "gemini-1.5-flash")

if API_KEY:
    genai.configure(api_key=API_KEY)


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"```$", "", text).strip()
    return text


def _safe_response_text(response) -> str:
    try:
        text = getattr(response, "text", "") or ""
        return text.strip()
    except Exception:
        pass

    try:
        candidates = getattr(response, "candidates", None) or []
        parts = []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", []) or []:
                part_text = getattr(part, "text", None)
                if part_text:
                    parts.append(part_text)
        return "".join(parts).strip()
    except Exception:
        return ""


def _parse_json_response(response_text: str):
    cleaned = _strip_code_fences(response_text)
    if not cleaned:
        raise ValueError("Gemini returned an empty response")

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}|\[.*\]", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Message]] = []
    isPlanRequest: Optional[bool] = False
    goal: Optional[str] = ""

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not set in .env")
        
    try:
        model = genai.GenerativeModel(MODEL_NAME)
    except Exception as e:
        print(f"Failed to load user model {MODEL_NAME}, trying fallback. Error: {e}")
        model = genai.GenerativeModel("gemini-1.5-flash")

    if req.isPlanRequest:
        system_instruction = """You are the Nexus Autonomous Agent Orchestrator. 
Your goal is to accept a natural language goal and decompose it into an ordered, hierarchical tree of subtasks.
You must return a raw JSON object only. Do not include markdown code block formatting (```json ... ```), just the raw JSON text itself.

The JSON should have the following structure:
{
  "goal": "The high level goal",
  "estimatedTime": "e.g., 5 minutes",
  "complexity": "Low | Medium | High",
  "subtasks": [
    {
      "id": "task-1",
      "title": "Short descriptive title",
      "description": "Detail of what is done",
      "status": "pending",
      "priority": "high | medium | low",
      "risk": "low | medium | high",
      "agent": "Search Agent | UI Navigation Agent | Writer Agent",
      "dependencies": []
    }
  ]
}"""
        prompt = f"Goal: {req.goal or req.message}"
        try:
            response = model.generate_content(system_instruction + "\n\n" + prompt)
            text = _safe_response_text(response)
            parsed = _parse_json_response(text)
            return parsed
        except Exception as e:
            print(f"JSON Parse Error: {e}")
            # Fallback plan for demonstration if generation fails formatting
            return {
                "goal": req.goal or req.message,
                "estimatedTime": "3 minutes",
                "complexity": "Medium",
                "subtasks": [
                    {
                        "id": "task-1",
                        "title": "Analyze Request Requirements",
                        "description": "Establish structural parameters based on operator request.",
                        "status": "pending",
                        "priority": "high",
                        "risk": "low",
                        "agent": "Analysis Agent",
                        "dependencies": []
                    }
                ]
            }
    else:
        system_instruction = """You are Nexus, a highly capable autonomous AI coding assistant and agent.
You speak in a crisp, confident, and professional tone.
Keep your answers engaging, bolding key points, using bullet lists where helpful, and write valid code blocks when asked.

Return your response in this exact JSON format:
{
  "text": "The full detailed markdown response of your answer, with code blocks if relevant"
}"""
        contents = []
        for h in req.history:
            contents.append({
                "role": "user" if h.role == "user" else "model",
                "parts": [h.content]
            })
        
        contents.append({
            "role": "user",
            "parts": [system_instruction + "\n\nUser Message: " + req.message]
        })

        try:
            response = model.generate_content(contents)
            text = _safe_response_text(response)
            try:
                return _parse_json_response(text)
            except Exception:
                return {"text": text or "No response details returned."}
        except Exception as e:
            print(f"Error generating standard response: {e}")
            return {"text": f"Error: I encountered an issue interacting with the GEMINI_API. {str(e)}"}
