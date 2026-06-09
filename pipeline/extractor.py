"""
Extrator de regras usando pydantic-ai.
Recebe o texto de um documento e retorna um ResultadoExtracao validado.
"""

import json
from pathlib import Path
from pydantic_ai import Agent
from pydantic_ai.settings import ModelSettings

from models import ParametrosLLM, ResultadoExtracao, ResultadoLote

PROMPT_PATH = Path(__file__).parent / "prompts" / "prompt_extracao_regras_v4.md"
EXAMPLES_DIR = Path(__file__).parent / "docs_for_prompt_examples"
EXAMPLE_FILENAMES = [
    "01_documento_orientador_emissao_de_diploma-ensino_medio-ifba.pdf",
    "02_Edital_n_C2_BA_13_2024_Estagio_versao_final_assina_240905_230648.pdf",
    "10_SEI_4282227_Edital_18_2025-1.pdf",
    "28_Edital_N_C2_BA_13.2025.DG.DEMAT.IFA_SSA_assinado__1_.pdf",
]

with open(PROMPT_PATH, encoding="utf-8") as f:
    BASE_SYSTEM_PROMPT = f.read()


def extract_text_from_pdf(pdf_path: Path) -> str:
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    return "\n".join(pages)


def build_examples_context() -> str:
    example_chunks: list[str] = []

    for i, example_filename in enumerate(EXAMPLE_FILENAMES, start=1):
        pdf_path = EXAMPLES_DIR / example_filename
        json_path = EXAMPLES_DIR / (Path(example_filename).stem + ".json")

        if not pdf_path.exists() or not json_path.exists():
            continue

        pdf_text = extract_text_from_pdf(pdf_path).strip()
        if not pdf_text:
            continue

        with open(json_path, encoding="utf-8") as f:
            expected_json = json.load(f)

        example_chunks.append(
            f"### Exemplo {i}: {example_filename}\n\n"
            f"**Texto do documento:**\n\n"
            f"{pdf_text}\n\n"
            f"**Extração esperada:**\n\n"
            f"```json\n{json.dumps(expected_json, ensure_ascii=False, indent=2)}\n```"
        )

    if not example_chunks:
        return ""

    return (
        "\n\n---\n\n".join(example_chunks)
        + "\n\n---\n\n"
        "Agora processe apenas o documento atual seguindo as instruções acima e os padrões demonstrados nos exemplos. "
        "Retorne apenas o JSON, sem texto adicional antes ou depois.\n"
    )


EXAMPLES_CONTEXT = build_examples_context()
SYSTEM_PROMPT = (
    BASE_SYSTEM_PROMPT.rstrip()
    + ("\n\n" + EXAMPLES_CONTEXT if EXAMPLES_CONTEXT else "")
)


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

    user_message = (
        f"Arquivo: {filename}\n"
        f"ID do arquivo: {file_id}\n\n"
        f"{text}"
    )

    prompt_utilizado = PROMPT_PATH.name
    result = agent.run_sync(user_message)

    resultado = result.output
    resultado.arquivo = filename
    resultado.id_arquivo = file_id
    if llm_parameters is not None:
        resultado.modelo = llm_parameters.model
    usage = result.usage
    resultado.tokens = usage.total_tokens if usage else None
    resultado.parametros_llm = llm_parameters
    resultado.prompt_utilizado = prompt_utilizado

    return resultado


def extract_batch(
    documents: list[dict],
    model,
    settings: ModelSettings | None = None,
    llm_parameters: ParametrosLLM | None = None,
) -> list[ResultadoExtracao]:
    """
    Extrai regras de múltiplos documentos em uma única chamada ao LLM.

    Cada item de `documents` deve ter as chaves: text, filename, file_id.
    Os tokens do system prompt são pagos uma única vez para todo o lote.

    Retorna os resultados na mesma ordem dos documentos de entrada.
    """
    agent = Agent(
        model=model,
        output_type=ResultadoLote,
        system_prompt=SYSTEM_PROMPT,
        model_settings=settings,
    )

    partes = []
    for doc in documents:
        partes.append(
            f"=== DOCUMENTO: {doc['filename']} | ID: {doc['file_id']} ===\n\n"
            f"{doc['text']}"
        )

    user_message = (
        "Processe cada documento abaixo e retorne a extração de todos no campo "
        "`resultados`, na mesma ordem em que aparecem.\n\n"
        + "\n\n".join(partes)
    )

    prompt_utilizado = PROMPT_PATH.name
    result = agent.run_sync(user_message)

    usage = result.usage
    tokens_total = usage.total_tokens if usage else None
    n_docs = len(documents)
    tokens_media = tokens_total // n_docs if tokens_total else None

    resultados = result.output.resultados
    for resultado, doc in zip(resultados, documents):
        resultado.arquivo = doc["filename"]
        resultado.id_arquivo = doc["file_id"]
        if llm_parameters is not None:
            resultado.modelo = llm_parameters.model
        resultado.tokens = None
        resultado.tokens_media_lote = tokens_media
        resultado.arquivos_no_lote = n_docs
        resultado.parametros_llm = llm_parameters
        resultado.prompt_utilizado = prompt_utilizado

    return resultados
