"""
Extrator de regras usando pydantic-ai.
Recebe o texto de um documento e retorna um ResultadoExtracao validado.
"""

from pathlib import Path
from pydantic_ai import Agent
from pydantic_ai.settings import ModelSettings
from models import ResultadoExtracao

# Carrega o system prompt a partir do arquivo de prompt (v2 por padrão)
PROMPT_PATH = Path(__file__).parent.parent / "prompt_extracao_regras_v2.md"

with open(PROMPT_PATH, encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()


def build_agent(model, settings: ModelSettings | None = None) -> Agent:
    return Agent(
        model=model,
        output_type=ResultadoExtracao,
        system_prompt=SYSTEM_PROMPT,
        model_settings=settings,
    )


def extract(text: str, filename: str, file_id: str, model, settings: ModelSettings | None = None) -> ResultadoExtracao:
    """
    Extrai regras de um texto de documento.

    Args:
        text:     Conteúdo extraído do PDF.
        filename: Nome original do arquivo (vai para o campo 'arquivo' no JSON).
        file_id:  Identificador numérico (ex: "01", "10").
        model:    Instância de modelo do pydantic-ai (de config.get_model()).

    Returns:
        ResultadoExtracao com as regras extraídas e validadas.
    """
    agent = build_agent(model, settings)

    user_message = (
        f"Arquivo: {filename}\n"
        f"ID do arquivo: {file_id}\n\n"
        f"{text}"
    )

    result = agent.run_sync(user_message)

    # Garante que os campos de metadados estão preenchidos
    resultado = result.output
    resultado.arquivo = filename
    resultado.id_arquivo = file_id
    usage = result.usage
    resultado.tokens = usage.total_tokens if usage else None

    return resultado
