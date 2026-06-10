# Pipeline de Extração de Regras Institucionais — IFBA

Pipeline em Python que lê documentos PDF do IFBA (editais, resoluções, documentos orientadores) e extrai automaticamente as **regras** que candidatos ou servidores precisam cumprir para participar de um processo institucional. A extração é feita por um LLM via [pydantic-ai](https://ai.pydantic.dev/), com suporte a Google Gemini, Anthropic Claude, OpenAI GPT e modelos locais via Ollama.

---

## Índice

1. [Visão geral](#1-visão-geral)
2. [Como funciona — passo a passo](#2-como-funciona--passo-a-passo)
3. [Estrutura do projeto](#3-estrutura-do-projeto)
4. [Pré-requisitos e instalação](#4-pré-requisitos-e-instalação)
5. [Configuração do `.env`](#5-configuração-do-env)
6. [Providers suportados](#6-providers-suportados)
7. [Como rodar](#7-como-rodar)
8. [Modo batch](#8-modo-batch)
9. [Formato da saída](#9-formato-da-saída)
10. [Avaliação automática](#10-avaliação-automática)
11. [Modelos locais com Ollama (Docker)](#11-modelos-locais-com-ollama-docker)
12. [Como os exemplos few-shot funcionam](#12-como-os-exemplos-few-shot-funcionam)
13. [Adicionando um novo provider](#13-adicionando-um-novo-provider)

---

## 1. Visão geral

O IFBA publica dezenas de documentos — editais de estágio, resoluções de afastamento, orientadores de emissão de diploma — cada um com regras específicas que candidatos ou servidores precisam atender. Ler, interpretar e catalogar essas regras manualmente é lento e propenso a erros.

Este projeto automatiza essa leitura. Dado um conjunto de PDFs, a pipeline:

1. Extrai o texto de cada documento com **pdfplumber**
2. Envia o texto ao LLM com um **system prompt especializado** + **exemplos few-shot** de extrações validadas
3. Recebe de volta um JSON estruturado com as regras identificadas, validado automaticamente com **Pydantic**
4. Opcionalmente, **avalia** a qualidade da extração comparando com uma planilha de referência preenchida manualmente

```
PDFs de entrada  →  Extração de texto  →  LLM + Exemplos  →  JSONs estruturados
                                                    ↓
                                      (opcional) Avaliação vs. planilha
                                                    ↓
                                         _avaliacao.json (P / R / F1)
```

---

## 2. Como funciona — passo a passo

### Etapa 1 — Varredura dos PDFs

`run.py` varre a pasta de entrada (padrão: `docs/`) em busca de arquivos `.pdf`, ordenados alfabeticamente. Cada arquivo recebe um `id_arquivo` inferido automaticamente do prefixo numérico do nome:

```
01_diploma.pdf           → id_arquivo = "01"
10_SEI_edital.pdf        → id_arquivo = "10"
28_Edital_N_13.2025.pdf  → id_arquivo = "28"
sem_numero.pdf           → id_arquivo = "00"  (fallback)
```

### Etapa 2 — Extração de texto

Para cada PDF, `pdfplumber` abre o arquivo, extrai o texto de todas as páginas e concatena em uma única string. Nenhum pré-processamento adicional é aplicado — o texto bruto vai direto para o LLM.

### Etapa 3 — Montagem do prompt

O agente pydantic-ai usa dois componentes:

**System prompt** — conteúdo de `pipeline/prompts/prompt_extracao_regras_v4.md` concatenado com os **exemplos few-shot** (ver seção 12). O system prompt instrui o LLM sobre o formato de saída esperado; os exemplos ensinam o padrão por demonstração.

**User message** — a mensagem enviada para cada documento contém apenas três informações:
```
Arquivo: 01_diploma.pdf
ID: 01

<texto extraído do PDF>
```

### Etapa 4 — Chamada ao LLM e validação

O pydantic-ai chama o modelo e valida a resposta automaticamente contra o schema `ResultadoExtracao`. Se o JSON vier malformado, o framework tenta corrigir antes de lançar erro. O schema garante que campos obrigatórios estejam presentes e que os tipos de dado sejam corretos.

### Etapa 5 — Salvamento do resultado

O resultado validado é serializado como JSON e salvo em `results/<timestamp>_<modelo>/` com o mesmo nome do PDF de origem:

```
results/
└── 2026-06-09_14-32-05_gemini-2.0-flash/
    ├── 01_diploma.json
    ├── 02_edital.json
    └── 10_sei.json
```

### Etapa 6 — Avaliação (opcional)

Se `--evaluate` ou `EVALUATE=true`, o `evaluate.py` compara cada JSON gerado com a planilha `extracoes_manuais_validadas.xlsx`. A comparação é puramente algorítmica (sem custo de API) e gera métricas de **precisão**, **revocação** e **F1** por arquivo e no total.

---

## 3. Estrutura do projeto

```
inf022/
│
├── docs/                              # PDFs de entrada (criar manualmente)
├── results/                           # JSONs de saída (criado automaticamente)
│
├── pipeline/                          # Código da pipeline
│   ├── config.py                      # Inicializa o modelo LLM pelo provider
│   ├── models.py                      # Schemas Pydantic (Regra, ResultadoExtracao, etc.)
│   ├── extractor.py                   # Agente pydantic-ai: extração individual e batch
│   ├── run.py                         # Entry point CLI — orquestra todo o fluxo
│   ├── evaluate.py                    # Avaliador: compara JSONs vs. planilha de referência
│   ├── requirements.txt               # Dependências Python
│   ├── .env.example                   # Template de configuração
│   ├── .env                           # Configuração local (não versionar!)
│   │
│   ├── prompts/
│   │   ├── prompt_extracao_regras_v1.md   # Versões anteriores (obsoletas)
│   │   ├── prompt_extracao_regras_v2.md
│   │   ├── prompt_extracao_regras_v3.md
│   │   └── prompt_extracao_regras_v4.md   # System prompt ATIVO
│   │
│   └── docs_for_prompt_examples/      # Exemplos few-shot (pares PDF + JSON validado)
│       ├── 01_documento_orientador_...pdf
│       ├── 01_documento_orientador_...json
│       ├── 02_Edital_...pdf
│       ├── 02_Edital_...json
│       ├── 10_SEI_...pdf
│       ├── 10_SEI_...json
│       ├── 28_Edital_...pdf
│       └── 28_Edital_...json
│
├── docker-compose.yml                 # Ollama via Docker (CPU)
├── docker-compose.gpu.yml             # Override: habilita GPU NVIDIA
├── exemplos_extracao.xlsx             # Fonte das extrações validadas nos exemplos
├── extracoes_manuais_validadas.xlsx   # Referência para avaliação (gabarito)
└── 00_Lista de Resolucoes.xlsx        # Índice de documentos a processar
```

### Responsabilidade de cada módulo

| Arquivo | Responsabilidade |
|---------|-----------------|
| `config.py` | Lê `PROVIDER` e `MODEL` do `.env` e retorna a instância correta do modelo pydantic-ai (Gemini, Claude, GPT ou Ollama). Também lê e expõe os parâmetros de LLM (temperature, max_tokens, etc.) |
| `models.py` | Define os schemas Pydantic: `ParametrosLLM`, `Regra`, `ResultadoExtracao` (saída individual) e `ResultadoLote` (saída batch) |
| `extractor.py` | Cria o agente pydantic-ai com o system prompt + exemplos few-shot. Expõe `extract()` (um documento) e `extract_batch()` (múltiplos documentos em uma única chamada) |
| `run.py` | Lê argumentos da CLI, inicializa o modelo, varre os PDFs, chama `extract()` ou `extract_batch()`, salva os JSONs e opcionalmente chama o avaliador |
| `evaluate.py` | Lê os JSONs gerados e a planilha de referência, calcula scores de similaridade para cada par de regras e gera `_avaliacao.json` com precisão/revocação/F1 |

---

## 4. Pré-requisitos e instalação

**Requisitos:**
- Python 3.11 ou superior
- Uma chave de API (Google Gemini recomendado para começar — possui nível gratuito generoso)
- PDFs para processar na pasta `docs/`

```bash
# 1. Entre na pasta da pipeline
cd pipeline

# 2. Crie o ambiente virtual
python -m venv .venv

# 3. Ative o ambiente virtual
# Linux / macOS
source .venv/bin/activate
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# Windows (CMD)
.venv\Scripts\activate.bat

# 4. Instale as dependências
pip install -r requirements.txt

# 5. Crie o arquivo de configuração
# Linux / macOS
cp .env.example .env
# Windows
copy .env.example .env

# 6. Crie a pasta de entrada e coloque os PDFs
mkdir ../docs
# Copie seus PDFs para ../docs/
```

---

## 5. Configuração do `.env`

O `.env` centraliza toda a configuração. Com ele preenchido, `python run.py` funciona sem nenhum argumento adicional.

```env
# ── Provider e modelo ─────────────────────────────────────────────────────────
# Provider ativo: google | anthropic | openai | ollama
PROVIDER=google
MODEL=gemini-2.0-flash

# ── Chaves de API ─────────────────────────────────────────────────────────────
# Preencha apenas a chave do provider escolhido
GEMINI_API_KEY=
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# Apenas se PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434/v1

# ── Parâmetros do LLM (opcionais) ─────────────────────────────────────────────
# Descomente para ativar. Se omitido, o provider usa seu próprio default.
# TEMPERATURE=0.0    # 0.0 = determinístico | 1.0 = máxima criatividade
#                    # Recomendado: 0.0 para extração estruturada
# MAX_TOKENS=8192    # Limite de tokens na resposta do modelo
# TIMEOUT=120        # Timeout por requisição (segundos)
# TOP_P=0.9          # Nucleus sampling — não use junto com TEMPERATURE
# TOP_K=40           # Limita a amostragem aos K tokens mais prováveis

# ── Parâmetros da pipeline (opcionais) ────────────────────────────────────────
# INPUT_DIR=../docs        # Pasta com os PDFs de entrada (default: ../docs)
# OUTPUT_DIR=../results    # Pasta base de saída (default: ../results)
# BATCH_SIZE=0             # Documentos por lote (0 = individual, ≥2 = batch)
# EVALUATE=false           # Executar avaliação ao final (true | false)

# ── Parâmetros de avaliação (opcionais) ───────────────────────────────────────
# MATCH_THRESHOLD=0.75     # Score mínimo (0.0–1.0) para considerar match válido
```

**Prioridade de configuração:** argumentos de linha de comando sempre sobrepõem o `.env`. `--batch-size 5` no terminal ignora `BATCH_SIZE=3` do `.env`.

### Por que `TEMPERATURE=0.0`?

Para extração estruturada, resultados determinísticos são essenciais. Com `TEMPERATURE=0.0`, executar a pipeline duas vezes sobre o mesmo documento gera o mesmo JSON — importante para comparações e para depurar o prompt. Valores mais altos podem fazer o modelo inventar regras ou variar a descrição.

> **Atenção:** `TOP_P` e `TEMPERATURE` controlam a aleatoriedade por mecanismos diferentes — usar os dois ao mesmo tempo produz comportamentos imprevisíveis. Escolha um ou outro.

### Sobre o `MATCH_THRESHOLD`

O score de comparação entre regras é calculado como:

```
score = 0.8 × Jaccard(descricao) + 0.1 × match_exato(tipo) + 0.1 × Jaccard(condicao)
```

O valor padrão é **0.5**. Com os pesos atuais (descrição com 80% do peso), o score reflete principalmente a similaridade textual — um score ≥ 0.5 exige que a descrição tenha Jaccard de pelo menos 0.375, evitando matches por coincidência de tipo e condição.

---

## 6. Providers suportados

### Google Gemini (recomendado)

Possui nível gratuito generoso — ideal para começar.

```env
PROVIDER=google
MODEL=gemini-2.0-flash
GEMINI_API_KEY=sua_chave_aqui
```

Obtenha sua chave em: [aistudio.google.com](https://aistudio.google.com/app/apikey)

Outros modelos: `gemini-2.0-flash-lite`, `gemini-1.5-pro`

---

### Anthropic Claude

```env
PROVIDER=anthropic
MODEL=claude-3-5-haiku-latest
ANTHROPIC_API_KEY=sua_chave_aqui
```

Obtenha sua chave em: [console.anthropic.com](https://console.anthropic.com/)

Outros modelos: `claude-3-5-sonnet-latest`, `claude-3-opus-latest`

---

### OpenAI GPT

```env
PROVIDER=openai
MODEL=gpt-4o-mini
OPENAI_API_KEY=sua_chave_aqui
```

Outros modelos: `gpt-4o`, `gpt-4-turbo`

---

### Ollama (modelos locais)

Permite rodar sem custo de API e sem enviar dados para serviços externos. Ver seção [11 — Ollama via Docker](#11-modelos-locais-com-ollama-docker).

```env
PROVIDER=ollama
MODEL=qwen2.5:3b
OLLAMA_BASE_URL=http://localhost:11434/v1
```

---

## 7. Como rodar

```bash
# Uso básico — lê tudo do .env
python run.py

# Sobrepondo entrada e saída
python run.py --input ../docs --output ../results

# Sobrepondo provider e modelo (prioridade sobre .env)
python run.py --provider google --model gemini-2.0-flash
python run.py --provider anthropic --model claude-3-5-haiku-latest
python run.py --provider ollama --model qwen2.5:3b

# Com avaliação automática ao final
python run.py --evaluate

# Com processamento em lote
python run.py --batch-size 4 --evaluate

# Tudo junto
python run.py --input ../docs --output ../results --provider google --model gemini-2.0-flash --batch-size 4 --evaluate
```

**Argumentos disponíveis:**

| Argumento | Equivalente no `.env` | Descrição |
|-----------|----------------------|-----------|
| `--input PATH` | `INPUT_DIR` | Pasta com os PDFs de entrada |
| `--output PATH` | `OUTPUT_DIR` | Pasta base de saída |
| `--provider NOME` | `PROVIDER` | Provider do LLM |
| `--model NOME` | `MODEL` | Nome do modelo |
| `--batch-size N` | `BATCH_SIZE` | Documentos por lote (0 = individual) |
| `--evaluate` | `EVALUATE=true` | Executar avaliação ao final |

### Saída no terminal

```
# Modo individual
Encontrados 4 PDFs.
Resultados serao salvos em: ../results/2026-06-09_14-32-05_gemini-2.0-flash

Processando: 01_diploma.pdf
  OK 8 regras extraidas -> 01_diploma.json
Processando: 02_edital.pdf
  OK 14 regras extraidas -> 02_edital.json
Processando: 10_sei.pdf
  OK 13 regras extraidas -> 10_sei.json
Processando: 28_edital.pdf
  ERRO ao processar 28_edital.pdf: <mensagem de erro>

Concluido.
```

---

## 8. Modo batch

Por padrão a pipeline envia um documento por chamada ao LLM. Com `--batch-size N`, ela agrupa os documentos em lotes de até N arquivos e processa cada lote em **uma única chamada**.

### Por que usar batch?

O system prompt — que inclui o prompt base e todos os exemplos few-shot — representa a maior parte do custo em tokens. No modo individual, ele é cobrado uma vez por documento. No modo batch, é cobrado **uma única vez por lote**:

```
Modo individual (4 docs):
  Doc 1: [system prompt 15KB] + [doc 1 texto]  = ~18K tokens
  Doc 2: [system prompt 15KB] + [doc 2 texto]  = ~18K tokens
  Doc 3: [system prompt 15KB] + [doc 3 texto]  = ~18K tokens
  Doc 4: [system prompt 15KB] + [doc 4 texto]  = ~18K tokens
  Total: ~72K tokens

Modo batch (4 docs, batch-size=4):
  Lote 1: [system prompt 15KB] + [doc 1] + [doc 2] + [doc 3] + [doc 4]  = ~27K tokens
  Total: ~27K tokens  (≈ 60% de economia)
```

### Estrutura da user message em batch

```
=== DOCUMENTO: 01_diploma.pdf | ID: 01 ===
<texto extraído do documento 1>

=== DOCUMENTO: 02_edital.pdf | ID: 02 ===
<texto extraído do documento 2>

=== DOCUMENTO: 10_sei.pdf | ID: 10 ===
<texto extraído do documento 3>
```

### Fallback automático

Se uma chamada em lote falhar (resposta malformada, timeout, output truncado), a pipeline detecta o erro e **reprocessa cada documento do lote individualmente**, garantindo que nenhum arquivo seja perdido. O arquivo `_lotes.json` registra o status de cada lote.

### O que muda nos arquivos gerados

- O campo `tokens` fica `null` (não é possível atribuir custo exato por documento em batch)
- `tokens_media_lote` registra a média: `tokens_total_lote ÷ quantidade_arquivos`
- `arquivos_no_lote` indica quantos documentos compuseram o lote
- A pasta de saída recebe o sufixo `_batch`
- Um arquivo `_lotes.json` é criado com o registro de cada lote

**Recomendação:** lotes de **3 a 5 documentos** equilibram bem economia de tokens e risco de falha. Lotes maiores podem estourar `MAX_TOKENS` se os documentos gerarem muitas regras.

### Saída no terminal (modo batch)

```
Encontrados 6 PDFs.
Resultados serao salvos em: ../results/2026-06-09_14-32-05_gemini-2.0-flash_batch

Processando lote [1]: 01_diploma.pdf, 02_edital.pdf, 10_sei.pdf
  OK 8 regras extraidas -> 01_diploma.json
  OK 14 regras extraidas -> 02_edital.json
  OK 13 regras extraidas -> 10_sei.json
Processando lote [2]: 28_edital.pdf, 36_resolucao.pdf
  OK 22 regras extraidas -> 28_edital.json
  OK 11 regras extraidas -> 36_resolucao.json

Concluido.
```

---

## 9. Formato da saída

### JSON individual (`<nome_do_arquivo>.json`)

Cada PDF gera um arquivo `.json` na pasta de resultados:

```json
{
  "arquivo": "10_SEI_4282227_Edital_18_2025.pdf",
  "id_arquivo": "10",
  "modelo": "gemini-2.0-flash",
  "tokens": 39878,
  "tokens_media_lote": null,
  "arquivos_no_lote": null,
  "prompt_utilizado": "prompt_extracao_regras_v4.md",
  "parametros_llm": {
    "provider": "google",
    "model": "gemini-2.0-flash",
    "temperature": 0.0,
    "max_tokens": 8192,
    "timeout": 120,
    "top_p": 0.9,
    "top_k": 40,
    "base_url": null
  },
  "regras": [
    {
      "id": "R01",
      "descricao": "Ser servidor/a efetivo/a do IFBA — Campus Salvador.",
      "tipo": "obrigatória",
      "condicao": null,
      "referencia": "Item 1.2"
    },
    {
      "id": "R02",
      "descricao": "Estar em efetivo exercício no campus no momento da inscrição.",
      "tipo": "obrigatória",
      "condicao": null,
      "referencia": "Item 1.3"
    },
    {
      "id": "R03",
      "descricao": "Apresentar declaração de vínculo emitida pela DGRH.",
      "tipo": "condicional",
      "condicao": "Apenas para servidores cedidos ou em exercício provisório.",
      "referencia": "Item 1.4"
    }
  ]
}
```

Em **modo batch**, `tokens` é `null` e os campos de lote são preenchidos:

```json
{
  "arquivo": "10_SEI_4282227_Edital_18_2025.pdf",
  "id_arquivo": "10",
  "modelo": "gemini-2.0-flash",
  "tokens": null,
  "tokens_media_lote": 16402,
  "arquivos_no_lote": 4,
  ...
}
```

### Tipos de regra

| Tipo | Descrição | Exemplo |
|------|-----------|---------|
| `obrigatória` | Requisito que todos devem cumprir, sem exceção | "Apresentar RG original" |
| `opcional` | Item que pode ou não ser apresentado | "Carta de recomendação (facultativa)" |
| `restritiva` | Condição que veda a participação | "Não pode ter vínculo com outra instituição" |
| `condicional` | Requisito que só se aplica sob uma condição | "Se servidor, apresentar portaria de lotação" |

### Arquivo `_lotes.json` (apenas em modo batch)

```json
{
  "lotes": [
    {
      "lote": 1,
      "arquivos": ["01_diploma.pdf", "02_edital.pdf", "10_sei.pdf"],
      "quantidade_arquivos": 3,
      "tokens_total_lote": 49206,
      "tokens_media_por_arquivo": 16402
    },
    {
      "lote": 2,
      "arquivos": ["28_edital.pdf", "36_resolucao.pdf"],
      "quantidade_arquivos": 2,
      "tokens_total_lote": 32804,
      "tokens_media_por_arquivo": 16402
    }
  ]
}
```

### Organização da pasta de saída

Cada execução cria uma subpasta com timestamp e nome do modelo. Em modo batch, o sufixo `_batch` é adicionado:

```
results/
├── 2026-06-09_14-32-05_gemini-2.0-flash/        # modo individual
│   ├── 01_diploma.json
│   ├── 02_edital.json
│   └── 10_sei.json
└── 2026-06-09_15-10-22_gemini-2.0-flash_batch/  # modo batch
    ├── 01_diploma.json
    ├── 02_edital.json
    ├── 10_sei.json
    ├── _lotes.json
    └── _avaliacao.json
```

Isso permite comparar facilmente resultados entre modelos, modos de execução e execuções diferentes.

---

## 10. Avaliação automática

O avaliador (`evaluate.py`) compara os JSONs gerados pela pipeline com as extrações da planilha `extracoes_manuais_validadas.xlsx`, feitas manualmente por humanos. Essa planilha é o **gabarito**: ela diz quais regras deveriam ter sido extraídas de cada documento. A comparação é **puramente algorítmica** — sem custo de API.

### Executar junto com a pipeline

```bash
python run.py --evaluate
# ou, via .env:
# EVALUATE=true
```

### Executar em separado sobre uma pasta já existente

```bash
python evaluate.py --results ../results/2026-06-09_14-32-05_gemini-2.0-flash

# Apontando para uma planilha em caminho diferente
python evaluate.py --results ../results/2026-06-09_... --spreadsheet /outro/caminho/planilha.xlsx
```

---

### Etapa 1 — Normalização do texto

Antes de qualquer comparação, o texto de cada campo (`descricao`, `tipo`, `condicao`) passa por uma função de normalização (`normalize()` em `evaluate.py`):

1. Converte para minúsculas
2. Remove acentos (decomposição Unicode NFKD + remoção de diacríticos)
3. Substitui pontuação por espaço
4. Colapsa múltiplos espaços em um único

```
"Ser servidor/a Efetivo/a do IFBA."
         ↓ minúsculas
"ser servidor/a efetivo/a do ifba."
         ↓ remove acentos
"ser servidor/a efetivo/a do ifba."
         ↓ remove pontuação
"ser servidor a efetivo a do ifba "
         ↓ colapsa espaços
"ser servidor a efetivo a do ifba"
```

O resultado é uma sequência de **tokens** (palavras) que podem ser comparados sem sensibilidade a maiúsculas, acentuação ou pontuação.

---

### Etapa 2 — Similaridade de Jaccard

O coeficiente de Jaccard mede o quanto dois conjuntos se sobrepõem. Para dois textos A e B:

```
Jaccard(A, B) = |tokens(A) ∩ tokens(B)|  ÷  |tokens(A) ∪ tokens(B)|
                  palavras em comum            todas as palavras distintas
```

O resultado é sempre entre 0.0 (nenhuma palavra em comum) e 1.0 (conjuntos idênticos).

**Exemplo passo a passo:**

```
Regra extraída:   "Ser servidor efetivo do IFBA Campus Salvador."
Regra referência: "Ser servidor efetivo do Campus Salvador."

Após normalização:
  A = {"ser", "servidor", "efetivo", "do", "ifba", "campus", "salvador"}
  B = {"ser", "servidor", "efetivo", "do", "campus", "salvador"}

Interseção  A ∩ B = {"ser", "servidor", "efetivo", "do", "campus", "salvador"}  →  6 tokens
União       A ∪ B = {"ser", "servidor", "efetivo", "do", "ifba", "campus", "salvador"}  →  7 tokens

Jaccard = 6 / 7 ≈ 0.857
```

Outro exemplo, textos mais diferentes:

```
Extraída:   "Apresentar comprovante de residência."
Referência: "Entregar comprovante de endereço atualizado."

A = {"apresentar", "comprovante", "de", "residencia"}
B = {"entregar", "comprovante", "de", "endereco", "atualizado"}

Interseção = {"comprovante", "de"}  →  2 tokens
União       = {"apresentar", "comprovante", "de", "residencia",
               "entregar", "endereco", "atualizado"}  →  7 tokens

Jaccard = 2 / 7 ≈ 0.286
```

> **Limitação importante:** o Jaccard trabalha com conjuntos de palavras exatas. Ele não reconhece sinônimos (`residência` ≠ `endereço`), variações morfológicas (`servidor` ≠ `servidores`) nem paráfrases. Dois textos com o mesmo sentido mas palavras distintas podem ter Jaccard baixo.

---

### Etapa 3 — Score composto por par de regras

O avaliador não compara apenas a `descricao`. Cada par de regras (extraída vs. referência) recebe um **score composto** que pondera três campos:

| Campo | Peso | Cálculo |
|-------|------|---------|
| `descricao` | 80% | Jaccard(descricao_extraida, descricao_referencia) |
| `tipo` | 10% | 1.0 se tipos iguais após normalização, 0.0 se diferentes |
| `condicao` | 10% | Jaccard se ambos preenchidos · 1.0 se ambos `null` · 0.0 se apenas um é `null` |

```
score_combinado = 0.8 × score_descricao + 0.1 × score_tipo + 0.1 × score_condicao
```

O peso maior na descrição garante que o score reflita principalmente a similaridade textual. Com os pesos anteriores (60/20/20), qualquer par onde ambas as regras fossem `obrigatória` e sem condição partia de um score mínimo de 0.40 — independente do texto. Com 80/10/10 esse piso cai para 0.20, eliminando matches espúrios.

**Exemplo completo:**

```
Extraída:   descricao="Ser servidor efetivo do IFBA Campus Salvador."
            tipo="obrigatória"
            condicao=null

Referência: descricao="Ser servidor efetivo do Campus Salvador."
            tipo="obrigatória"
            condicao=null

score_descricao = Jaccard(A, B) = 0.857   (calculado acima)
score_tipo      = 1.0   (ambos "obrigatoria" após normalização)
score_condicao  = 1.0   (ambos null)

score_combinado = 0.8 × 0.857 + 0.1 × 1.0 + 0.1 × 1.0
               = 0.686 + 0.100 + 0.100
               = 0.886
```

Para cada regra extraída, o avaliador calcula esse score contra **todas** as regras da referência e guarda apenas o maior — o `melhor_score_combinado`. Se esse valor for ≥ `MATCH_THRESHOLD`, a regra é considerada **encontrada** (para precisão) ou **coberta** (para revocação).

O avaliador nunca força um emparelhamento fixo entre regras. Cada regra extraída compete livremente contra todas as regras do gabarito — o melhor match vence, independente de posição ou ordem. O mesmo vale no sentido inverso: cada regra do gabarito busca seu melhor match entre todas as extraídas.

**Exemplo:** documento com 3 regras no gabarito

```
Regra extraída R07: "Apresentar comprovante de quitação eleitoral."

vs. Ref R01 "Ser servidor efetivo..."              → score 0.042
vs. Ref R02 "Apresentar RG e CPF..."               → score 0.231
vs. Ref R03 "Apresentar comprovante eleitoral."    → score 0.762   ← melhor

melhor_score_combinado de R07 = 0.762
```

Com `MATCH_THRESHOLD=0.5`: `0.762 ≥ 0.5` → R07 é marcada como `encontrada_na_referencia: true`.

---

### Etapa 4 — Precisão, Revocação e F1

Precisão e revocação respondem perguntas opostas sobre o mesmo conjunto de dados.

#### Precisão

> *Das regras que o modelo extraiu, quantas realmente existem no gabarito?*

O avaliador percorre cada regra extraída, busca o melhor match na referência e verifica se o score ≥ threshold:

```
Precisão = extraidas_com_match / total_extraidas
```

**Exemplo:** o modelo extraiu 15 regras. 12 matcharam na referência. 3 não têm correspondente (foram inventadas ou subdivididas demais).

```
Precisão = 12 / 15 = 0.800
```

Uma precisão baixa indica que o modelo está extraindo coisas que não estão no documento ou fragmentando uma regra em várias.

#### Revocação

> *Das regras que existem no gabarito, quantas o modelo capturou?*

O avaliador faz o caminho inverso: percorre cada regra da **referência**, busca o melhor match nas extraídas e verifica se o score ≥ threshold:

```
Revocação = gabarito_cobertas / total_no_gabarito
```

**Exemplo:** a referência tem 13 regras. Todas as 13 foram cobertas por alguma regra extraída.

```
Revocação = 13 / 13 = 1.000
```

Uma revocação baixa indica que o modelo deixou passar regras que existem no documento.

#### Por que as duas métricas são necessárias?

Elas medem falhas opostas e podem ser manipuladas em sentidos contrários:

| Comportamento do modelo | Precisão | Revocação |
|-------------------------|----------|-----------|
| Extrai poucas regras, mas sempre certas | Alta | Baixa |
| Extrai tudo que encontra (e mais) | Baixa | Alta |
| Extrai as regras certas na quantidade certa | Alta | Alta |

Um modelo que simplesmente copiasse o documento inteiro como uma única "regra" poderia ter revocação 1.0 — cobriria tudo — mas precisão próxima de zero. O inverso também é possível. Por isso, nenhuma das duas sozinha é suficiente.

#### F1

O F1 é a **média harmônica** entre precisão e revocação. Ao contrário da média aritmética, a média harmônica é puxada para baixo pelo menor dos dois valores — ela só sobe quando **ambas** estão altas ao mesmo tempo:

```
F1 = 2 × Precisão × Revocação / (Precisão + Revocação)
```

**Exemplo com os números acima:**

```
Precisão  = 0.800
Revocação = 1.000

F1 = 2 × 0.800 × 1.000 / (0.800 + 1.000)
   = 1.600 / 1.800
   ≈ 0.889
```

Se a precisão caísse para 0.5 com a mesma revocação, a média aritmética seria 0.75 — número que parece razoável. O F1 seria 0.667 — um número que reflete melhor o problema real.

#### Métricas globais (resumo entre todos os arquivos)

As métricas do `resumo` **não são a média das métricas por arquivo**. O avaliador soma os contadores brutos de todos os arquivos e recalcula do zero:

```
precisao_geral  = Σ(extraidas_com_match) / Σ(total_extraidas)
revocacao_geral = Σ(gabarito_cobertas)  / Σ(total_no_gabarito)
```

**Por quê?** Fazer média das métricas daria peso igual a documentos com 2 regras e documentos com 50 regras. Somar os contadores dá peso proporcional ao volume real de cada arquivo:

```
Arquivo A:  2 extraídas,   2 encontradas   →  P = 1.00
Arquivo B: 50 extraídas,  25 encontradas   →  P = 0.50

Média das precisões:   (1.00 + 0.50) / 2 = 0.750  ← peso igual, ignora tamanho
Soma dos contadores:   27 / 52           = 0.519  ← peso real, proporcional ao volume
```

---

### Formato do `_avaliacao.json`

```json
{
  "resumo": {
    "total_arquivos_avaliados": 4,
    "total_sem_referencia": 0,
    "total_extraidas": 70,
    "total_no_gabarito": 52,
    "extraidas_com_match": 66,
    "gabarito_cobertas": 52,
    "gabarito_perdidas": 0,
    "precisao": 0.943,
    "revocacao": 1.0,
    "f1": 0.971,
    "total_tokens_extracao": 168749,
    "threshold_match": 0.5
  },
  "avaliacoes": [
    {
      "arquivo": "10_SEI_4282227_Edital_18_2025.pdf",
      "id_arquivo": "10",
      "modelo": "gemini-2.0-flash",
      "tokens_extracao": 39878,
      "status": "avaliado",
      "metricas": {
        "precisao": 0.8,
        "revocacao": 1.0,
        "f1": 0.889,
        "threshold_match": 0.5
      },
      "contagem": {
        "total_extraidas": 15,
        "total_no_gabarito": 13,
        "extraidas_com_match": 12,
        "extraidas_sem_match": 3,
        "gabarito_cobertas": 13,
        "gabarito_perdidas": 0
      },
      "referencia": {
        "nome_documento": "EDITAL DE APOIO A CONCESSÃO DE DIÁRIAS E PASSAGENS"
      },
      "regras": [
        {
          "id": "R01",
          "descricao": "Ser servidor/a efetivo/a do IFBA — Campus Salvador.",
          "tipo": "obrigatória",
          "condicao": null,
          "encontrada_na_referencia": true,
          "melhor_score_combinado": 0.914,
          "score_descricao": 0.857,
          "score_tipo": 1.0,
          "score_condicao": 1.0
        }
      ],
      "fora_da_referencia": [
        {
          "id": "R14",
          "descricao": "Regra que o modelo extraiu mas não existe na referência",
          "tipo": "obrigatória",
          "condicao": null,
          "encontrada_na_referencia": false,
          "melhor_score_combinado": 0.08,
          "score_descricao": 0.04,
          "score_tipo": 1.0,
          "score_condicao": 1.0
        }
      ],
      "referencia_nao_coberta": [
        {
          "descricao": "Regra da planilha que o modelo não capturou",
          "tipo": "restritiva",
          "condicao": null,
          "melhor_score_combinado": 0.05
        }
      ]
    }
  ]
}
```

**Campos de diagnóstico:**

- `regras` — todas as regras extraídas com seus scores individuais; `encontrada_na_referencia: true` significa que o `melhor_score_combinado` atingiu o threshold
- `fora_da_referencia` — subconjunto de `regras` onde `encontrada_na_referencia: false`; indica o que o modelo inventou, duplicou ou subdividiu demais
- `referencia_nao_coberta` — regras do gabarito que não foram cobertas por nenhuma regra extraída; indica o que o modelo deixou passar
- `melhor_score_combinado` — score máximo obtido contra qualquer regra do gabarito; com os pesos 80/10/10, um score baixo aqui significa que os textos têm poucas palavras em comum
- `score_descricao`, `score_tipo`, `score_condicao` — sub-scores individuais para diagnóstico de casos borderline; se `score_descricao` é alto mas `score_tipo` é 0.0, o modelo extraiu o texto certo mas classificou o tipo errado

---

## 11. Modelos locais com Ollama (Docker)

O projeto inclui arquivos Docker Compose para subir o Ollama localmente — sem custo de API e sem enviar dados para serviços externos.

### CPU (padrão)

```bash
docker compose up -d
```

O serviço `ollama-setup` baixa automaticamente o modelo `qwen2.5:3b` na primeira execução.

### GPU NVIDIA

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

### Configure o `.env`

```env
PROVIDER=ollama
MODEL=qwen2.5:3b
OLLAMA_BASE_URL=http://localhost:11434/v1
```

O Ollama expõe uma API compatível com OpenAI. Nenhuma chave de API é necessária — o campo é preenchido internamente com o valor `"ollama"`.

> **Atenção:** modelos maiores (ex: `qwen2.5:14b`) rodando apenas em CPU podem ser muito lentos. Para uso com CPU, prefira `qwen2.5:3b` ou `llama3.2:3b`. Para trocar o modelo padrão baixado, edite o `entrypoint` do serviço `ollama-setup` em `docker-compose.yml`.

---

## 12. Como os exemplos few-shot funcionam

O arquivo `pipeline/prompts/prompt_extracao_regras_v4.md` é propositalmente enxuto (≈3KB). O "ensino" do padrão de extração acontece via **exemplos few-shot** montados dinamicamente pela função `build_examples_context()` em `extractor.py`.

### Processo de montagem

Para cada par de arquivos em `pipeline/docs_for_prompt_examples/`:

1. O texto do PDF de exemplo é extraído com pdfplumber
2. O JSON validado manualmente (mesmo nome, extensão `.json`) é carregado
3. Os dois são concatenados no system prompt como um par **entrada → saída esperada**:

```
=== EXEMPLO 1 ===
DOCUMENTO: 01_documento_orientador_...pdf

[texto extraído do PDF de exemplo]

EXTRAÇÃO ESPERADA:
{
  "arquivo": "01_documento_orientador_...",
  "regras": [
    { "id": "R01", "descricao": "...", "tipo": "obrigatória", ... }
  ]
}
```

4. O system prompt resultante (base + 4 exemplos) fica com ≈10–20KB

### Por que 4 exemplos?

Os exemplos foram escolhidos para cobrir diferentes tipos de documentos e padrões de regra presentes no corpus IFBA:

| Exemplo | Tipo de documento | Destaque |
|---------|------------------|----------|
| `01_diploma` | Documento orientador | Regras de apresentação de documentos |
| `02_edital_2024` | Edital de estágio | Regras condicionais por categoria de candidato |
| `10_SEI_edital_2025` | Edital de diárias | Regras restritivas e mistas |
| `28_edital_2025` | Edital de estágio | Volume maior de regras, regras opcionais |

### Versões do prompt

| Versão | Tamanho | Status | Característica |
|--------|---------|--------|---------------|
| v1 | 18KB | Obsoleta | Primeira versão, instruções extensas |
| v2 | 19KB | Obsoleta | Iteração com mais exemplos inline |
| v3 | 21KB | Obsoleta | Versão mais detalhada |
| v4 | 3.3KB | **Ativa** | Compacta — confia nos exemplos few-shot |

A v4 produziu melhor qualidade com menor custo de tokens ao eliminar redundâncias das versões anteriores e delegar o "ensino" do padrão inteiramente aos exemplos.

---

## 13. Adicionando um novo provider

Qualquer serviço com endpoint compatível com a API da OpenAI pode ser adicionado em `config.py` usando `OpenAIModel` com um `base_url` customizado — da mesma forma que o Ollama.

Para um provider com SDK próprio no pydantic-ai:

```python
# pipeline/config.py — adicione um novo bloco elif
elif provider == "novo_provider":
    from pydantic_ai.models.xxx import XxxModel
    return XxxModel(model_name)
```

Exemplos de providers compatíveis com OpenAI que podem ser adicionados assim: **Groq**, **Together AI**, **Mistral**, **LM Studio**.
