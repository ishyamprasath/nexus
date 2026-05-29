"""Neo4j graph memory for agent orchestration visualization."""
import json
from typing import Any, Dict, List, Optional
from neo4j import GraphDatabase
from nexus.models import AgentExecution, SubTask, ThoughtStep
from nexus import config


class Neo4jMemory:
    """Graph-based memory for agent execution tracking and visualization."""

    def __init__(self):
        self._driver = None
        self._connected = False
        try:
            self._driver = GraphDatabase.driver(
                config.NEO4J_URI,
                auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
            )
            self._driver.verify_connectivity()
            self._connected = True
            self._init_schema()
        except Exception as e:
            print(f"[Neo4j] Connection failed: {e}. Running in memory-only mode.")
            self._driver = None

    def _init_schema(self):
        """Initialize graph schema with constraints."""
        if not self._connected:
            return
        with self._driver.session() as session:
            # Create constraints
            session.run("""
                CREATE CONSTRAINT execution_id IF NOT EXISTS
                FOR (e:Execution) REQUIRE e.id IS UNIQUE
            """)
            session.run("""
                CREATE CONSTRAINT task_id IF NOT EXISTS
                FOR (t:Task) REQUIRE t.id IS UNIQUE
            """)
            session.run("""
                CREATE CONSTRAINT agent_id IF NOT EXISTS
                FOR (a:Agent) REQUIRE a.id IS UNIQUE
            """)
        print("[Neo4j] Schema initialized.")

    def store_execution(self, execution: AgentExecution):
        """Store an execution in the graph."""
        if not self._connected:
            return

        with self._driver.session() as session:
            # Create Execution node
            session.run("""
                MERGE (e:Execution {id: $id})
                SET e.task = $task,
                    e.status = $status,
                    e.created_at = $created_at,
                    e.final_result = $final_result
            """, {
                "id": execution.id,
                "task": execution.task,
                "status": execution.status,
                "created_at": execution.created_at.isoformat(),
                "final_result": execution.final_result or ""
            })

            # Create Orchestrator agent
            session.run("""
                MERGE (a:Agent {id: $agent_id, role: 'orchestrator'})
                MERGE (a)-[:ORCHESTRATES]->(e:Execution {id: $exec_id})
            """, {
                "agent_id": f"agent_orchestrator_{execution.id}",
                "exec_id": execution.id
            })

            # Create sub-task nodes and relationships
            for task in execution.sub_tasks:
                self._store_task(session, execution.id, task)

    def _store_task(self, session, execution_id: str, task: SubTask):
        """Store a single sub-task."""
        # Create Task node
        session.run("""
            MERGE (t:Task {id: $id})
            SET t.description = $description,
                t.status = $status,
                t.agent_role = $agent_role,
                t.result = $result,
                t.error = $error,
                t.created_at = $created_at
        """, {
            "id": task.id,
            "description": task.description,
            "status": task.status,
            "agent_role": task.agent_role,
            "result": task.result or "",
            "error": task.error or "",
            "created_at": task.created_at.isoformat()
        })

        # Link to execution
        session.run("""
            MATCH (e:Execution {id: $exec_id})
            MATCH (t:Task {id: $task_id})
            MERGE (e)-[:HAS_TASK]->(t)
        """, {"exec_id": execution_id, "task_id": task.id})

        # Create agent node for this task
        agent_id = f"agent_{task.agent_role}_{task.id}"
        session.run("""
            MERGE (a:Agent {id: $agent_id, role: $role})
            MERGE (a)-[:EXECUTES]->(t:Task {id: $task_id})
        """, {
            "agent_id": agent_id,
            "role": task.agent_role,
            "task_id": task.id
        })

        # Link dependencies
        for dep_id in task.dependencies:
            session.run("""
                MATCH (t:Task {id: $task_id})
                MATCH (dep:Task {id: $dep_id})
                MERGE (t)-[:DEPENDS_ON]->(dep)
            """, {"task_id": task.id, "dep_id": dep_id})

        # Store thinking traces
        for step in task.thinking_trace:
            session.run("""
                MATCH (t:Task {id: $task_id})
                CREATE (ts:ThinkingStep {
                    step: $step,
                    thought: $thought,
                    action: $action,
                    observation: $observation,
                    timestamp: $timestamp
                })
                CREATE (t)-[:HAS_THOUGHT]->(ts)
            """, {
                "task_id": task.id,
                "step": step.step,
                "thought": step.thought,
                "action": step.action or "",
                "observation": step.observation or "",
                "timestamp": step.timestamp.isoformat()
            })

    def get_execution_graph(self, execution_id: str) -> Dict[str, Any]:
        """Get full execution graph as nodes and edges for visualization."""
        if not self._connected:
            return {"nodes": [], "edges": []}

        with self._driver.session() as session:
            result = session.run("""
                MATCH (e:Execution {id: $id})-[:HAS_TASK]->(t:Task)
                OPTIONAL MATCH (t)-[:DEPENDS_ON]->(dep:Task)
                OPTIONAL MATCH (a:Agent)-[:EXECUTES]->(t)
                OPTIONAL MATCH (t)-[:HAS_THOUGHT]->(ts:ThinkingStep)
                RETURN e, t, dep, a, ts
            """, {"id": execution_id})

            nodes = []
            edges = []
            seen = set()

            for record in result:
                exec_node = record["e"]
                task_node = record["t"]
                dep_node = record["dep"]
                agent_node = record["a"]
                thought_node = record["ts"]

                # Execution node
                if exec_node and exec_node["id"] not in seen:
                    seen.add(exec_node["id"])
                    nodes.append({
                        "id": exec_node["id"],
                        "type": "execution",
                        "label": exec_node["task"][:50],
                        "status": exec_node["status"]
                    })

                # Task node
                if task_node and task_node["id"] not in seen:
                    seen.add(task_node["id"])
                    nodes.append({
                        "id": task_node["id"],
                        "type": "task",
                        "label": task_node["description"][:50],
                        "status": task_node["status"],
                        "agent_role": task_node["agent_role"]
                    })
                    edges.append({
                        "from": exec_node["id"],
                        "to": task_node["id"],
                        "type": "has_task"
                    })

                # Dependency edge
                if dep_node and task_node:
                    edges.append({
                        "from": task_node["id"],
                        "to": dep_node["id"],
                        "type": "depends_on"
                    })

                # Agent node
                if agent_node and agent_node["id"] not in seen:
                    seen.add(agent_node["id"])
                    nodes.append({
                        "id": agent_node["id"],
                        "type": "agent",
                        "label": agent_node["role"],
                        "role": agent_node["role"]
                    })
                    edges.append({
                        "from": agent_node["id"],
                        "to": task_node["id"],
                        "type": "executes"
                    })

                # Thinking step node
                if thought_node and thought_node["step"] is not None:
                    thought_id = f"{task_node['id']}_thought_{thought_node['step']}"
                    if thought_id not in seen:
                        seen.add(thought_id)
                        nodes.append({
                            "id": thought_id,
                            "type": "thought",
                            "label": f"Step {thought_node['step']}",
                            "thought": thought_node["thought"]
                        })
                        edges.append({
                            "from": task_node["id"],
                            "to": thought_id,
                            "type": "has_thought"
                        })

            return {"nodes": nodes, "edges": edges}

    def get_active_executions(self) -> List[Dict[str, Any]]:
        """Get currently active executions."""
        if not self._connected:
            return []

        with self._driver.session() as session:
            result = session.run("""
                MATCH (e:Execution)
                WHERE e.status IN ['pending', 'in_progress']
                RETURN e.id as id, e.task as task, e.status as status,
                       e.created_at as created_at
                ORDER BY e.created_at DESC
                LIMIT 10
            """)
            return [dict(r) for r in result]

    def close(self):
        if self._driver:
            self._driver.close()
