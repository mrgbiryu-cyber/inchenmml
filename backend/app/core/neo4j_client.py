from neo4j import AsyncGraphDatabase
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.core.config import settings
from app.models.schemas import Project, AgentDefinition

class Neo4jClient:
    def __init__(self):
        self.driver = None
        self._connected = False
        if settings.NEO4J_URI and settings.NEO4J_USER and settings.NEO4J_PASSWORD:
            try:
                self.driver = AsyncGraphDatabase.driver(
                    settings.NEO4J_URI, 
                    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                    connection_timeout=2.0,
                    max_connection_lifetime=600
                )
            except Exception as e:
                print(f"DEBUG: Neo4j driver initialization failed: {e}")

    async def verify_connectivity(self) -> bool:
        if not self.driver:
            return False
        if self._connected:
            return True
        try:
            async with self.driver.session() as session:
                result = await session.run("RETURN 1 AS result")
                record = await result.single()
                self._connected = (record["result"] == 1)
                return self._connected
        except Exception:
            self._connected = False
            return False

    async def create_project_graph(self, project: Project):
        if not self.driver:
            return

        clear_query = """
        MATCH (p:Project {id: $project_id})
        OPTIONAL MATCH (p)-[:HAS_AGENT]->(a:AgentRole)
        DETACH DELETE a
        """

        query = """
        MERGE (p:Project {id: $project_id})
        SET p.name = $name, 
            p.description = $description,
            p.project_type = $project_type,
            p.repo_path = $repo_path,
            p.tenant_id = $tenant_id, 
            p.user_id = $user_id,
            p.created_at = $created_at,
            p.updated_at = $updated_at,
            p.workflow_type = $workflow_type,
            p.entry_agent_id = $entry_agent_id
        
        WITH p
        UNWIND $agents AS agent
        MERGE (a:AgentRole {id: agent.agent_id})
        SET a.role = agent.role, 
            a.model = agent.model, 
            a.provider = agent.provider,
            a.system_prompt = agent.system_prompt
        MERGE (p)-[:HAS_AGENT]->(a)
        
        WITH p
        UNWIND $agents AS agent
        MATCH (src:AgentRole {id: agent.agent_id})
        UNWIND agent.next_agents AS next_id
        MATCH (dst:AgentRole {id: next_id})
        MERGE (src)-[:NEXT_STEP]->(dst)
        """
        
        agents_data = []
        if project.agent_config:
            agents_data = [agent.dict() for agent in project.agent_config.agents]
        
        async with self.driver.session() as session:
            await session.run(clear_query, {"project_id": project.id})
            await session.run(query, {
                "project_id": project.id,
                "name": project.name,
                "description": project.description,
                "project_type": project.project_type,
                "repo_path": project.repo_path,
                "tenant_id": project.tenant_id,
                "user_id": project.user_id,
                "created_at": project.created_at.isoformat() if isinstance(project.created_at, datetime) else project.created_at,
                "updated_at": project.updated_at.isoformat() if isinstance(project.updated_at, datetime) else project.updated_at,
                "workflow_type": project.agent_config.workflow_type if project.agent_config else "SEQUENTIAL",
                "entry_agent_id": project.agent_config.entry_agent_id if project.agent_config else None,
                "agents": agents_data
            })

    async def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        if not self.driver:
            return None
        
        query = """
        MATCH (p:Project {id: $project_id})
        OPTIONAL MATCH (p)-[:HAS_AGENT]->(a:AgentRole)
        OPTIONAL MATCH (a)-[:NEXT_STEP]->(next:AgentRole)
        RETURN p, collect(DISTINCT a) as agents, collect(DISTINCT {from: a.id, to: next.id}) as steps
        """
        
        async with self.driver.session() as session:
            result = await session.run(query, {"project_id": project_id})
            record = await result.single()
            if not record:
                return None
            
            project_data = self._convert_neo4j_types(dict(record["p"]))
            agents_nodes = record["agents"]
            steps = record["steps"]
            
            if agents_nodes:
                agents_list = []
                for agent_node in agents_nodes:
                    if not agent_node: continue
                    a_data = dict(agent_node)
                    a_id = a_data["id"]
                    a_data["agent_id"] = a_id
                    del a_data["id"]
                    a_data["next_agents"] = [s["to"] for s in steps if s["from"] == a_id and s["to"]]
                    agents_list.append(a_data)
                
                project_data["agent_config"] = {
                    "workflow_type": project_data.get("workflow_type", "SEQUENTIAL"),
                    "entry_agent_id": project_data.get("entry_agent_id") or (agents_list[0]["agent_id"] if agents_list else None),
                    "agents": agents_list
                }
            else:
                project_data["agent_config"] = None

            return project_data

    async def delete_project(self, project_id: str):
        if not self.driver:
            return
        query = """
        MATCH (p:Project {id: $project_id})
        OPTIONAL MATCH (p)-[:HAS_AGENT]->(a:AgentRole)
        DETACH DELETE p, a
        """
        async with self.driver.session() as session:
            await session.run(query, {"project_id": project_id})

    async def list_projects(self, tenant_id: str) -> List[Dict[str, Any]]:
        if not self.driver:
            return []
        query = """
        MATCH (p:Project {tenant_id: $tenant_id})
        RETURN p
        ORDER BY p.updated_at DESC
        """
        async with self.driver.session() as session:
            result = await session.run(query, {"tenant_id": tenant_id})
            projects = []
            async for record in result:
                project_data = self._convert_neo4j_types(dict(record["p"]))
                projects.append(project_data)
            return projects

    def _convert_neo4j_types(self, data: Dict[str, Any]) -> Dict[str, Any]:
        import neo4j.time
        converted = {}
        for key, value in data.items():
            if isinstance(value, neo4j.time.DateTime):
                converted[key] = datetime(
                    value.year, value.month, value.day,
                    value.hour, value.minute, int(value.second),
                    int(value.nanosecond / 1000)
                )
            else:
                converted[key] = value
        return converted

    _chat_cache: Dict[str, List[Dict[str, Any]]] = {}

    async def save_chat_message(self, project_id: str, role: str, content: str, thread_id: Optional[str] = None, user_id: Optional[str] = None):
        if self.driver:
            try:
                query = """
                MERGE (p:Project {id: $project_id})
                ON CREATE SET p.name = CASE WHEN $project_id = 'system-master' THEN 'System Master' ELSE 'Unknown Project' END,
                              p.tenant_id = 'tenant_hyungnim',
                              p.user_id = $user_id,
                              p.project_type = 'SYSTEM',
                              p.repo_path = 'D:/project/myllm',
                              p.created_at = datetime(),
                              p.updated_at = datetime()
                ON MATCH SET p.repo_path = CASE WHEN $project_id = 'system-master' AND (p.repo_path IS NULL OR p.repo_path = '') THEN 'D:/project/myllm' ELSE p.repo_path END,
                             p.user_id = COALESCE($user_id, p.user_id)
                
                CREATE (m:ChatMessage {
                    id: randomUUID(),
                    role: $role,
                    content: $content,
                    thread_id: $thread_id,
                    user_id: $user_id,
                    created_at: datetime()
                })
                CREATE (p)-[:HAS_MESSAGE]->(m)
                SET p.updated_at = datetime()
                """
                async with self.driver.session() as session:
                    await session.run(query, {
                        "project_id": project_id,
                        "role": role,
                        "content": content,
                        "thread_id": thread_id,
                        "user_id": user_id or "system"
                    })
                if project_id in self._chat_cache:
                    del self._chat_cache[project_id]
                return
            except Exception as e:
                print(f"Neo4j save failed: {e}")

    async def get_chat_history(self, project_id: str, limit: int = 50, thread_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if not thread_id and project_id in self._chat_cache:
            return self._chat_cache[project_id][-limit:]

        messages = []
        if self.driver:
            try:
                # Use CASE or simple IF for the WHERE clause
                if thread_id:
                    query = """
                    MATCH (p:Project {id: $project_id})-[:HAS_MESSAGE]->(m:ChatMessage)
                    WHERE m.thread_id = $thread_id
                    RETURN m
                    ORDER BY m.created_at ASC
                    LIMIT $limit
                    """
                else:
                    query = """
                    MATCH (p:Project {id: $project_id})-[:HAS_MESSAGE]->(m:ChatMessage)
                    RETURN m
                    ORDER BY m.created_at ASC
                    LIMIT $limit
                    """
                
                async with self.driver.session() as session:
                    result = await session.run(query, {
                        "project_id": project_id, 
                        "limit": limit,
                        "thread_id": thread_id
                    })
                    async for record in result:
                        msg_node = record["m"]
                        msg_data = dict(msg_node)
                        if "created_at" in msg_data:
                            msg_data["created_at"] = str(msg_data["created_at"])
                        messages.append(msg_data)
                
                if messages and not thread_id:
                    self._chat_cache[project_id] = messages
                return messages
            except Exception as e:
                print(f"Neo4j fetch failed: {e}")
        return []

neo4j_client = Neo4jClient()
