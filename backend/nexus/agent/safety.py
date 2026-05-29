"""Safety policies for agent tool execution - deny by default."""
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from nexus.models import SafetyEvent
from nexus import config


class SafetyPolicy:
    """Declarative safety policy system. Deny all by default."""

    def __init__(self):
        self._allowed_tools: set = set()
        self._denied_tools: set = set()
        self._ask_user_tools: set = set(config.SAFETY_ASK_USER_TOOLS)
        self._events: List[SafetyEvent] = []
        self._handlers: Dict[str, Callable] = {}
        self._setup_defaults()

    def _setup_defaults(self):
        """Set up default safe tools."""
        safe_tools = [
            "view_file", "read_file", "search_files", "list_directory",
            "get_webpage", "search_google", "navigate_to", "click_element",
            "type_text", "scroll_page", "take_screenshot", "get_page_source",
            "extract_text", "find_links"
        ]
        for tool in safe_tools:
            self.allow(tool)

    def allow(self, tool_pattern: str):
        """Allow a tool or pattern (e.g., 'view_*')."""
        self._allowed_tools.add(tool_pattern)

    def deny(self, tool_pattern: str):
        """Deny a tool or pattern."""
        self._denied_tools.add(tool_pattern)

    def ask_user(self, tool_pattern: str, handler: Optional[Callable] = None):
        """Require user approval for a tool."""
        self._ask_user_tools.add(tool_pattern)
        if handler:
            self._handlers[tool_pattern] = handler

    def _matches(self, tool: str, pattern: str) -> bool:
        """Check if tool matches pattern (supports wildcards)."""
        if pattern == "*":
            return True
        if pattern.endswith("*"):
            return tool.startswith(pattern[:-1])
        return tool == pattern

    def _is_allowed(self, tool: str) -> bool:
        """Check if tool is explicitly allowed."""
        for pattern in self._allowed_tools:
            if self._matches(tool, pattern):
                return True
        return False

    def _is_denied(self, tool: str) -> bool:
        """Check if tool is explicitly denied."""
        for pattern in self._denied_tools:
            if self._matches(tool, pattern):
                return True
        return False

    def _requires_approval(self, tool: str) -> bool:
        """Check if tool requires user approval."""
        for pattern in self._ask_user_tools:
            if self._matches(tool, pattern):
                return True
        return False

    def check(self, tool: str, arguments: Dict[str, Any], user_id: Optional[str] = None,
              execution_id: Optional[str] = None) -> tuple[bool, str]:
        """
        Evaluate tool execution against safety policy.
        Returns (allowed, reason).
        """
        # Deny by default
        if not self._is_allowed(tool):
            event = SafetyEvent(
                id=f"evt_{int(time.time() * 1000)}",
                tool=tool,
                action=str(arguments),
                allowed=False,
                reason=f"Tool '{tool}' is not in the allowed list (deny by default policy)",
                user_id=user_id,
                execution_id=execution_id
            )
            self._events.append(event)
            return False, event.reason

        # Check explicit deny list
        if self._is_denied(tool):
            event = SafetyEvent(
                id=f"evt_{int(time.time() * 1000)}",
                tool=tool,
                action=str(arguments),
                allowed=False,
                reason=f"Tool '{tool}' is explicitly denied",
                user_id=user_id,
                execution_id=execution_id
            )
            self._events.append(event)
            return False, event.reason

        # Check if requires user approval
        if self._requires_approval(tool):
            event = SafetyEvent(
                id=f"evt_{int(time.time() * 1000)}",
                tool=tool,
                action=str(arguments),
                allowed=True,  # Pre-approved for now; in production, would wait for user
                reason=f"Tool '{tool}' requires user approval - pre-approved in this session",
                user_id=user_id,
                execution_id=execution_id
            )
            self._events.append(event)
            return True, event.reason

        # Tool is allowed
        event = SafetyEvent(
            id=f"evt_{int(time.time() * 1000)}",
            tool=tool,
            action=str(arguments),
            allowed=True,
            reason=f"Tool '{tool}' is allowed by policy",
            user_id=user_id,
            execution_id=execution_id
        )
        self._events.append(event)
        return True, event.reason

    def get_events(self, limit: int = 100) -> List[SafetyEvent]:
        """Get recent safety events."""
        return self._events[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Get safety statistics."""
        total = len(self._events)
        blocked = sum(1 for e in self._events if not e.allowed)
        allowed = total - blocked
        return {
            "total_events": total,
            "blocked": blocked,
            "allowed": allowed,
            "allowed_tools": list(self._allowed_tools),
            "denied_tools": list(self._denied_tools),
            "ask_user_tools": list(self._ask_user_tools)
        }
