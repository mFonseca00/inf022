import asyncio
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from services import storage_service, pipeline_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas de request/response
# ---------------------------------------------------------------------------

class RegraUpdate(BaseModel):
    descricao: str | None = None
    tipo: str | None = None
    condicao: str | None = None
    referencia: str | None = None


class RegraCreate(BaseModel):
    descricao: str
    tipo: str = "obrigatória"
    condicao: str | None = None
    referencia: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
def listar_processos():
    """Lista todos os processos existentes em results/."""
    return storage_service.listar_processos()


@router.get("/{processo_id}")
def obter_processo(processo_id: str):
    """Retorna um processo com todas as suas regras."""
    processo = storage_service.obter_processo(processo_id)
    if not processo:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")
    return processo


@router.post("")
async def criar_processo(file: UploadFile = File(...)):
    """
    Recebe um PDF, inicia a extração em background e retorna um job_id
    para acompanhar o progresso via GET /api/processos/jobs/{job_id}.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Apenas arquivos PDF são aceitos.")

    # Salva o PDF em arquivo temporário para não manter em memória durante a extração
    tmp_dir = Path(tempfile.gettempdir()) / "ifba_uploads"
    tmp_dir.mkdir(exist_ok=True)
    tmp_path = tmp_dir / f"{uuid.uuid4().hex}_{file.filename}"
    tmp_path.write_bytes(await file.read())

    job_id = uuid.uuid4().hex
    asyncio.create_task(
        pipeline_service.iniciar_extracao(
            job_id=job_id,
            pdf_path=tmp_path,
            original_filename=file.filename,
        )
    )

    return {"job_id": job_id, "status": "processando"}


@router.get("/jobs/{job_id}")
def status_job(job_id: str):
    """
    Retorna o status de um job de extração.
    status: processando | pronto | erro
    Quando pronto, retorna também o processo_id para buscar o resultado.
    """
    job = pipeline_service.get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado.")
    return job


@router.put("/{processo_id}/regras/{regra_id}")
def atualizar_regra(processo_id: str, regra_id: str, dados: RegraUpdate):
    """Edita os campos de uma regra existente."""
    regra = storage_service.atualizar_regra(
        processo_id, regra_id, dados.model_dump(exclude_none=True)
    )
    if not regra:
        raise HTTPException(status_code=404, detail="Processo ou regra não encontrados.")
    return regra


@router.delete("/{processo_id}/regras/{regra_id}")
def remover_regra(processo_id: str, regra_id: str):
    """Remove uma regra de um processo."""
    removido = storage_service.remover_regra(processo_id, regra_id)
    if not removido:
        raise HTTPException(status_code=404, detail="Processo ou regra não encontrados.")
    return {"detail": "Regra removida com sucesso."}


@router.post("/{processo_id}/regras")
def adicionar_regra(processo_id: str, regra: RegraCreate):
    """Adiciona uma nova regra a um processo existente."""
    nova = storage_service.adicionar_regra(processo_id, regra.model_dump())
    if not nova:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")
    return nova
