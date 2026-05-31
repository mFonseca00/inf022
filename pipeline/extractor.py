"""
Extrator de regras usando pydantic-ai.
Recebe o texto de um documento e retorna um ResultadoExtracao validado.
"""

from pathlib import Path
from pydantic_ai import Agent
from pydantic_ai.settings import ModelSettings

from models import ParametrosLLM, ResultadoExtracao

# Carrega o system prompt a partir do arquivo de prompt dentro da pasta prompts
PROMPT_PATH = Path(__file__).parent / "prompts" / "prompt_extracao_regras_v3.md"
EXAMPLES_DIR = Path(__file__).parent / "docs_for_prompt_examples"
EXAMPLE_FILENAMES = [
    "01_documento_orientador_emissao_de_diploma-ensino_medio-ifba.pdf",
    "02_Edital_n_C2_BA_13_2024_Estagio_versao_final_assina_240905_230648.pdf",
    "10_SEI_4282227_Edital_18_2025-1.pdf",
    "28_Edital_N_C2_BA_13.2025.DG.DEMAT.IFA_SSA_assinado__1_.pdf",
]

with open(PROMPT_PATH, encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()


def extract_text_from_pdf(pdf_path: Path) -> str:
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    return "\n".join(pages)


def build_examples_context(current_filename: str) -> str:
    example_chunks: list[str] = []

    for example_filename in EXAMPLE_FILENAMES:
        if example_filename == current_filename:
            continue

        example_path = EXAMPLES_DIR / example_filename
        if not example_path.exists():
            continue

        example_text = extract_text_from_pdf(example_path).strip()
        if not example_text:
            continue

        example_chunks.append(
            f"### Exemplo de contexto: {example_filename}\n"
            f"{example_text}"
        )

    if not example_chunks:
        return ""

    return "\n\n".join(example_chunks)


def build_agent(model, settings: ModelSettings | None = None) -> Agent:
    return Agent(
        model=model,
        output_type=ResultadoExtracao,
        system_prompt=SYSTEM_PROMPT,
        model_settings=settings,
    )


def extract(
    text: str,
    filename: str,
    file_id: str,
    model,
    settings: ModelSettings | None = None,
    llm_parameters: ParametrosLLM | None = None,
) -> ResultadoExtracao:
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

    examples_context = build_examples_context(filename)

    user_message = (
        f"Arquivo: {filename}\n"
        f"ID do arquivo: {file_id}\n\n"
        f"{text}"
    )

    if examples_context:
        user_message = (
            f"{examples_context}\n\n"
            f"---\n\n"
            f"Documento atual:\n"
            f"{user_message}"
        )

    result = agent.run_sync(user_message)

    # Garante que os campos de metadados estão preenchidos
    resultado = result.output
    resultado.arquivo = filename
    resultado.id_arquivo = file_id
    if llm_parameters is not None:
        resultado.modelo = llm_parameters.model
    usage = result.usage
    resultado.tokens = usage.total_tokens if usage else None
    resultado.parametros_llm = llm_parameters

    return resultado
