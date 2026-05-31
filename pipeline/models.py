from typing import Optional

from pydantic import BaseModel


class ParametrosLLM(BaseModel):
    provider: str
    model: str
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    timeout: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    base_url: Optional[str] = None


class Regra(BaseModel):
    id: str
    descricao: str
    tipo: str  # obrigatória | opcional | restritiva | condicional
    condicao: Optional[str]
    referencia: Optional[str]


class ResultadoExtracao(BaseModel):
    arquivo: str
    id_arquivo: str
    modelo: str
    tokens: Optional[int]
    parametros_llm: Optional[ParametrosLLM] = None
    regras: list[Regra]
