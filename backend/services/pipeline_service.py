"""
Integração com a pipeline de extração.
Executa a extração em background e persiste o resultado via storage_service.
"""

import os
import re
import sys
import asyncio
from datetime import datetime
from pathlib import Path

import pdfplumber
from dotenv import load_dotenv

# Garante que o módulo pipeline seja encontrado
PIPELINE_DIR = Path(__file__).parent.parent.parent / "pipeline"
sys.path.insert(0, str(PIPELINE_DIR))

load_dotenv(PIPELINE_DIR / ".env")

from config import get_model, get_model_settings  # noqa: E402
from models import ParametrosLLM  # noqa: E402
from extractor import extract  # noqa: E402

from services import storage_service  # noqa: E402

# Registro em memória dos jobs em andamento: job_id -> status/resultado
_jobs: dict[str, dict] = {}


def _extract_text(pdf_path: Path) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _infer_file_id(filename: str) -> str:
    match = re.match(r"^(\d+)", filename)
    return match.group(1).zfill(2) if match else "00"


def _make_run_dir_name(model_name: str) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    safe_model = re.sub(r"[^\w\-.]", "_", model_name)
    return f"{timestamp}_{safe_model}"


def _get_setting_value(settings, key: str):
    if settings is None:
        return None
    if isinstance(settings, dict):
        return settings.get(key)
    return getattr(settings, key, None)


def get_job_status(job_id: str) -> dict | None:
    return _jobs.get(job_id)


async def iniciar_extracao(job_id: str, pdf_path: Path, original_filename: str) -> None:
    """Executa a extração em background e atualiza _jobs com o resultado."""
    _jobs[job_id] = {"status": "processando", "processo_id": None, "erro": None}

    try:
        model_name = os.getenv("MODEL", "gemini-flash-latest")
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

        text = await asyncio.to_thread(_extract_text, pdf_path)
        file_id = _infer_file_id(original_filename)

        resultado = await asyncio.to_thread(
            extract,
            text=text,
            filename=original_filename,
            file_id=file_id,
            model=model,
            settings=settings,
            llm_parameters=llm_parameters,
        )

        run_dir_name = _make_run_dir_name(model_name)
        stem = Path(original_filename).stem
        processo_id = storage_service.salvar_processo(
            data=resultado.model_dump(),
            run_dir_name=run_dir_name,
            filename=f"{stem}.json",
        )

        _jobs[job_id] = {"status": "pronto", "processo_id": processo_id, "erro": None}

    except Exception as e:
        _jobs[job_id] = {"status": "erro", "processo_id": None, "erro": str(e)}

    finally:
        # Remove o PDF temporário após o processamento
        try:
            pdf_path.unlink(missing_ok=True)
        except Exception:
            pass
