import asyncio
import os
import sys
from unittest.mock import MagicMock, patch

# Add backend to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Mock external libraries to avoid import errors during test
sys.modules["pinecone"] = MagicMock()
sys.modules["langfuse"] = MagicMock()
sys.modules["langfuse.callback"] = MagicMock()
sys.modules["tavily"] = MagicMock()

# Mock environment variables before importing config
os.environ["PINECONE_API_KEY"] = "mock-pinecone-key"
os.environ["PINECONE_INDEX_NAME"] = "mock-index"
os.environ["LANGFUSE_PUBLIC_KEY"] = "mock-lf-pk"
os.environ["LANGFUSE_SECRET_KEY"] = "mock-lf-sk"
os.environ["TAVILY_API_KEY"] = "mock-tavily-key"

from app.core.vector_store import PineconeClient
from app.core.observability import LangFuseHandler
from app.core.search_client import TavilyClient

async def test_integrations():
    print("🚀 Testing Technical Integrations")
    print("============================================================")

    # 1. Test Pinecone Client
    print("\n1. Testing PineconeClient...")
    with patch("app.core.vector_store.Pinecone") as MockPinecone:
        # Setup mock
        mock_index = MagicMock()
        MockPinecone.return_value.Index.return_value = mock_index
        
        client = PineconeClient()
        
        # Test Upsert
        await client.upsert_vectors(
            tenant_id="tenant-123",
            vectors=[{"id": "vec1", "values": [0.1, 0.2], "metadata": {"text": "hello"}}]
        )
        
        # Verify call arguments
        call_args = mock_index.upsert.call_args
        if call_args:
            vectors = call_args.kwargs.get('vectors', [])
            if vectors and vectors[0]['metadata'].get('tenant_id') == "tenant-123":
                print("   ✅ Upsert: tenant_id enforced in metadata")
            else:
                print("   ❌ Upsert: tenant_id missing or incorrect")
        else:
            print("   ❌ Upsert: Method not called")

        # Test Query
        mock_index.query.return_value.matches = []
        await client.query_vectors(tenant_id="tenant-123", vector=[0.1, 0.2])
        
        call_args = mock_index.query.call_args
        if call_args:
            filter_arg = call_args.kwargs.get('filter', {})
            if filter_arg.get('tenant_id') == "tenant-123":
                print("   ✅ Query: tenant_id filter applied")
            else:
                print("   ❌ Query: tenant_id filter missing")
        else:
            print("   ❌ Query: Method not called")

    # 2. Test LangFuse Handler
    print("\n2. Testing LangFuseHandler...")
    with patch("app.core.observability.Langfuse") as MockLangfuse:
        handler = LangFuseHandler()
        if handler.langfuse:
            print("   ✅ LangFuse initialized")
        else:
            print("   ❌ LangFuse failed to init")
            
        cb = handler.get_callback_handler("user-1", "session-1")
        if cb:
            print("   ✅ CallbackHandler created")
        else:
            print("   ❌ CallbackHandler failed")

    # 3. Test Tavily Client
    print("\n3. Testing TavilyClient...")
    with patch("app.core.search_client.TavilySDK") as MockTavily:
        mock_tavily_instance = MagicMock()
        MockTavily.return_value = mock_tavily_instance
        
        client = TavilyClient()
        
        # Test Search
        mock_tavily_instance.search.return_value = {"results": [{"title": "Test Result"}]}
        results = await client.search("test query")
        
        if len(results) == 1 and results[0]["title"] == "Test Result":
            print("   ✅ Search executed successfully")
        else:
            print("   ❌ Search failed or empty results")

    print("\n============================================================")
    print("🎉 Integration Tests Completed")

if __name__ == "__main__":
    asyncio.run(test_integrations())
