"""
Avaliador de extrações geradas pela pipeline.

Compara os JSONs de um diretório de resultados com as extrações manuais
validadas da planilha extracoes_manuais_validadas.xlsx.

Uso:
    python evaluate.py --results ../results/2026-06-02_gemini-flash-latest
    python evaluate.py --results ../results/2026-06-02_gemini-flash-latest --spreadsheet ../extracoes_manuais_validadas.xlsx
"""

import argparse
import json
import re
import unicodedata
from pathlib import Path

import openpyxl


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize(text: str) -> str:
    """Minúsculas, sem acentos, sem pontuação, tokens separados por espaço."""
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def token_overlap(a: str, b: str) -> float:
    """Jaccard sobre tokens normalizados."""
    ta = set(normalize(a).split())
    tb = set(normalize(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def rule_similarity(extracted: dict, reference: dict) -> dict:
    """
    Score composto entre uma regra extraída e uma regra de referência.

    Pesos:
      60% descricao  — Jaccard sobre tokens
      20% tipo       — match exato após normalização
      20% condicao   — Jaccard, ou 1.0 se ambos null, ou 0.0 se só um é null
    """
    desc_score = token_overlap(
        str(extracted.get("descricao") or ""),
        str(reference.get("descricao") or ""),
    )

    tipo_extr = normalize(str(extracted.get("tipo") or ""))
    tipo_ref  = normalize(str(reference.get("tipo") or ""))
    tipo_score = 1.0 if tipo_extr == tipo_ref else 0.0

    cond_extr = extracted.get("condicao")
    cond_ref  = reference.get("condicao")
    if cond_extr is None and cond_ref is None:
        cond_score = 1.0
    elif cond_extr is None or cond_ref is None:
        cond_score = 0.0
    else:
        cond_score = token_overlap(str(cond_extr), str(cond_ref))

    combined = round(0.6 * desc_score + 0.2 * tipo_score + 0.2 * cond_score, 3)
    return {
        "score_descricao": round(desc_score, 3),
        "score_tipo":      round(tipo_score, 3),
        "score_condicao":  round(cond_score, 3),
        "score_combinado": combined,
    }


def best_rule_match(extracted: dict, reference_rules: list) -> dict:
    """Retorna o score do melhor match dentre todas as regras de referência."""
    if not reference_rules:
        return {"score_descricao": 0.0, "score_tipo": 0.0, "score_condicao": 0.0, "score_combinado": 0.0}
    scores = [rule_similarity(extracted, ref) for ref in reference_rules]
    return max(scores, key=lambda s: s["score_combinado"])


# ---------------------------------------------------------------------------
# Leitura da planilha
# ---------------------------------------------------------------------------

def load_spreadsheet(path: Path) -> dict[str, dict]:
    """
    Retorna dict keyed por id_arquivo (string, ex: "1", "10", "43").
    Valor: {"nome": str, "regras": [{"descricao", "tipo", "condicao"}, ...]}

    Formato da planilha:
      col[0] = Id_arquivo
      col[1] = Nome Resolução
      col[4] = Regras validadas — fragmento JSON: "regras": [{id, descricao, tipo, condicao, referencia}, ...]
    """
    wb = openpyxl.load_workbook(path)
    ws = wb.active

    records: dict[str, dict] = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        if len(row) < 5:
            continue
        id_arq      = row[0]
        nome        = row[1]
        regras_json = row[4]

        if id_arq is None:
            continue

        try:
            id_str = str(int(float(str(id_arq).strip())))
        except (ValueError, TypeError):
            id_str = str(id_arq).strip()

        if not regras_json or not str(regras_json).strip():
            continue

        try:
            parsed = json.loads("{" + str(regras_json) + "}")
            regras = [
                {
                    "descricao": r.get("descricao") or "",
                    "tipo":      r.get("tipo") or "",
                    "condicao":  r.get("condicao"),
                }
                for r in parsed.get("regras", [])
                if r.get("descricao")
            ]
        except (json.JSONDecodeError, KeyError):
            continue

        if not regras:
            continue

        records[id_str] = {
            "nome":   str(nome) if nome else "",
            "regras": regras,
        }

    return records


# ---------------------------------------------------------------------------
# Avaliação de um único JSON
# ---------------------------------------------------------------------------

# MATCH_THRESHOLD = 0.25  # score mínimo para considerar uma regra "encontrada"
MATCH_THRESHOLD = 0.2


def evaluate_file(json_path: Path, spreadsheet_data: dict[str, dict]) -> dict | None:
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    id_arquivo = str(data.get("id_arquivo", "")).lstrip("0") or data.get("id_arquivo", "")
    # garante que "01" vire "1", mas "10" continue "10"
    try:
        id_arquivo = str(int(id_arquivo))
    except ValueError:
        pass

    if id_arquivo not in spreadsheet_data:
        return {
            "arquivo": data.get("arquivo"),
            "id_arquivo": data.get("id_arquivo"),
            "status": "sem_referencia",
            "mensagem": f"id_arquivo '{id_arquivo}' não encontrado na planilha.",
        }

    ref = spreadsheet_data[id_arquivo]
    tokens_extracao = data.get("tokens")
    regras_extraidas: list[dict] = data.get("regras", [])
    n_extraidas = len(regras_extraidas)
    n_referencia = len(ref["regras"])

    regras_avaliadas = []
    for regra in regras_extraidas:
        match = best_rule_match(regra, ref["regras"])
        encontrada = match["score_combinado"] >= MATCH_THRESHOLD

        regras_avaliadas.append({
            "id":                       regra.get("id"),
            "descricao":                regra.get("descricao", ""),
            "tipo":                     regra.get("tipo"),
            "condicao":                 regra.get("condicao"),
            "encontrada_na_referencia": encontrada,
            "melhor_score_combinado":   match["score_combinado"],
            "score_descricao":          match["score_descricao"],
            "score_tipo":               match["score_tipo"],
            "score_condicao":           match["score_condicao"],
        })

    n_encontradas = sum(1 for r in regras_avaliadas if r["encontrada_na_referencia"])
    n_nao_encontradas = n_extraidas - n_encontradas
    percentual_confiabilidade = round(n_encontradas / n_extraidas * 100) if n_extraidas else 0

    return {
        "arquivo": data.get("arquivo"),
        "id_arquivo": data.get("id_arquivo"),
        "modelo": data.get("modelo"),
        "tokens_extracao": tokens_extracao,
        "status": "avaliado",
        "percentual_confiabilidade": percentual_confiabilidade,
        "contagem": {
            "regras_extraidas":             n_extraidas,
            "regras_na_referencia":         n_referencia,
            "encontradas_na_referencia":    n_encontradas,
            "nao_encontradas_na_referencia": n_nao_encontradas,
            "threshold_match":              MATCH_THRESHOLD,
        },
        "referencia": {
            "nome_documento": ref["nome"],
        },
        "regras": regras_avaliadas,
    }


# ---------------------------------------------------------------------------
# Entry point programático (importável por run.py)
# ---------------------------------------------------------------------------

DEFAULT_SPREADSHEET = Path(__file__).parent.parent / "extracoes_manuais_validadas.xlsx"


def run_evaluation(results_dir: Path, spreadsheet_path: Path = DEFAULT_SPREADSHEET) -> Path | None:
    """
    Avalia os JSONs em results_dir contra a planilha e salva _avaliacao.json.
    Retorna o caminho do arquivo gerado, ou None se nada foi avaliado.
    """
    if not results_dir.is_dir():
        print(f"ERRO: pasta de resultados nao encontrada: {results_dir}")
        return None
    if not spreadsheet_path.exists():
        print(f"ERRO: planilha nao encontrada: {spreadsheet_path}")
        return None

    print(f"Avaliando resultados em: {results_dir}")
    print(f"Planilha de referencia: {spreadsheet_path}")
    spreadsheet_data = load_spreadsheet(spreadsheet_path)
    print(f"  {len(spreadsheet_data)} documentos com referencia.\n")

    json_files = sorted(f for f in results_dir.glob("*.json") if f.stem != "_avaliacao")

    if not json_files:
        print("Nenhum JSON encontrado na pasta de resultados.")
        return None

    resultados = []
    for json_path in json_files:
        result = evaluate_file(json_path, spreadsheet_data)
        if result is None:
            continue
        resultados.append(result)

        status = result["status"]
        if status == "sem_referencia":
            print(f"  SEM REF  {json_path.name}")
        else:
            c = result["contagem"]
            pct = round(c["encontradas_na_referencia"] / c["regras_extraidas"] * 100) if c["regras_extraidas"] else 0
            print(
                f"  OK  {json_path.name}  |  "
                f"extraidas={c['regras_extraidas']}  "
                f"ref={c['regras_na_referencia']}  "
                f"encontradas={c['encontradas_na_referencia']} ({pct}%)"
            )

    avaliados = [r for r in resultados if r["status"] == "avaliado"]
    total_extraidas = sum(r["contagem"]["regras_extraidas"] for r in avaliados)
    total_encontradas = sum(r["contagem"]["encontradas_na_referencia"] for r in avaliados)
    pct_total = round(total_encontradas / total_extraidas * 100) if total_extraidas else 0
    total_tokens = sum(r["tokens_extracao"] for r in avaliados if r.get("tokens_extracao") is not None)

    output = {
        "resumo": {
            "total_arquivos_avaliados": len(avaliados),
            "total_sem_referencia": len(resultados) - len(avaliados),
            "total_regras_extraidas": total_extraidas,
            "total_encontradas_na_referencia": total_encontradas,
            "percentual_confiabilidade": pct_total,
            "total_tokens_extracao": total_tokens,
            "threshold_match": MATCH_THRESHOLD,
        },
        "avaliacoes": resultados,
    }

    output_path = results_dir / "_avaliacao.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nResumo: {total_extraidas} regras extraidas, {total_encontradas} encontradas ({pct_total}% confiabilidade), {total_tokens} tokens gastos")
    print(f"Avaliacao salva em: {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# Entry point CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Avalia JSONs gerados pela pipeline contra a planilha de referencia.")
    parser.add_argument("--results", required=True, help="Pasta com os JSONs a avaliar")
    parser.add_argument(
        "--spreadsheet",
        default=str(DEFAULT_SPREADSHEET),
        help="Caminho para extracoes_manuais_validadas.xlsx",
    )
    args = parser.parse_args()
    run_evaluation(Path(args.results), Path(args.spreadsheet))


if __name__ == "__main__":
    main()
