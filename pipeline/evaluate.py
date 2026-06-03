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


def best_match_score(rule_desc: str, reference_text: str) -> float:
    """
    Divide o texto de referência em itens (por número/letra de lista ou por
    quebra de linha) e retorna o maior score de sobreposição de tokens.
    """
    # Divide em linhas e remove linhas vazias
    lines = [l.strip() for l in reference_text.splitlines() if l.strip()]
    if not lines:
        return 0.0
    return max(token_overlap(rule_desc, line) for line in lines)


# ---------------------------------------------------------------------------
# Leitura da planilha
# ---------------------------------------------------------------------------

def load_spreadsheet(path: Path) -> dict[str, dict]:
    """
    Retorna dict keyed por id_arquivo (string, ex: "1", "10", "43").
    Valor: {"nome": str, "extracoes": [str, ...]}
    """
    wb = openpyxl.load_workbook(path)
    ws = wb.active

    records: dict[str, dict] = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        if len(row) < 10:
            continue
        id_arq = row[0]
        nome   = row[1]
        ext1   = row[5]
        ext2   = row[7]
        ext3   = row[9] if len(row) > 9 else None
        if id_arq is None:
            continue

        # id pode vir como float (ex: 1.0) — normaliza para string sem zeros
        id_str = str(int(float(id_arq)))

        extracoes = [e for e in [ext1, ext2, ext3] if e and str(e).strip()]
        if not extracoes:
            continue

        records[id_str] = {
            "nome": str(nome) if nome else "",
            "extracoes": extracoes,
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

    # Conta regras de referência: usa a média do número de linhas não-vazias
    # entre as extrações disponíveis como proxy de "quantidade esperada"
    ref_counts = []
    for ext_text in ref["extracoes"]:
        linhas = [l.strip() for l in ext_text.splitlines() if l.strip()]
        ref_counts.append(len(linhas))
    n_referencia_media = round(sum(ref_counts) / len(ref_counts), 1)

    # Para cada regra extraída, calcula o melhor score contra cada extração manual
    regras_avaliadas = []
    for regra in regras_extraidas:
        desc = regra.get("descricao", "")
        scores_por_extrator = []
        for ext_text in ref["extracoes"]:
            score = best_match_score(desc, ext_text)
            scores_por_extrator.append(round(score, 3))

        melhor_score = max(scores_por_extrator)
        encontrada = melhor_score >= MATCH_THRESHOLD

        regras_avaliadas.append({
            "id": regra.get("id"),
            "descricao": desc,
            "tipo": regra.get("tipo"),
            "encontrada_na_referencia": encontrada,
            "melhor_score": melhor_score,
            "scores_por_extrator": scores_por_extrator,
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
            "regras_extraidas": n_extraidas,
            "referencia_media_linhas": n_referencia_media,
            "encontradas_na_referencia": n_encontradas,
            "nao_encontradas_na_referencia": n_nao_encontradas,
            "threshold_match": MATCH_THRESHOLD,
        },
        "referencia": {
            "nome_documento": ref["nome"],
            "n_extratores": len(ref["extracoes"]),
            "contagens_por_extrator": ref_counts,
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
                f"ref~{c['referencia_media_linhas']}  "
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
