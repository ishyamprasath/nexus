"""Configuration for Nexus backend."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env")

# Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", os.getenv("MODEL", "gemma-3-27b-it"))

# Neo4j
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "nexus123")

# Browser
CHROME_DEBUG_PORT = int(os.getenv("CHROME_DEBUG_PORT", "9222"))
CHROME_PATH = os.getenv("CHROME_PATH", "C:/Program Files/Google/Chrome/Application/chrome.exe")

# Safety
SAFETY_DENY_BY_DEFAULT = os.getenv("SAFETY_DENY_BY_DEFAULT", "true").lower() == "true"
SAFETY_ASK_USER_TOOLS = os.getenv("SAFETY_ASK_USER_TOOLS", "run_command,execute_shell").split(",")

# Server
CORS_ORIGINS = ["*"]
WS_MESSAGE_QUEUE_SIZE = 1000
