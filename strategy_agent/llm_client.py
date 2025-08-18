"""
Simple LLM Client using Instructor's from_provider method
KISS principle: Keep It Simple, Stupid
"""
import os
import logging
from typing import Any, Dict, Optional
from dataclasses import dataclass

try:
    import instructor
except ImportError:
    instructor = None

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """Simple LLM configuration"""
    model: str  # Format: "provider/model" or just "model"
    api_key: str
    temperature: float = 0.3
    max_tokens: Optional[int] = None
    timeout: int = 300


class SimpleLLMClient:
    """
    Simple LLM client using instructor.from_provider()
    Supports any provider that instructor supports
    """
    
    def __init__(self, config: LLMConfig):
        if instructor is None:
            raise ImportError("instructor package is required. Install with: pip install instructor")
        
        self.config = config
        
        # Parse provider from model string
        if "/" in config.model:
            provider, model_name = config.model.split("/", 1)
        else:
            provider = "openai"
            model_name = config.model
        
        # DeepSeek uses OpenAI-compatible API
        if provider == "deepseek":
            # Use OpenAI client with DeepSeek's base URL
            from openai import AsyncOpenAI
            base_client = AsyncOpenAI(
                api_key=config.api_key,
                base_url="https://api.deepseek.com"
            )
            self.client = instructor.from_openai(base_client)
            self.model_name = model_name  # Store just the model name
            logger.info(f"Initialized DeepSeek client for model: {model_name}")
        else:
            # Use instructor.from_provider for other providers
            try:
                self.client = instructor.from_provider(
                    model=config.model,
                    api_key=config.api_key
                )
                self.model_name = config.model  # Use full model string
                logger.info(f"Initialized LLM client for model: {config.model}")
            except Exception as e:
                logger.error(f"Failed to initialize LLM client for {config.model}: {e}")
                raise
    
    async def create_completion(self, messages: list, response_model: type, **kwargs) -> Any:
        """Create completion using instructor"""
        try:
            completion_kwargs = {
                "model": self.model_name,  # Use the parsed model name
                "response_model": response_model,
                "messages": messages,
                "temperature": kwargs.get("temperature", self.config.temperature),
                "max_retries": kwargs.get("max_retries", 2)
            }
            
            if self.config.max_tokens:
                completion_kwargs["max_tokens"] = self.config.max_tokens
            
            return await self.client.chat.completions.create(**completion_kwargs)
            
        except Exception as e:
            logger.error(f"LLM completion failed: {e}")
            raise
    
    def get_provider_name(self) -> str:
        """Get provider name from model string"""
        if "/" in self.config.model:
            return self.config.model.split("/")[0]
        return "openai"  # Default assumption


def create_llm_config_from_env() -> LLMConfig:
    """
    Create LLM configuration from environment variables
    
    Environment variables:
        LLM_MODEL: Model name (e.g., "openai/gpt-4o-mini", "anthropic/claude-3-haiku", "groq/llama-3.1-8b-instant")
        LLM_API_KEY: API key for the provider
        LLM_TEMPERATURE: Temperature for generation (default: 0.3)
        LLM_MAX_TOKENS: Max tokens for generation (optional)
        LLM_TIMEOUT: Request timeout in seconds (default: 300)
    
    Returns:
        LLM configuration
        
    Raises:
        ValueError: If required environment variables are missing
    """
    model = os.getenv("LLM_MODEL")
    api_key = os.getenv("LLM_API_KEY")
    
    if not model:
        raise ValueError("LLM_MODEL environment variable is required")
    if not api_key:
        raise ValueError("LLM_API_KEY environment variable is required")
    
    return LLMConfig(
        model=model,
        api_key=api_key,
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
        max_tokens=int(os.getenv("LLM_MAX_TOKENS")) if os.getenv("LLM_MAX_TOKENS") else None,
        timeout=int(os.getenv("LLM_TIMEOUT", "300"))
    )


def create_llm_client(config: LLMConfig = None) -> SimpleLLMClient:
    """
    Create LLM client from configuration
    
    Args:
        config: LLM configuration (if None, will create from environment variables)
        
    Returns:
        LLM client instance
    """
    if config is None:
        config = create_llm_config_from_env()
    
    return SimpleLLMClient(config)


# Singleton pattern for global LLM client
_global_llm_client: Optional[SimpleLLMClient] = None


def get_llm_client() -> SimpleLLMClient:
    """
    Get or create global LLM client instance
    
    Returns:
        LLM client instance
    """
    global _global_llm_client
    
    if _global_llm_client is None:
        config = create_llm_config_from_env()
        _global_llm_client = SimpleLLMClient(config)
    
    return _global_llm_client


def set_llm_client(client: SimpleLLMClient):
    """Set global LLM client (for testing/dependency injection)"""
    global _global_llm_client
    _global_llm_client = client


async def test_llm_client(config: LLMConfig = None):
    """Test LLM client with a simple completion"""
    if config is None:
        config = create_llm_config_from_env()
    
    client = create_llm_client(config)
    
    try:
        from pydantic import BaseModel
        
        class TestResponse(BaseModel):
            message: str
            provider: str
        
        response = await client.create_completion(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say hello and tell me what provider you are using."}
            ],
            response_model=TestResponse
        )
        
        print(f"✅ {client.get_provider_name()} client test successful")
        print(f"Response: {response.message}")
        print(f"Provider: {response.provider}")
        return True
        
    except Exception as e:
        print(f"❌ {client.get_provider_name()} client test failed: {e}")
        return False


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_llm_client())