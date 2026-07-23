# Validação de Extrações — Definições e Cálculos

Este documento descreve em detalhe como o sistema valida as regras extraídas de documentos institucionais por um LLM. A lógica está implementada em [`pipeline/evaluate.py`](../pipeline/evaluate.py) e pode ser replicada em qualquer projeto com extração estruturada de campos de documentos.

---

## 1. Visão Geral do Fluxo

```
PDFs                     Gabarito (planilha XLSX)
  │                              │
  ▼                              ▼
Extração via LLM        Leitura e parsing
  │                              │
  ▼                              │
JSONs de resultado               │
  │                              │
  └──────────────┬───────────────┘
                 ▼
         Avaliação por documento
         (comparação regra a regra)
                 │
                 ▼
         Métricas por documento
         (Precisão, Revocação, F1)
                 │
                 ▼
         Métricas globais
         (micro-média sobre todos os documentos)
                 │
                 ▼
         _avaliacao.json
```

---

## 2. Estrutura dos Dados

### 2.1 Regra Extraída (saída do LLM)

Cada documento processado produz uma lista de regras. Cada regra tem os seguintes campos:

| Campo        | Tipo            | Descrição                                                    |
|--------------|-----------------|--------------------------------------------------------------|
| `id`         | string          | Identificador incremental (ex: `R01`, `R02`)                 |
| `descricao`  | string          | Texto descritivo da regra extraída                           |
| `tipo`       | string          | Categoria: `obrigatória`, `opcional`, `restritiva`, `condicional` |
| `condicao`   | string ou null  | Condição de aplicação (preenchido apenas quando `tipo = condicional`) |
| `referencia` | string ou null  | Artigo ou seção do documento de origem                       |

**Exemplo:**
```json
{
  "id": "R03",
  "descricao": "Estar regularmente matriculado no curso",
  "tipo": "obrigatória",
  "condicao": null,
  "referencia": "Art. 5º, inciso II"
}
```

### 2.2 Regra de Referência (gabarito)

O gabarito é uma planilha XLSX (`extracoes_manuais_validadas.xlsx`) com extrações feitas manualmente por humanos. Cada linha representa um documento. A coluna 5 (índice 4) contém um fragmento JSON com as regras validadas, no formato:

```
"regras": [{id, descricao, tipo, condicao, referencia}, ...]
```

Campos utilizados na comparação: `descricao`, `tipo`, `condicao`.

---

## 3. Normalização de Texto

Antes de qualquer comparação textual, ambos os textos (extraído e referência) passam pela função `normalize()`:

```
normalize(texto):
  1. Converter para minúsculas
  2. Aplicar decomposição Unicode NFKD
  3. Remover caracteres combinantes (acentos diacríticos)
  4. Substituir tudo que não é alfanumérico ou espaço por espaço
  5. Colapsar múltiplos espaços em um único
  6. Remover espaços nas extremidades
```

**Exemplos:**

| Entrada                              | Saída normalizada                    |
|--------------------------------------|--------------------------------------|
| `"Ser docente do quadro efetivo."`   | `"ser docente do quadro efetivo"`    |
| `"Art. 5º, inciso II"`               | `"art 5 inciso ii"`                  |
| `"Pré-requisito: matrícula ativa"`   | `"pre requisito matricula ativa"`    |

> **Objetivo:** Tornar a comparação robusta a variações de maiúsculas, acentuação e pontuação — sem alterar o conteúdo semântico.

---

## 4. Similaridade entre Tokens (Jaccard)

A função `token_overlap(a, b)` mede o grau de sobreposição vocabular entre dois textos normalizados usando o **índice de Jaccard**:

$$J(A, B) = \frac{|A \cap B|}{|A \cup B|}$$

Onde `A` e `B` são os conjuntos de tokens (palavras) dos textos normalizados.

**Exemplo:**

```
a = "ser regularmente matriculado no curso"
b = "estar regularmente matriculado no programa"

A = {ser, regularmente, matriculado, no, curso}
B = {estar, regularmente, matriculado, no, programa}

A ∩ B = {regularmente, matriculado, no}  → |A ∩ B| = 3
A ∪ B = {ser, estar, regularmente, matriculado, no, curso, programa}  → |A ∪ B| = 7

J(A, B) = 3 / 7 ≈ 0.429
```

**Casos especiais:**
- Se `A` ou `B` for vazio → resultado é `0.0`
- Strings idênticas → resultado é `1.0`

---

## 5. Score Composto por Par de Regras

A função `rule_similarity(extraida, referencia)` calcula um **score composto** entre uma regra extraída e uma regra do gabarito, combinando três dimensões:

### 5.1 Score por Dimensão

| Dimensão       | Cálculo                                                                                                                                         | Peso |
|----------------|-------------------------------------------------------------------------------------------------------------------------------------------------|------|
| `score_descricao` | Jaccard sobre tokens normalizados de `descricao`                                                                                           | 80%  |
| `score_tipo`      | Match exato após normalização: `1.0` se iguais, `0.0` se diferentes                                                                       | 10%  |
| `score_condicao`  | Se ambos `null` → `1.0`; se apenas um é `null` → `0.0`; caso contrário, Jaccard sobre tokens normalizados de `condicao`                   | 10%  |

### 5.2 Fórmula do Score Combinado

$$\text{score\_combinado} = 0.8 \times \text{score\_descricao} + 0.1 \times \text{score\_tipo} + 0.1 \times \text{score\_condicao}$$

**Exemplo completo:**

```
Extraída:
  descricao = "Ter sido aprovado em programa de pós-graduação"
  tipo      = "obrigatória"
  condicao  = null

Referência:
  descricao = "Ser aprovado em programa de pós-graduação reconhecido pela CAPES"
  tipo      = "obrigatória"
  condicao  = null

→ score_descricao = Jaccard({ter, sido, aprovado, em, programa, de, pos, graduacao},
                             {ser, aprovado, em, programa, de, pos, graduacao, reconhecido, pela, capes})
                  = 5 / 10 = 0.500

→ score_tipo      = normalize("obrigatória") == normalize("obrigatória")  → 1.0

→ score_condicao  = ambos null → 1.0

→ score_combinado = 0.8 × 0.500 + 0.1 × 1.0 + 0.1 × 1.0
                  = 0.400 + 0.100 + 0.100
                  = 0.600
```

---

## 6. Melhor Match (Best Match)

A função `best_rule_match(regra_alvo, lista_candidatas)` calcula o score composto entre `regra_alvo` e **cada** regra em `lista_candidatas`, retornando o resultado de maior `score_combinado`:

```
best_match = max([rule_similarity(regra_alvo, candidata)
                  for candidata in lista_candidatas],
                 key=lambda s: s["score_combinado"])
```

Se `lista_candidatas` estiver vazia, retorna todos os scores como `0.0`.

> **Importante:** Não há restrição de uso exclusivo — a mesma regra do gabarito pode ser o melhor match de múltiplas regras extraídas, e vice-versa. Cada regra é avaliada independentemente.

---

## 7. Threshold de Match

Um par de regras é considerado **correspondente** quando:

$$\text{score\_combinado} \geq \text{MATCH\_THRESHOLD}$$

O valor padrão é `MATCH_THRESHOLD = 0.8`, configurável via variável de ambiente:

```env
MATCH_THRESHOLD=0.8
```

Esse limiar é o único parâmetro que define se uma regra foi "encontrada" ou não. Valores menores aumentam a permissividade (mais matches aceitos); valores maiores exigem maior similaridade textual.

---

## 8. Métricas por Documento

### 8.1 Precisão

Mede a fração das regras **extraídas** que têm correspondência no gabarito.

**Cálculo:**
```
Para cada regra extraída:
  Calcula best_rule_match(regra, gabarito["regras"])
  Se score_combinado >= MATCH_THRESHOLD → "encontrada"

precisao = n_encontradas / n_extraidas
```

$$\text{Precisão} = \frac{\text{regras extraídas com match no gabarito}}{\text{total de regras extraídas}}$$

> Alta precisão significa que o LLM extraiu poucas regras falsas (não inventou).

### 8.2 Revocação

Mede a fração das regras do **gabarito** que foram capturadas pela extração.

**Cálculo:**
```
Para cada regra de referência (gabarito):
  Calcula best_rule_match(regra_ref, regras_extraidas)
  Se score_combinado >= MATCH_THRESHOLD → "coberta"

revocacao = n_cobertas / n_referencia
```

$$\text{Revocação} = \frac{\text{regras do gabarito cobertas pela extração}}{\text{total de regras no gabarito}}$$

> Alta revocação significa que o LLM não perdeu regras importantes.

### 8.3 F1-Score

Média harmônica entre precisão e revocação. Penaliza fortemente quando um dos dois é baixo.

$$F_1 = 2 \times \frac{\text{Precisão} \times \text{Revocação}}{\text{Precisão} + \text{Revocação}}$$

Se `Precisão + Revocação = 0`, então `F1 = 0`.

---

## 9. Métricas Globais (Micro-Média)

As métricas globais são calculadas somando os contadores brutos de **todos os documentos avaliados** e então computando as métricas uma única vez — não tirando a média das métricas individuais (isso seria macro-média).

```
total_extraidas   = Σ n_extraidas    (por documento)
total_referencia  = Σ n_referencia   (por documento)
total_encontradas = Σ n_encontradas  (por documento)
total_cobertas    = Σ n_cobertas     (por documento)

precisao_geral  = total_encontradas / total_extraidas
revocacao_geral = total_cobertas    / total_referencia
f1_geral        = 2 × P × R / (P + R)
```

> **Micro-média vs macro-média:** A micro-média dá mais peso a documentos com mais regras. Um documento com 30 regras influencia mais o resultado global do que um com 3.

---

## 10. Contagens e Tipos de Erro

O resultado de cada documento contém a seção `contagem` com os seguintes campos:

| Campo                  | Significado                                                    |
|------------------------|----------------------------------------------------------------|
| `total_extraidas`      | Quantas regras o LLM extraiu                                  |
| `total_no_gabarito`    | Quantas regras o gabarito tem para esse documento             |
| `extraidas_com_match`  | Regras extraídas que encontraram correspondência no gabarito  |
| `extraidas_sem_match`  | Regras extraídas sem correspondência (falsos positivos)       |
| `gabarito_cobertas`    | Regras do gabarito que foram encontradas pela extração        |
| `gabarito_perdidas`    | Regras do gabarito que a extração não capturou (falsos negativos) |

**Relação com as métricas:**

```
Precisão  = extraidas_com_match  / total_extraidas
Revocação = gabarito_cobertas    / total_no_gabarito
```

---

## 11. Estrutura do JSON de Saída

O arquivo `_avaliacao.json` gerado tem a seguinte estrutura:

```json
{
  "resumo": {
    "total_arquivos_avaliados": 4,
    "total_sem_referencia": 0,
    "total_extraidas": 58,
    "total_no_gabarito": 39,
    "extraidas_com_match": 18,
    "gabarito_cobertas": 25,
    "gabarito_perdidas": 14,
    "precisao": 0.31,
    "revocacao": 0.641,
    "f1": 0.418,
    "total_tokens_extracao": 86036,
    "threshold_match": 0.5
  },
  "avaliacoes": [
    {
      "arquivo": "nome_do_arquivo.pdf",
      "id_arquivo": "23",
      "modelo": "gemini-flash-latest",
      "status": "avaliado",
      "metricas": {
        "precisao": 0.308,
        "revocacao": 1.0,
        "f1": 0.471,
        "threshold_match": 0.5
      },
      "contagem": { ... },
      "regras": [
        {
          "id": "R01",
          "descricao": "...",
          "tipo": "obrigatória",
          "condicao": null,
          "encontrada_na_referencia": false,
          "melhor_score_combinado": 0.242,
          "score_descricao": 0.053,
          "score_tipo": 1.0,
          "score_condicao": 1.0
        }
      ],
      "fora_da_referencia": [...],
      "referencia_nao_coberta": [...]
    }
  ]
}
```

**Campos de diagnóstico:**
- `regras`: lista completa das regras extraídas com seus scores individuais
- `fora_da_referencia`: subconjunto de `regras` onde `encontrada_na_referencia = false` (falsos positivos)
- `referencia_nao_coberta`: regras do gabarito que não foram capturadas (falsos negativos)

---

## 12. Casos Especiais

### Documento sem referência no gabarito

Se o `id_arquivo` do JSON extraído não for encontrado na planilha:
```json
{
  "status": "sem_referencia",
  "mensagem": "id_arquivo '99' não encontrado na planilha."
}
```
Esse documento é contado em `total_sem_referencia` e **não** entra nas métricas globais.

### Extração vazia

Se `n_extraidas = 0`, então `precisao = 0.0` (divisão por zero evitada).  
Se `n_referencia = 0`, então `revocacao = 0.0`.  
Se `precisao + revocacao = 0`, então `f1 = 0.0`.

---

## 13. Replicação em Outro Projeto

Para adaptar este sistema de validação a outro contexto de extração de dados de documentos, os únicos pontos que precisam ser ajustados são:

### 13.1 Redefinir os campos da entidade extraída

Substitua `Regra` (com campos `descricao`, `tipo`, `condicao`) pelos campos do seu domínio. Por exemplo, para extração de cláusulas contratuais:

```python
class Clausula(BaseModel):
    id: str
    texto: str          # equivalente a "descricao"
    categoria: str      # equivalente a "tipo"
    restricao: str | None  # equivalente a "condicao"
```

### 13.2 Redefinir a função `rule_similarity()`

Mapeie os campos do seu domínio para as três dimensões de score e ajuste os pesos conforme a importância relativa de cada campo:

```python
def clausula_similarity(extraida, referencia):
    texto_score = token_overlap(extraida["texto"], referencia["texto"])
    categoria_score = 1.0 if normalize(extraida["categoria"]) == normalize(referencia["categoria"]) else 0.0
    # ... campo condicional conforme seu domínio

    # Ajuste os pesos: devem somar 1.0
    combined = 0.7 * texto_score + 0.2 * categoria_score + 0.1 * restricao_score
    return combined
```

### 13.3 Definir o gabarito

O gabarito pode ser qualquer fonte estruturada — planilha XLSX, CSV, banco de dados, JSONs anotados manualmente. O requisito é ter, por documento, uma lista de entidades esperadas com os mesmos campos utilizados na comparação.

### 13.4 Definir o threshold

Escolha o `MATCH_THRESHOLD` adequado ao seu domínio. Regras de negócio:
- **Threshold alto (0.8–1.0):** exige textos muito similares; adequado quando as descrições são padronizadas
- **Threshold médio (0.5–0.7):** mais tolerante a paráfrases; adequado quando textos variam bastante em forma mas não em conteúdo
- **Threshold baixo (< 0.5):** permissivo; use apenas para análise exploratória

### 13.5 O restante permanece igual

As funções `normalize()`, `token_overlap()`, `best_rule_match()`, e o cálculo de Precisão / Revocação / F1 são agnósticos ao domínio e podem ser usados sem modificação.

---

## 14. Limitações Conhecidas

| Limitação | Impacto |
|-----------|---------|
| Jaccard é sensível ao tamanho dos textos — textos muito curtos ou muito longos têm scores distorcidos | Regras de um único token podem ter Jaccard alto mesmo sendo semanticamente diferentes |
| Não há penalidade por match duplo — a mesma regra do gabarito pode ser o melhor match de várias regras extraídas | A revocação não descobre que uma regra foi capturada "múltiplas vezes" |
| A comparação é léxica, não semântica | Sinônimos ou paráfrases com vocabulário diferente geram score baixo mesmo sendo equivalentes |
| O threshold único se aplica a todos os campos — um campo com texto muito curto (ex: `tipo`) pode dominar o score se tiver peso alto | Considere usar thresholds por campo para domínios com campos heterogêneos |
