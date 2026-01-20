import httpx
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from app.core.config import settings

router = APIRouter()

@router.get("/ollama")
async def list_ollama_models():
    """List models available in local Ollama"""
    # Assuming standard Ollama endpoint, but we can make it configurable
    ollama_url = "http://localhost:11434/api/tags"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(ollama_url, timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                models = []
                for m in data.get("models", []):
                    models.append({
                        "id": m["name"],
                        "name": m["name"],
                        "details": m.get("details", {})
                    })
                return models
            return []
    except Exception as e:
        print(f"Ollama connection error: {e}")
        return []

@router.get("/openrouter")
async def list_openrouter_models():
    """List models available via OpenRouter"""
    url = "https://openrouter.ai/api/v1/models"
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                models = []
                for m in data.get("data", []):
                    models.append({
                        "id": m["id"],
                        "name": m.get("name") or m["id"],
                        "pricing": m.get("pricing", {}),
                        "context_length": m.get("context_length")
                    })
                return models
            return []
    except Exception as e:
        print(f"OpenRouter API error: {e}")
        return []
