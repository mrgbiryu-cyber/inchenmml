import os
from typing import Optional
from langfuse import Langfuse
from langfuse.callback import CallbackHandler
from app.core.config import settings

class LangFuseHandler:
    """
    Handler for LangFuse observability.
    Provides callback handlers for LangChain/LangGraph.
    """
    
    def __init__(self):
        self.public_key = settings.LANGFUSE_PUBLIC_KEY
        self.secret_key = settings.LANGFUSE_SECRET_KEY
        self.host = settings.LANGFUSE_HOST
        
        if self.public_key and self.secret_key:
            self.langfuse = Langfuse(
                public_key=self.public_key,
                secret_key=self.secret_key,
                host=self.host
            )
        else:
            print("⚠️ LangFuse credentials not set. Observability disabled.")
            self.langfuse = None

    def get_callback_handler(self, user_id: str, session_id: str) -> Optional[CallbackHandler]:
        """
        Get LangChain callback handler for tracing.
        """
        if not self.langfuse:
            return None
            
        return CallbackHandler(
            public_key=self.public_key,
            secret_key=self.secret_key,
            host=self.host,
            user_id=user_id,
            session_id=session_id
        )

    def trace(self, name: str, **kwargs):
        """
        Manual tracing wrapper
        """
        if self.langfuse:
            return self.langfuse.trace(name=name, **kwargs)
        return None
