from neo4j import AsyncGraphDatabase
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio
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
            a.system_prompt = agent.system_prompt,
            a.config_json = agent.config_json
        MERGE (p)-[:HAS_AGENT]->(a)
        
        WITH p
        UNWIND $agents AS agent
        MATCH (src:AgentRole {id: agent.agent_id})
        UNWIND agent.next_agents AS next_id
        MATCH (dst:AgentRole {id: next_id})
        MERGE (src)-[:NEXT_STEP]->(dst)
        """
        
        import json
        agents_data = []
        if project.agent_config:
            for agent in project.agent_config.agents:
                a_dict = agent.dict()
                # config를 JSON 문자열로 변환하여 전달
                a_dict["config_json"] = json.dumps(a_dict.get("config", {}), ensure_ascii=False)
                agents_data.append(a_dict)
        
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

    async def delete_project_agents(self, project_id: str):
        """프로젝트에 연결된 모든 에이전트 노드와 관계를 물리적으로 삭제합니다."""
        if self.driver:
            query = """
            MATCH (p:Project {id: $project_id})
            OPTIONAL MATCH (p)-[:HAS_AGENT]->(a:AgentRole)
            DETACH DELETE a
            SET p.agent_config = null,
                p.workflow_type = 'SEQUENTIAL',
                p.entry_agent_id = null
            """
            async with self.driver.session() as session:
                await session.run(query, {"project_id": project_id})

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
            
            import json
            if agents_nodes:
                agents_list = []
                for agent_node in agents_nodes:
                    if not agent_node: continue
                    a_data = dict(agent_node)
                    a_id = a_data["id"]
                    a_data["agent_id"] = a_id
                    del a_data["id"]
                    
                    # config_json 복구
                    if "config_json" in a_data:
                        try:
                            a_data["config"] = json.loads(a_data["config_json"])
                        except:
                            a_data["config"] = {}
                        del a_data["config_json"]
                    else:
                        a_data["config"] = {}
                        
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

    async def list_projects(self, tenant_id: str, user_id: str = None, project_ids: List[str] = None) -> List[Dict[str, Any]]:
        if not self.driver:
            return []
        
        # [v5.0] RBAC: 
        # 1. user_id provided: Filter by creator (Legacy/Creator mode)
        # 2. project_ids provided: Filter by specific IDs (Assigned mode)
        # 3. Neither: Return all in tenant (Admin mode)
        
        params = {"tenant_id": tenant_id}
        
        if project_ids is not None:
            # Filter by explicit list of IDs (UserProjectModel mapping)
            query = """
            MATCH (p:Project {tenant_id: $tenant_id})
            WHERE p.id IN $project_ids
            RETURN p
            ORDER BY p.updated_at DESC
            """
            params["project_ids"] = project_ids
        elif user_id:
            # Filter by creator only
            query = """
            MATCH (p:Project {tenant_id: $tenant_id})
            WHERE p.user_id = $user_id
            RETURN p
            ORDER BY p.updated_at DESC
            """
            params["user_id"] = user_id
        else:
            # All projects (Admin)
            query = """
            MATCH (p:Project {tenant_id: $tenant_id})
            RETURN p
            ORDER BY p.updated_at DESC
            """
            
        async with self.driver.session() as session:
            result = await session.run(query, params)
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

    async def save_chat_message(self, project_id: str, role: str, content: str, thread_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        [DEPRECATED] ChatMessage 노드는 더 이상 사용하지 않음
        RDB (PostgreSQL)가 Single Source of Truth
        대화 맥락은 ConversationChunk 노드로 관리
        """
        # 비활성화: 중복 저장 방지
        pass

    async def get_chat_history(self, project_id: str, limit: int = 50, thread_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        [DEPRECATED] ChatMessage 노드는 더 이상 사용하지 않음
        RDB (PostgreSQL)의 get_messages_from_rdb() 사용
        """
        # 비활성화: RDB 사용
        return []
        
        # messages = []
        # if self.driver:
        #     try:
        #         if thread_id:
        #             query = """
        #             MATCH (p:Project {id: $project_id})-[:HAS_MESSAGE]->(m:ChatMessage)
        #             WHERE m.thread_id = $thread_id
        #             RETURN m
        #             ORDER BY m.timestamp ASC
        #             LIMIT $limit
        #             """
        #         else:
        #             query = """
        #             MATCH (p:Project {id: $project_id})-[:HAS_MESSAGE]->(m:ChatMessage)
        #             RETURN m
        #             ORDER BY m.timestamp ASC
        #             LIMIT $limit
        #             """
        #         
        #         async with self.driver.session() as session:
        #             result = await session.run(query, {
        #                 "project_id": project_id, 
        #                 "limit": limit,
        #                 "thread_id": thread_id
        #             })
        #             async for record in result:
        #                 msg_node = record["m"]
        #                 msg_data = dict(msg_node)
        #                 if "timestamp" in msg_data:
        #                     msg_data["timestamp"] = str(msg_data["timestamp"])
        #                 messages.append(msg_data)
        #         return messages
        #     except Exception as e:
        #         print(f"Neo4j fetch failed: {e}")
        # return []

    async def query_knowledge(self, project_id: str, query_text: str, limit: int = 5) -> List[Dict[str, Any]]:
        if not self.driver: return []
        query = """
        MATCH (p:Project {id: $project_id})-[r]->(n)
        WHERE (type(r) STARTS WITH 'HAS_' OR type(r) = 'RELATES_TO')
          AND (
            (n.title IS NOT NULL AND n.title CONTAINS $query_text) OR 
            (n.name IS NOT NULL AND n.name CONTAINS $query_text) OR 
            (n.description IS NOT NULL AND n.description CONTAINS $query_text) OR
            (n.content IS NOT NULL AND n.content CONTAINS $query_text) OR
            (n.claim IS NOT NULL AND n.claim CONTAINS $query_text)
          )
        RETURN n, labels(n) as types
        LIMIT $limit
        """
        async def _execute():
            items = []
            try:
                async with self.driver.session() as session:
                    result = await session.run(query, {"project_id": project_id, "query_text": query_text, "limit": limit})
                    async for record in result:
                        node = record["n"]
                        data = dict(node)
                        data["types"] = record["types"]
                        items.append(data)
                return items
            except Exception as e:
                print(f"❌ Neo4j inner query error: {e}")
                return []
        try:
            return await asyncio.wait_for(_execute(), timeout=5.0)
        except asyncio.TimeoutError:
            print(f"⚠️ Neo4j query timed out for query: {query_text}")
            return []
        except Exception as e:
            print(f"❌ Neo4j query wrapper error: {e}")
            return []

    async def get_knowledge_graph(self, project_id: str) -> Dict[str, Any]:
        if not self.driver: return {"nodes": [], "links": []}
        
        # [CRITICAL FIX] Print debug with exact project_id
        print(f"DEBUG: [Neo4j] get_knowledge_graph called for project: '{project_id}' (type: {type(project_id)})")
        
        # [v5.0 CRITICAL FIX] Optimized query - Separate nodes and relationships
        # Step 1: Get all knowledge nodes for this project
        # Step 2: Get all relationships between those nodes
        query = """
        // Collect all knowledge nodes for this project
        MATCH (n)
        WHERE (n.project_id = $project_id OR (:Project {id: $project_id})-[:HAS_KNOWLEDGE]->(n))
          AND labels(n)[0] IN ['Concept', 'Requirement', 'Decision', 'Logic', 'Fact', 'Task', 'File', 'History']
        WITH collect(DISTINCT n) as knowledge_nodes, collect(DISTINCT n.id) as node_ids
        
        // Now find all relationships between these nodes
        UNWIND knowledge_nodes as n
        OPTIONAL MATCH (n)-[r]->(m)
        WHERE m.id IN node_ids
          AND labels(m)[0] IN ['Concept', 'Requirement', 'Decision', 'Logic', 'Fact', 'Task', 'File', 'History']
        
        RETURN n, labels(n) as labels, 
               collect(DISTINCT {type: type(r), target: m.id, source: n.id}) as rels
        """
        
        nodes, links, node_ids = [], [], set()
        
        async with self.driver.session() as session:
            # [CRITICAL FIX] Log before query execution
            print(f"DEBUG: [Neo4j] Executing Cypher query with project_id: '{project_id}'")
            
            result = await session.run(query, {"project_id": project_id})
            
            record_count = 0
            link_count = 0
            async for record in result:
                record_count += 1
                n = record["n"]
                raw_id = n.get("id") or n.element_id
                n_id = str(raw_id[0]) if isinstance(raw_id, list) else str(raw_id)
                labels = record["labels"]
                
                if n_id not in node_ids:
                    color, val = "#3b82f6", 10
                    main_label = labels[0] if labels else "Concept"
                    if main_label == "Requirement": color, val = "#ef4444", 15
                    elif main_label == "Decision": color, val = "#10b981", 18
                    elif main_label == "Logic": color, val = "#f59e0b", 12
                    elif main_label == "Concept": color, val = "#8b5cf6", 12
                    elif main_label == "Fact": color, val = "#06b6d4", 8
                    elif main_label == "Task": color, val = "#f97316", 10
                    
                    # [v4.2 FIX] Use content/claim as fallback for name if title is missing
                    display_name = n.get("title") or n.get("name") or n.get("summary")
                    if not display_name:
                        content_val = n.get("content") or n.get("claim") or n.get("text")
                        if content_val:
                            display_name = (content_val[:30] + "...") if len(content_val) > 30 else content_val
                    
                    # [CRITICAL FIX] Log node's project_id for verification
                    node_project_id = n.get("project_id", "NONE")
                    if record_count <= 3:  # Only log first 3 nodes
                        print(f"DEBUG: [Neo4j] Node {n_id} has project_id: '{node_project_id}' (expected: '{project_id}')")
                    
                    # [v5.0 FIX] Flatten critical properties for Frontend Interface (GraphNode)
                    node_props = dict(n)
                    nodes.append({
                        "id": n_id, 
                        "name": display_name or n_id, 
                        "title": n.get("title"),
                        "content": n.get("content"),
                        "source_message_id": n.get("source_message_id"),
                        "type": main_label, 
                        "val": val, 
                        "color": color, 
                        "properties": node_props
                    })
                    node_ids.add(n_id)
                
                # [CRITICAL FIX] Process relationships correctly
                rels = record["rels"]
                for rel in rels:
                    if not rel or not rel.get("target") or not rel.get("source"):
                        continue
                    
                    source_id = rel.get("source")
                    target_id = rel.get("target")
                    rel_type = rel.get("type")
                    
                    if not rel_type:
                        continue
                    
                    # Normalize IDs
                    s_id = str(source_id[0]) if isinstance(source_id, list) else str(source_id)
                    t_id = str(target_id[0]) if isinstance(target_id, list) else str(target_id)
                    
                    if s_id and t_id and s_id != t_id:
                        link_obj = {
                            "source": s_id, 
                            "target": t_id, 
                            "type": rel_type  # [v5.0 FIX] Use 'type' not 'label' for frontend compatibility
                        }
                        # Avoid duplicate links
                        if link_obj not in links:
                            links.append(link_obj)
                            if len(links) <= 3:  # Log first 3 links
                                print(f"DEBUG: [Neo4j] Link added: {s_id[:12]}... -{rel_type}-> {t_id[:12]}...")
        
        # [CRITICAL FIX] Print final result summary
        print(f"DEBUG: [Neo4j] Query processed {record_count} records")
        print(f"DEBUG: [Neo4j] Returning {len(nodes)} nodes and {len(links)} links for project '{project_id}'")
        
        # [v5.0 FIX] Check raw DB in a new session to avoid "Session closed" error
        if len(links) == 0 and len(nodes) > 0:
            print(f"WARNING: [Neo4j] {len(nodes)} nodes exist but 0 relationships found!")
            print(f"WARNING: [Neo4j] Checking raw DB for relationships with project_id '{project_id}'...")
            try:
                # Open a NEW session for the raw DB check
                async with self.driver.session() as check_session:
                    # [v5.0 CRITICAL] Check ALL relationship types, grouped
                    check_query = """
                    MATCH (n)-[r]->(m)
                    WHERE (n.project_id = $project_id OR m.project_id = $project_id OR r.project_id = $project_id)
                    RETURN type(r) as rel_type, count(*) as count
                    ORDER BY count DESC
                    """
                    check_result = await check_session.run(check_query, {"project_id": project_id})
                    rel_types = []
                    total_rels = 0
                    async for check_record in check_result:
                        rel_type = check_record["rel_type"]
                        count = check_record["count"]
                        rel_types.append(f"{rel_type}: {count}")
                        total_rels += count
                    
                    if rel_types:
                        print(f"WARNING: [Neo4j] Found {total_rels} raw relationships in DB but query returned 0!")
                        print(f"         Relationship types: {', '.join(rel_types)}")
                        
                        # [v5.0] Sample actual knowledge node relationships
                        sample_query = """
                        MATCH (n)-[r]->(m)
                        WHERE n.project_id = $project_id AND m.project_id = $project_id
                          AND labels(n)[0] IN ['Concept', 'Requirement', 'Decision', 'Logic', 'Fact', 'Task', 'File', 'History']
                          AND labels(m)[0] IN ['Concept', 'Requirement', 'Decision', 'Logic', 'Fact', 'Task', 'File', 'History']
                        RETURN type(r) as rel_type, n.id as source_id, m.id as target_id
                        LIMIT 5
                        """
                        sample_result = await check_session.run(sample_query, {"project_id": project_id})
                        samples = []
                        async for sample_record in sample_result:
                            samples.append(dict(sample_record))
                        
                        if samples:
                            print(f"         Sample knowledge-to-knowledge relationships:")
                            for i, rel in enumerate(samples):
                                print(f"           {i+1}. {rel['source_id'][:12]}... -{rel['rel_type']}-> {rel['target_id'][:12]}...")
                    else:
                        print(f"WARNING: [Neo4j] No relationships found in raw DB either. They may not have been created.")
            except Exception as check_err:
                print(f"ERROR: [Neo4j] Failed to check raw relationships: {check_err}")
        
        return {"nodes": nodes, "links": links}

    async def create_indexes(self):
        if not self.driver: return
        try:
            async with self.driver.session() as session:
                await session.run("CREATE CONSTRAINT project_id_unique IF NOT EXISTS FOR (p:Project) REQUIRE p.id IS UNIQUE")
        except Exception as e:
            if "already exists an index" in str(e):
                try:
                    async with self.driver.session() as session:
                        await session.run("DROP INDEX FOR (n:Project) ON (n.id)")
                        await session.run("CREATE CONSTRAINT project_id_unique IF NOT EXISTS FOR (p:Project) REQUIRE p.id IS UNIQUE")
                except: pass
        index_queries = [
            "CREATE INDEX IF NOT EXISTS FOR (n:Concept) ON (n.title)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Concept) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Requirement) ON (n.title)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Decision) ON (n.title)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Fact) ON (n.claim)",
            # "CREATE INDEX IF NOT EXISTS FOR (n:ChatMessage) ON (n.message_id)",  # Deprecated
            "CREATE INDEX IF NOT EXISTS FOR (n:ConversationChunk) ON (n.chunk_id)"  # New
        ]
        async with self.driver.session() as session:
            for q in index_queries:
                try: await session.run(q)
                except: pass

neo4j_client = Neo4jClient()
