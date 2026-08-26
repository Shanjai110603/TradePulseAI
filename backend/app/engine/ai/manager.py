from typing import Dict, Optional, List, Any
from app.core.config import settings
from app.engine.ai.base import AIProvider
from app.engine.ai.mock_ai import MockAIProvider
from app.engine.ai.openai_provider import OpenAIProvider
from app.engine.ai.openrouter_provider import OpenRouterAIProvider


class AIProviderManager:
    """
    Registry and factory for AI analysis providers.
    Supports switching between Mock, OpenRouter, OpenAI, Anthropic, Gemini.
    """

    def __init__(self):
        self._providers: Dict[str, AIProvider] = {
            "mock": MockAIProvider(),
            "openai": OpenAIProvider(),
            "openrouter": OpenRouterAIProvider(),
        }
        self._default_provider_name = settings.AI_PROVIDER

    def register_provider(self, name: str, provider: AIProvider):
        self._providers[name] = provider

    def get_provider(self, provider_name: Optional[str] = None) -> AIProvider:
        name = provider_name or self._default_provider_name
        provider = self._providers.get(name)
        if not provider:
            return self._providers["mock"]
        return provider

    def get_mock_provider(self) -> MockAIProvider:
        return self._providers["mock"]  # type: ignore

    def list_providers(self) -> List[Dict[str, Any]]:
        return [
            {"id": name, "name": name.capitalize()}
            for name in self._providers.keys()
        ]


# Singleton instance
ai_manager = AIProviderManager()
