from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime

class RetrievalChunk(BaseModel):
    rank: int
    score: float
    title: str
    text: str
    source_message_id: Optional[str] = None
    node_id: Optional[str] = None  # [v5.0 Critical] Neo4j kg-* ID for tab navigation
    type: Optional[str] = None  # [v5.0] Node type (Concept, Requirement, etc.)
    metadata: Optional[dict] = None

class RetrievalDebug(BaseModel):
    chunks: List[RetrievalChunk] = []
    graph_nodes: List[dict] = []  # Graph 검색 결과용

class DebugInfo(BaseModel):
    retrieval: RetrievalDebug = Field(default_factory=RetrievalDebug)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ChatDebugResponse(BaseModel):
    request_id: str
    debug_info: DebugInfo
