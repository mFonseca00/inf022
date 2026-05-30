from typing import Optional
from pydantic import BaseModel


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
    regras: list[Regra]
