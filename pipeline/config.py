"""
Configuração do provider, modelo e parâmetros de execução da pipeline.

Para trocar o modelo, basta ajustar as variáveis de ambiente:

  # Google Gemini (gratuito)
  PROVIDER=google
  MODEL=gemini-2.0-flash
  GOOGLE_API_KEY=sua_chave

  # Anthropic Claude
  PROVIDER=anthropic
  MODEL=claude-3-5-haiku-latest
  ANTHROPIC_API_KEY=sua_chave

  # OpenAI
  PROVIDER=openai
  MODEL=gpt-4o-mini
  OPENAI_API_KEY=sua_chave

  # Ollama local (via Docker)
  PROVIDER=ollama
  MODEL=llama3.2
  OLLAMA_BASE_URL=http://localhost:11434/v1  # padrão

Parâmetros de execução (opcionais — se omitidos, usam o default do provider):

  TEMPERATURE=0.0      # 0.0 = mais determinístico, 1.0 = mais criativo
  MAX_TOKENS=8192      # limite de tokens na resposta
  TIMEOUT=120          # timeout por requisição em segundos
"""

import os
from pydantic_ai.models.gemini import GeminiModel
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.settings import ModelSettings


def get_model():
    provider = os.getenv("PROVIDER", "google").lower()
    model_name = os.getenv("MODEL", "gemini-2.0-flash")

    if provider == "google":
        return GeminiModel(model_name)

    elif provider == "anthropic":
        return AnthropicModel(model_name)

    elif provider == "openai":
        return OpenAIModel(model_name)

    elif provider == "ollama":
        # Ollama expõe um endpoint OpenAI-compatible
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        return OpenAIModel(
            model_name,
            base_url=base_url,
            api_key="ollama",  # Ollama não exige chave, mas o campo é obrigatório
        )

    else:
        raise ValueError(
            f"Provider '{provider}' não suportado. "
            "Use: google, anthropic, openai ou ollama."
        )


def get_model_settings() -> ModelSettings:
    """
    Lê os parâmetros de execução do .env e retorna um ModelSettings.
    Campos não definidos ficam como None (o provider usa seu próprio default).
    """
    def _float(key):
        v = os.getenv(key)
        return float(v) if v is not None else None

    def _int(key):
        v = os.getenv(key)
        return int(v) if v is not None else None

    return ModelSettings(
        temperature=_float("TEMPERATURE"),
        max_tokens=_int("MAX_TOKENS"),
        timeout=_float("TIMEOUT"),
    )
