"""
Leitura e escrita dos JSONs de resultados em results/.
Cada processo corresponde a um arquivo .json dentro de uma subpasta de execução.
"""

import json
import uuid
from pathlib import Path
from typing import Optional

RESULTS_DIR = Path(__file__).parent.parent.parent / "results"


def _all_result_dirs() -> list[Path]:
    if not RESULTS_DIR.exists():
        return []
    return sorted(
        [d for d in RESULTS_DIR.iterdir() if d.is_dir()],
        key=lambda d: d.name,
        reverse=True,
    )


def _all_json_files() -> list[Path]:
    files = []
    for run_dir in _all_result_dirs():
        for f in sorted(run_dir.glob("*.json")):
            if not f.name.startswith("_"):
                files.append(f)
    return files


def listar_processos() -> list[dict]:
    processos = []
    for json_path in _all_json_files():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            processos.append({
                "id": _make_id(json_path),
                "arquivo": data.get("arquivo", json_path.stem),
                "modelo": data.get("modelo", ""),
                "total_regras": len(data.get("regras", [])),
                "run_dir": json_path.parent.name,
                "filename": json_path.name,
            })
        except Exception:
            continue
    return processos


def obter_processo(processo_id: str) -> Optional[dict]:
    json_path = _find_by_id(processo_id)
    if not json_path:
        return None
    data = json.loads(json_path.read_text(encoding="utf-8"))
    data["id"] = processo_id
    return data


def salvar_processo(data: dict, run_dir_name: str, filename: str) -> str:
    run_dir = RESULTS_DIR / run_dir_name
    run_dir.mkdir(parents=True, exist_ok=True)
    json_path = run_dir / filename
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return _make_id(json_path)


def atualizar_regra(processo_id: str, regra_id: str, dados: dict) -> Optional[dict]:
    json_path = _find_by_id(processo_id)
    if not json_path:
        return None
    data = json.loads(json_path.read_text(encoding="utf-8"))
    regras = data.get("regras", [])
    for i, r in enumerate(regras):
        if r["id"] == regra_id:
            regras[i] = {**r, **dados, "id": regra_id}
            json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return regras[i]
    return None


def remover_regra(processo_id: str, regra_id: str) -> bool:
    json_path = _find_by_id(processo_id)
    if not json_path:
        return False
    data = json.loads(json_path.read_text(encoding="utf-8"))
    antes = len(data.get("regras", []))
    data["regras"] = [r for r in data.get("regras", []) if r["id"] != regra_id]
    if len(data["regras"]) == antes:
        return False
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def adicionar_regra(processo_id: str, regra: dict) -> Optional[dict]:
    json_path = _find_by_id(processo_id)
    if not json_path:
        return None
    data = json.loads(json_path.read_text(encoding="utf-8"))
    regra["id"] = str(uuid.uuid4())[:8]
    data.setdefault("regras", []).append(regra)
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return regra


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_id(json_path: Path) -> str:
    """ID estável derivado do caminho relativo: <run_dir>/<stem>."""
    return f"{json_path.parent.name}__{json_path.stem}"


def _find_by_id(processo_id: str) -> Optional[Path]:
    parts = processo_id.split("__", 1)
    if len(parts) != 2:
        return None
    run_dir_name, stem = parts
    candidate = RESULTS_DIR / run_dir_name / f"{stem}.json"
    return candidate if candidate.exists() else None
