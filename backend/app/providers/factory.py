from functools import lru_cache
from .base import AIProvider
from ..config import get_settings


@lru_cache(maxsize=1)
def get_provider() -> AIProvider:
    settings = get_settings()
    mode = settings.AI_PROVIDER.lower()
    if mode in ("mock", "test", "none"):
        from .mock_provider import MockProvider
        return MockProvider()
    elif mode == "groq":
        from .groq_provider import GroqProvider
        return GroqProvider()
    elif mode == "local":
        from .local_provider import LocalProvider
        return LocalProvider()
    elif mode == "api":
        from .api_provider import APIProvider
        return APIProvider()
    else:
        raise ValueError(
            f"Unknown AI_PROVIDER: {mode!r}. "
            "Valid options: 'groq' (free), 'local' (Ollama), 'api' (Gemini), 'mock' (CI/testing)."
        )
