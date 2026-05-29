"""ReACT (Reasoning + Acting) agent using Gemini."""
import json
import re
import time
from typing import Any, Dict, List, Optional

from google import genai
from nexus.models import AgentRole, SubTask, TaskStatus, ThoughtStep, ToolCall
from nexus.agent.safety import SafetyPolicy
from nexus import config


class ReACTAgent:
    """ReACT agent: thinks, acts, observes in a loop until task complete."""

    def __init__(self, role: AgentRole = AgentRole.EXECUTOR,
                 safety_policy: Optional[SafetyPolicy] = None,
                 max_steps: int = 5):
        self.role = role
        self.safety = safety_policy or SafetyPolicy()
        self.max_steps = max_steps
        self.tools: Dict[str, Any] = {}
        self._setup_tools()
        self._client = None
        if config.GEMINI_API_KEY:
            self._client = genai.Client(api_key=config.GEMINI_API_KEY)

    def _setup_tools(self):
        """Register built-in tools."""
        self.tools = {
            "search_google": self._search_google,
            "search_youtube": self._search_youtube,
            "play_youtube": self._play_youtube,
            "navigate_to": self._navigate_to,
            "click_element": self._click_element,
            "type_text": self._type_text,
            "scroll_page": self._scroll_page,
            "take_screenshot": self._take_screenshot,
            "extract_text": self._extract_text,
            "get_page_source": self._get_page_source,
            "find_links": self._find_links,
            "ask_user": self._ask_user,
            "wait": self._wait,
            "complete": self._complete,
        }

    def execute(self, task: SubTask, context: Dict[str, Any] = None) -> str:
        """Execute a sub-task using ReACT loop."""
        if not self._client:
            return "Error: Gemini API not configured"

        task.status = TaskStatus.IN_PROGRESS
        context = context or {}

        # Build ReACT prompt
        system_prompt = self._build_system_prompt()
        history = context.get("history", [])

        no_action_count = 0
        for step in range(1, self.max_steps + 1):
            # Think
            prompt = self._build_think_prompt(task, step, history)
            try:
                response = self._client.models.generate_content(
                    model=config.GEMINI_MODEL,
                    contents=f"{system_prompt}\n\n{prompt}"
                )
                thought = response.text.strip()
            except Exception as e:
                thought = f"Error generating response: {e}"

            task.thinking_trace.append(ThoughtStep(
                step=step,
                thought=thought
            ))

            # Parse action from thought
            action = self._parse_action(thought)
            if not action:
                no_action_count += 1
                history.append(f"Step {step}: {thought}\nObservation: No valid action found. Please use the exact format: Action: {{\"tool\": \"...\", \"args\": {{...}}}}")
                if no_action_count >= 2:
                    # Force complete with accumulated thoughts
                    task.status = TaskStatus.COMPLETED
                    task.result = thought
                    return thought
                continue

            no_action_count = 0

            task.thinking_trace[-1].action = json.dumps(action)

            # Check safety
            allowed, reason = self.safety.check(
                action["tool"], action.get("args", {}),
                user_id=context.get("user_id"),
                execution_id=context.get("execution_id")
            )
            if not allowed:
                task.thinking_trace[-1].observation = f"SAFETY BLOCKED: {reason}"
                history.append(f"Step {step}: {thought}\nObservation: SAFETY BLOCKED - {reason}")
                continue

            # Execute action
            tool_call = ToolCall(
                tool=action["tool"],
                arguments=action.get("args", {})
            )
            task.tool_calls.append(tool_call)

            start_time = time.time()
            try:
                result = self._execute_tool(action["tool"], action.get("args", {}), context)
                tool_call.result = str(result)[:500]
                tool_call.success = True
                tool_call.duration_ms = int((time.time() - start_time) * 1000)

                task.thinking_trace[-1].observation = str(result)[:1000]
                history.append(f"Step {step}: {thought}\nObservation: {result}")

                # Check if complete
                if action["tool"] == "complete":
                    task.status = TaskStatus.COMPLETED
                    task.result = result
                    return result

            except Exception as e:
                tool_call.success = False
                error_msg = f"Error: {str(e)}"
                task.thinking_trace[-1].observation = error_msg
                history.append(f"Step {step}: {thought}\nObservation: {error_msg}")

        # Max steps reached
        task.status = TaskStatus.FAILED
        task.error = "Maximum steps reached without completion"
        return task.error

    def _build_system_prompt(self) -> str:
        """Build the ReACT system prompt."""
        tools_desc = "\n".join([
            f"- {name}()" for name in self.tools.keys()
        ])

        return f"""You are a {self.role.value} agent in the Nexus multi-agent system.
Your job is to complete tasks by reasoning step-by-step, then taking actions.

Available tools:
{tools_desc}

You MUST use the following ReACT format:
Thought: <your reasoning about what to do next>
Action: {{"tool": "tool_name", "args": {{"key": "value"}}}}

Or to finish:
Thought: <reasoning that task is complete>
Action: {{"tool": "complete", "args": {{"result": "your final answer"}}}}

Always think before acting. Be concise but thorough."""

    def _build_think_prompt(self, task: SubTask, step: int, history: List[str]) -> str:
        """Build the prompt for the current thinking step."""
        history_text = "\n\n".join(history[-5:]) if history else "No previous steps."
        return f"""Task: {task.description}
Role: {task.agent_role}
Step: {step}/{self.max_steps}

Previous steps:
{history_text}

What is your next thought and action?"""

    def _parse_action(self, thought: str) -> Optional[Dict[str, Any]]:
        """Parse Action JSON from thought text."""
        # Try to find Action: {...} pattern
        match = re.search(r'Action:\s*(\{.*?\})', thought, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find JSON anywhere in the text
        try:
            json_match = re.search(r'\{[^{}]*"tool"[^}]*\}', thought, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
        except:
            pass

        return None

    def _execute_tool(self, tool_name: str, args: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Execute a tool by name."""
        if tool_name not in self.tools:
            return f"Unknown tool: {tool_name}"
        return self.tools[tool_name](args, context)

    # === Tool Implementations ===

    def _run_async(self, coro):
        """Run an async coroutine from sync context."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return loop.run_in_executor(pool, lambda: asyncio.run(coro))
        except RuntimeError:
            return asyncio.run(coro)

    def _search_google(self, args: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Search Google and return top results."""
        query = args.get("query", "")
        from nexus.agent.browser import get_browser
        browser = get_browser()
        if not browser.is_connected():
            return f"Chrome not connected. Start Chrome with --remote-debugging-port=9222. Query was: {query}"
        result = asyncio.run(browser.search_google(query))
        return str(result)

    def _navigate_to(self, args: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Navigate to a URL."""
        url = args.get("url", "")
        from nexus.agent.browser import get_browser
        browser = get_browser()
        if not browser.is_connected():
            return f"Chrome not connected. Start Chrome with --remote-debugging-port=9222. URL was: {url}"
        result = asyncio.run(browser.navigate(url))
        return str(result)

    def _click_element(self, args: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Click an element on the page."""
        selector = args.get("selector", "")
        from nexus.agent.browser import get_browser
        browser = get_browser()
        if not browser.is_connected():
            return "Chrome not connected"
        result = asyncio.run(browser.click_element(selector))
        return str(result)

    def _type_text(self, args: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Type text into an input field."""
        selector = args.get("selector", "")
        text = args.get("text", "")
        submit = args.get("submit", False)
        from nexus.agent.browser import get_browser
        browser = get_browser()
        if not browser.is_connected():
            return "Chrome not connected"
        result = asyncio.run(browser.type_text(selector, text, submit))
        return str(result)

    def _scroll_page(self, args: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Scroll the page."""
        direction = args.get("direction", "down")
        amount = args.get("amount", 500)
        from nexus.agent.browser import get_browser
        browser = get_browser()
        if not browser.is_connected():
            return "Chrome not connected"
        result = asyncio.run(browser.scroll_page(direction, amount))
        return str(result)

    def _take_screenshot(self, args: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Take a screenshot."""
        from nexus.agent.browser import get_browser
        browser = get_browser()
        if not browser.is_connected():
            return "Chrome not connected"
        result = asyncio.run(browser.take_screenshot())
        return str(result)[:200]  # Truncate base64 for display

    def _extract_text(self, args: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Extract text from the current page."""
        from nexus.agent.browser import get_browser
        browser = get_browser()
        if not browser.is_connected():
            return "Chrome not connected"
        result = asyncio.run(browser.extract_text())
        return str(result)

    def _get_page_source(self, args: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Get raw HTML of the page."""
        from nexus.agent.browser import get_browser
        browser = get_browser()
        if not browser.is_connected():
            return "Chrome not connected"
        result = asyncio.run(browser.get_page_source())
        return str(result)

    def _find_links(self, args: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Find all links on the page."""
        from nexus.agent.browser import get_browser
        browser = get_browser()
        if not browser.is_connected():
            return "Chrome not connected"
        result = asyncio.run(browser.extract_links())
        return str(result)

    def _search_youtube(self, args: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Search YouTube and return top video results."""
        query = args.get("query", "")
        from nexus.agent.browser import get_browser
        browser = get_browser()
        if not browser.is_connected():
            return f"Chrome not connected. Start Chrome with --remote-debugging-port=9222. Query was: {query}"
        result = asyncio.run(browser.search_youtube(query))
        return str(result)

    def _play_youtube(self, args: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Search YouTube and play the first matching video."""
        query = args.get("query", "")
        from nexus.agent.browser import get_browser
        browser = get_browser()
        if not browser.is_connected():
            return f"Chrome not connected. Start Chrome with --remote-debugging-port=9222. Query was: {query}"
        result = asyncio.run(browser.play_youtube_video(query))
        return str(result)

    def _ask_user(self, args: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Ask the user a question."""
        question = args.get("question", "")
        return f"Asked user: {question} (awaiting response)"

    def _wait(self, args: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Wait for a specified duration."""
        seconds = args.get("seconds", 1)
        time.sleep(min(seconds, 10))
        return f"Waited {seconds} seconds"

    def _complete(self, args: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Mark task as complete."""
        return args.get("result", "Task completed successfully")
