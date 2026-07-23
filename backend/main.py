from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import processos

app = FastAPI(title="Extrator de Regras IFBA", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(processos.router, prefix="/api/processos", tags=["processos"])


@app.get("/")
def health():
    return {"status": "ok"}
