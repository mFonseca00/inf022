"""
Entry point da pipeline de extração.

Uso:
    python run.py --input ../docs --output ../results

    # Ou sobrepondo provider/modelo por argumento:
    python run.py --input ../docs --output ../results --provider ollama --model llama3.2

Cada execução cria uma subpasta com timestamp dentro de --output, ex:
    results/
    └── 2025-06-01_14-32-05_gemini-2.0-flash/
        ├── 01_diploma.json
        └── 10_edital.json
"""

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).parent / ".env")

from config import get_model, get_model_settings
from models import ParametrosLLM
from extractor import extract
from evaluate import run_evaluation
from pdf_utils import extract_text_from_pdf


def infer_file_id(filename: str) -> str:
    """Tenta inferir o id_arquivo a partir do prefixo numérico do nome do arquivo."""
    match = re.match(r"^(\d+)", filename)
    return match.group(1).zfill(2) if match else "00"


def make_run_dir(base_output: Path, model_name: str) -> Path:
    """Cria uma subpasta única para esta execução, com timestamp e nome do modelo."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # Remove caracteres inválidos em nomes de pasta (ex: "/" em nomes de modelo)
    safe_model = re.sub(r"[^\w\-.]", "_", model_name)
    run_dir = base_output / f"{timestamp}_{safe_model}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _get_setting_value(settings, key: str):
    if settings is None:
        return None
    if isinstance(settings, dict):
        return settings.get(key)
    return getattr(settings, key, None)


def process_folder(input_dir: Path, output_dir: Path, model, model_name: str, settings=None, llm_parameters=None, evaluate: bool = False):
    run_dir = make_run_dir(output_dir, model_name)
    pdfs = sorted(input_dir.glob("*.pdf"))

    if not pdfs:
        print(f"Nenhum PDF encontrado em: {input_dir}")
        return

    print(f"Encontrados {len(pdfs)} PDFs.")
    print(f"Resultados serão salvos em: {run_dir}\n")

    for pdf_path in pdfs:
        print(f"Processando: {pdf_path.name}")
        try:
            text = extract_text_from_pdf(pdf_path)
            file_id = infer_file_id(pdf_path.name)

            resultado = extract(
                text=text,
                filename=pdf_path.name,
                file_id=file_id,
                model=model,
                settings=settings,
                llm_parameters=llm_parameters,
            )

            output_path = run_dir / f"{pdf_path.stem}.json"
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(resultado.model_dump(), f, ensure_ascii=False, indent=2)

            print(f"  OK {len(resultado.regras)} regras extraidas -> {output_path.name}")

        except Exception as e:
            print(f"  ERRO ao processar {pdf_path.name}: {e}")

    print("\nConcluido.")

    if evaluate:
        print()
        run_evaluation(run_dir)


def main():
    parser = argparse.ArgumentParser(description="Pipeline de extração de regras institucionais")
    parser.add_argument("--input", required=True, help="Pasta com os PDFs de entrada")
    parser.add_argument("--output", required=True, help="Pasta base onde as subpastas de execução serão criadas")
    parser.add_argument("--provider", help="Provider (google, anthropic, openai, ollama) — sobrepoem PROVIDER do .env")
    parser.add_argument("--model", help="Nome do modelo — sobrepoem MODEL do .env")
    parser.add_argument("--evaluate", action="store_true", help="Executa a avaliacao automaticamente apos a extracao")
    args = parser.parse_args()

    # Argumentos de CLI têm prioridade sobre variáveis de ambiente
    if args.provider:
        os.environ["PROVIDER"] = args.provider
    if args.model:
        os.environ["MODEL"] = args.model

    model_name = os.getenv("MODEL", "gemini-2.0-flash")
    provider = os.getenv("PROVIDER", "google").lower()
    base_url = os.getenv("OLLAMA_BASE_URL") if provider == "ollama" else None
    model = get_model()
    settings = get_model_settings()
    llm_parameters = ParametrosLLM(
        provider=provider,
        model=model_name,
        temperature=_get_setting_value(settings, "temperature"),
        max_tokens=_get_setting_value(settings, "max_tokens"),
        timeout=_get_setting_value(settings, "timeout"),
        top_p=_get_setting_value(settings, "top_p"),
        top_k=_get_setting_value(settings, "top_k"),
        base_url=base_url,
    )
    input_dir = Path(args.input)
    output_dir = Path(args.output)

    process_folder(input_dir, output_dir, model, model_name, settings, llm_parameters, evaluate=args.evaluate)


if __name__ == "__main__":
    main()
