# VECTORDB RETRIEVAL & INGEST - Embedding Pipeline Specification

**Issue**: H5 - 잘못된 청킹 → 임베딩 오염 → KG Edge 전파  
**Evidence**: VectorDB client exists but chunking/embedding pipeline missing  
**Status**: **GAP IDENTIFIED** - Need to implement missing components

---

## Evidence Summary

### VectorDB Client (Exists)
- **File**: `backend/app/core/vector_store.py:8-72`
- **Class**: `PineconeClient`
- **Methods**:
  - `upsert_vectors(tenant_id, namespace, vectors)` - Line 24-50
  - `query_vectors(tenant_id, namespace, vector, top_k, filter)` - Line 52-72

### Configuration
- **File**: `backend/app/core/config.py`
  - Line 38: `PINECONE_API_KEY: Optional[str] = None`
  - Line 39: `PINECONE_ENVIRONMENT: str = "us-west1-gcp"`
  - Line 40: `PINECONE_INDEX_NAME: str = "buja-knowledge"`

### ❌ Chunking Logic - NOT FOUND
- **Search**: "chunk", "split", "RecursiveCharacterTextSplitter"
- **Result**: No document chunking code found

### ❌ Embedding Generation - NOT FOUND
- **Search**: "embed", "OpenAIEmbeddings", "HuggingFaceEmbeddings"
- **Result**: No embedding model initialization

### ❌ Integration with Knowledge Service - NOT FOUND
- **File**: `backend/app/services/knowledge_service.py`
- **Analysis**: Only saves to Neo4j (line 112: `_upsert_to_neo4j()`), no VectorDB call

---

## Gap Analysis

### Missing Component #1: Document Chunking

**Need**: Split long documents into smaller chunks for embedding

**Standard Approach**:
```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    separators=["\n\n", "\n", ". ", " ", ""]
)

chunks = splitter.split_text(document_text)
```

**Current**: No such code exists

### Missing Component #2: Embedding Model

**Need**: Convert text chunks to vectors

**Standard Approach**:
```python
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    api_key=settings.OPENROUTER_API_KEY
)

vectors = embeddings.embed_documents(chunks)
```

**Current**: No such code exists

### Missing Component #3: Upload Pipeline

**Need**: Chunk → Embed → Upsert to Pinecone

**Current Flow**:
```
User uploads document
       ↓
    ??? (missing)
       ↓
   Pinecone
```

**Should Be**:
```
User uploads document
       ↓
   Chunking (500 chars, 50 overlap)
       ↓
   Embedding (text-embedding-3-small)
       ↓
   Metadata tagging (tenant_id, chunk_id, doc_id)
       ↓
   Upsert to Pinecone
       ↓
   (Optional) Create KG nodes for chunks
```

---

## Design Solution

### 1. Document Chunking Service

**New File**: `backend/app/services/chunking_service.py`

```python
from typing import List, Dict
from langchain.text_splitter import RecursiveCharacterTextSplitter
import hashlib

class ChunkingService:
    """
    Handles document chunking with metadata preservation.
    """
    
    def __init__(self):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len
        )
    
    def chunk_document(
        self, 
        text: str, 
        doc_id: str, 
        metadata: Dict = None
    ) -> List[Dict]:
        """
        Split document into chunks with metadata.
        
        Returns:
            List of {chunk_id, text, doc_id, metadata, index}
        """
        chunks = self.splitter.split_text(text)
        
        result = []
        for idx, chunk_text in enumerate(chunks):
            chunk_id = hashlib.sha256(
                f"{doc_id}:{idx}:{chunk_text[:50]}".encode()
            ).hexdigest()[:16]
            
            result.append({
                "chunk_id": chunk_id,
                "text": chunk_text,
                "doc_id": doc_id,
                "chunk_index": idx,
                "metadata": metadata or {}
            })
        
        return result

chunking_service = ChunkingService()
```

### 2. Embedding Service

**New File**: `backend/app/services/embedding_service.py`

```python
from typing import List
from langchain_openai import OpenAIEmbeddings
from app.core.config import settings

class EmbeddingService:
    """
    Handles text embedding generation.
    """
    
    def __init__(self):
        if settings.OPENROUTER_API_KEY:
            self.embeddings = OpenAIEmbeddings(
                model="text-embedding-3-small",
                api_key=settings.OPENROUTER_API_KEY
            )
        else:
            self.embeddings = None
            logger.warning("Embedding service disabled (no API key)")
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for list of texts.
        
        Returns:
            List of vectors (each vector is List[float])
        """
        if not self.embeddings:
            raise ValueError("Embedding service not configured")
        
        # Note: OpenAIEmbeddings.embed_documents is synchronous
        # Wrap in thread executor for async context
        import asyncio
        loop = asyncio.get_event_loop()
        vectors = await loop.run_in_executor(
            None, 
            self.embeddings.embed_documents,
            texts
        )
        
        return vectors

embedding_service = EmbeddingService()
```

### 3. Document Upload API

**New Endpoint**: `POST /api/v1/projects/{project_id}/documents/upload`

**File**: `backend/app/api/v1/documents.py` (NEW)

```python
from fastapi import APIRouter, UploadFile, Depends
from app.services.chunking_service import chunking_service
from app.services.embedding_service import embedding_service
from app.core.vector_store import PineconeClient

router = APIRouter()

@router.post("/{project_id}/documents/upload")
async def upload_document(
    project_id: str,
    file: UploadFile,
    current_user: User = Depends(get_current_user)
):
    """
    Upload document for embedding and retrieval.
    
    Process:
    1. Read file content
    2. Chunk text
    3. Generate embeddings
    4. Upsert to Pinecone
    5. Optionally create KG summary
    """
    # Read file
    content = await file.read()
    text = content.decode("utf-8")
    
    # Generate doc_id
    doc_id = f"{project_id}:{file.filename}:{uuid.uuid4().hex[:8]}"
    
    # Chunk
    chunks = chunking_service.chunk_document(
        text=text,
        doc_id=doc_id,
        metadata={
            "filename": file.filename,
            "upload_user_id": current_user.id
        }
    )
    
    # Embed
    chunk_texts = [c["text"] for c in chunks]
    vectors = await embedding_service.embed_texts(chunk_texts)
    
    # Prepare Pinecone vectors
    pinecone_vectors = [
        {
            "id": chunk["chunk_id"],
            "values": vector,
            "metadata": {
                "tenant_id": current_user.tenant_id,
                "project_id": project_id,
                "doc_id": doc_id,
                "chunk_index": chunk["chunk_index"],
                "text": chunk["text"][:200],  # Preview
                "filename": file.filename
            }
        }
        for chunk, vector in zip(chunks, vectors)
    ]
    
    # Upsert to Pinecone
    client = PineconeClient()
    await client.upsert_vectors(
        tenant_id=current_user.tenant_id,
        namespace=project_id,
        vectors=pinecone_vectors
    )
    
    return {
        "doc_id": doc_id,
        "chunks": len(chunks),
        "status": "uploaded"
    }
```

### 4. Retrieval Integration

**File**: `backend/app/services/master_agent_service.py`

**New Tool**: `retrieve_documents_tool`

```python
@tool
async def retrieve_documents_tool(query: str, project_id: str) -> str:
    """
    Retrieve relevant document chunks from vector store.
    """
    # Embed query
    query_vector = await embedding_service.embed_texts([query])
    
    # Query Pinecone
    client = PineconeClient()
    results = await client.query_vectors(
        tenant_id=current_user.tenant_id,
        namespace=project_id,
        vector=query_vector[0],
        top_k=5
    )
    
    if not results:
        return "문서 검색 결과가 없습니다."
    
    # Format results
    formatted = []
    for match in results:
        text = match["metadata"].get("text", "")
        score = match.get("score", 0.0)
        filename = match["metadata"].get("filename", "Unknown")
        
        formatted.append(f"[{filename}] (relevance: {score:.2f})\n{text}")
    
    return "\n\n---\n\n".join(formatted)
```

---

## Cascade Delete / Version Invalidation

### Problem
If document re-uploaded → old chunks should be removed

### Solution

**File**: `backend/app/api/v1/documents.py`

```python
@router.delete("/{project_id}/documents/{doc_id}")
async def delete_document(project_id: str, doc_id: str):
    """
    Delete document and all its chunks from VectorDB.
    """
    client = PineconeClient()
    
    # Delete by metadata filter
    await client.index.delete(
        namespace=project_id,
        filter={"doc_id": {"$eq": doc_id}}
    )
    
    return {"status": "deleted", "doc_id": doc_id}
```

**Re-upload Strategy**:
1. Delete old doc_id chunks
2. Upload new chunks with new doc_id + version suffix

---

## Implementation Checklist

- [ ] Install dependencies: `langchain`, `langchain-openai`, `pinecone-client`
- [ ] Create `chunking_service.py`
- [ ] Create `embedding_service.py`
- [ ] Add embedding model to config (text-embedding-3-small)
- [ ] Create `documents.py` router
- [ ] Add `/upload` endpoint
- [ ] Add `/delete` endpoint
- [ ] Add `retrieve_documents_tool` to master agent
- [ ] Test upload → chunk → embed → query pipeline
- [ ] Add cascade delete on re-upload

---

## Testing Requirements

1. **Chunking Test**:
   ```python
   text = "A" * 1000
   chunks = chunking_service.chunk_document(text, "test_doc")
   assert len(chunks) == 2  # 500 + 500 with overlap
   ```

2. **Embedding Test**:
   ```python
   vectors = await embedding_service.embed_texts(["Hello", "World"])
   assert len(vectors) == 2
   assert len(vectors[0]) == 1536  # text-embedding-3-small dimension
   ```

3. **Retrieval Test**:
   - Upload document "SEO best practices..."
   - Query "SEO tips"
   - Verify relevant chunks returned

---

## Breaking Changes

None (new feature)

---

## References

- `backend/app/core/vector_store.py` - Pinecone client
- `backend/app/services/knowledge_service.py` - Knowledge extraction (for integration)
- [MODEL_STRATEGY.md](./MODEL_STRATEGY.md) - Embedding model choice
- [COLD_START_AND_DATA_HYGIENE.md](./COLD_START_AND_DATA_HYGIENE.md) - VectorDB = Optional

---

## Status

**Current**: VectorDB client exists but no upload pipeline  
**After Fix**: Complete Document → Chunk → Embed → Store → Retrieve flow
