# Pipeline de Extração de Regras Institucionais — IFBA

Pipeline em Python que lê documentos PDF do IFBA (editais, resoluções, documentos orientadores) e extrai automaticamente as **regras** que candidatos ou servidores precisam cumprir para participar de um processo institucional. A extração é feita por um LLM via [pydantic-ai](https://ai.pydantic.dev/), com suporte a Google Gemini, Anthropic Claude, OpenAI GPT e modelos locais via Ollama.

O projeto inclui também uma **interface web** — backend FastAPI + frontend React — que permite carregar PDFs, acompanhar a extração em tempo real e editar as regras extraídas.

---

## Índice

1. [Visão geral](#1-visão-geral)
2. [Como funciona — passo a passo](#2-como-funciona--passo-a-passo)
3. [Estrutura do projeto](#3-estrutura-do-projeto)
4. [Pré-requisitos](#4-pré-requisitos)
5. [Configuração do `.env`](#5-configuração-do-env)
6. [Como rodar — Interface Web](#6-como-rodar--interface-web)
7. [Como rodar — CLI (pipeline direta)](#7-como-rodar--cli-pipeline-direta)
8. [Providers suportados](#8-providers-suportados)
9. [Modo batch](#9-modo-batch)
10. [Formato da saída](#10-formato-da-saída)
11. [Avaliação automática](#11-avaliação-automática)
12. [Modelos locais com Ollama (Docker)](#12-modelos-locais-com-ollama-docker)
13. [Como os exemplos few-shot funcionam](#13-como-os-exemplos-few-shot-funcionam)
14. [Adicionando um novo provider](#14-adicionando-um-novo-provider)

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

**System prompt** — conteúdo de `pipeline/prompts/prompt_extracao_regras_v4.md` concatenado com os **exemplos few-shot** (ver seção 13). O system prompt instrui o LLM sobre o formato de saída esperado; os exemplos ensinam o padrão por demonstração.

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
├── pipeline/                          # Código da pipeline de extração
│   ├── config.py                      # Inicializa o modelo LLM pelo provider
│   ├── models.py                      # Schemas Pydantic (Regra, ResultadoExtracao, etc.)
│   ├── extractor.py                   # Agente pydantic-ai: extração individual e batch
│   ├── run.py                         # Entry point CLI — orquestra todo o fluxo
│   ├── evaluate.py                    # Avaliador: compara JSONs vs. planilha de referência
│   ├── requirements.txt               # Dependências Python da pipeline
│   ├── .env.example                   # Template de configuração
│   ├── .env                           # Configuração local (não versionar!)
│   │
│   ├── prompts/
│   │   └── prompt_extracao_regras_v4.md   # System prompt ATIVO
│   │
│   └── docs_for_prompt_examples/      # Exemplos few-shot (pares PDF + JSON validado)
│
├── backend/                           # API REST (FastAPI)
│   ├── main.py                        # App FastAPI + CORS
│   ├── requirements.txt               # Dependências Python do backend
│   ├── routers/
│   │   └── processos.py               # Todos os endpoints da API
│   └── services/
│       ├── storage_service.py         # Leitura/escrita dos JSONs em results/
│       └── pipeline_service.py        # Integração com a pipeline (roda extração em background)
│
├── frontend/                          # Interface web (React + TypeScript)
│   ├── src/
│   │   ├── api/client.ts              # Tipos e chamadas à API
│   │   ├── pages/
│   │   │   ├── ProcessosList.tsx      # Tela 1: lista de processos
│   │   │   └── NovoProcesso.tsx       # Tela 2: upload + extração + edição
│   │   └── components/
│   │       ├── RegraCard.tsx          # Card individual de regra
│   │       └── RegraModal.tsx         # Modal de criação/edição de regra
│   └── package.json
│
├── docker-compose.yml                 # Ollama via Docker (CPU)
├── docker-compose.gpu.yml             # Override: habilita GPU NVIDIA
├── exemplos_extracao.xlsx             # Fonte das extrações validadas nos exemplos
├── extracoes_manuais_validadas.xlsx   # Referência para avaliação (gabarito)
└── 00_Lista de Resolucoes.xlsx        # Índice de documentos a processar
```

---

## 4. Pré-requisitos

**Para a interface web (backend + frontend):**
- Python 3.11 ou superior
- Node.js 18 ou superior
- Uma chave de API do provider escolhido (Google Gemini recomendado — tem nível gratuito)

**Para a CLI (pipeline direta):**
- Python 3.11 ou superior
- Uma chave de API

---

## 5. Configuração do `.env`

Existe **apenas um arquivo `.env`**, localizado em `pipeline/.env`. Tanto a pipeline CLI quanto o backend FastAPI leem esse mesmo arquivo — o backend descobre o caminho automaticamente.

```bash
# Copie o template
cp pipeline/.env.example pipeline/.env
# Windows:
copy pipeline\.env.example pipeline\.env
```

Edite `pipeline/.env`:

```env
# ── Provider e modelo ─────────────────────────────────────────────────────────
PROVIDER=google
MODEL=gemini-flash-latest

# ── Chaves de API ─────────────────────────────────────────────────────────────
# Preencha apenas a chave do provider escolhido
GEMINI_API_KEY=sua_chave_aqui
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# Apenas se PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434/v1

# ── Parâmetros do LLM (opcionais) ─────────────────────────────────────────────
TEMPERATURE=0.0    # 0.0 = determinístico | 1.0 = máxima criatividade

# ── Parâmetros da pipeline CLI (usados apenas pelo run.py) ────────────────────
INPUT_DIR=../docs
OUTPUT_DIR=../results
BATCH_SIZE=4
EVALUATE=true
MATCH_THRESHOLD=0.5
```

Obtenha sua chave Gemini (gratuita) em: [aistudio.google.com](https://aistudio.google.com/app/apikey)

---

## 6. Como rodar — Interface Web

A interface web é composta por dois servidores que rodam em paralelo: o backend FastAPI (porta 8000) e o frontend React (porta 5173).

### Passo 1 — Configurar o `.env`

Siga a seção 5. Sem o `.env` preenchido o backend não consegue chamar o LLM.

### Passo 2 — Subir o backend

```bash
cd backend

# Na primeira vez: crie o ambiente virtual e instale as dependências
python -m venv .venv

# Ative o ambiente virtual
# Linux / macOS:
source .venv/bin/activate
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Windows (CMD):
.venv\Scripts\activate.bat

pip install -r requirements.txt

# Suba o servidor (mantenha este terminal aberto)
uvicorn main:app --reload --port 8000
```

O backend ficará disponível em `http://localhost:8000`.
A documentação interativa dos endpoints estará em `http://localhost:8000/docs`.

### Passo 3 — Subir o frontend

Em um **segundo terminal**:

```bash
cd frontend

# Na primeira vez: instale as dependências
npm install

# Suba o servidor de desenvolvimento (mantenha este terminal aberto)
npm run dev
```

O frontend abrirá em `http://localhost:5173`.

### Fluxo de uso

1. Acesse `http://localhost:5173`
2. Clique em **+ Novo Processo**
3. Arraste um PDF ou clique em **Selecionar arquivo**
4. Aguarde a extração (10–30s dependendo do tamanho do documento e do modelo)
5. Edite, remova ou adicione regras conforme necessário
6. Volte à tela inicial para ver todos os processos — é possível renomear ou excluir processos pela lista

---

## 7. Como rodar — CLI (pipeline direta)

Use a CLI quando quiser processar um lote de PDFs de uma vez sem passar pela interface web.

```bash
cd pipeline

# Na primeira vez: crie o ambiente virtual e instale as dependências
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# ou .venv\Scripts\activate.bat  (Windows CMD)

pip install -r requirements.txt

# Coloque os PDFs em docs/ (na raiz do projeto)
mkdir ../docs
# copie seus PDFs para ../docs/

# Uso básico — lê tudo do .env
python run.py

# Sobrepondo entrada, saída, provider e modelo
python run.py --input ../docs --output ../results --provider google --model gemini-flash-latest

# Com processamento em lote e avaliação
python run.py --batch-size 4 --evaluate
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

---

## 8. Providers suportados

### Google Gemini (recomendado)

Possui nível gratuito generoso — ideal para começar.

```env
PROVIDER=google
MODEL=gemini-flash-latest
GEMINI_API_KEY=sua_chave_aqui
```

Outros modelos: `gemini-2.0-flash`, `gemini-2.0-flash-lite`, `gemini-1.5-pro`

---

### Anthropic Claude

```env
PROVIDER=anthropic
MODEL=claude-3-5-haiku-latest
ANTHROPIC_API_KEY=sua_chave_aqui
```

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

Permite rodar sem custo de API e sem enviar dados para serviços externos. Ver seção [12 — Ollama via Docker](#12-modelos-locais-com-ollama-docker).

```env
PROVIDER=ollama
MODEL=qwen2.5:3b
OLLAMA_BASE_URL=http://localhost:11434/v1
```

---

## 9. Modo batch

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

### Fallback automático

Se uma chamada em lote falhar, a pipeline detecta o erro e **reprocessa cada documento do lote individualmente**, garantindo que nenhum arquivo seja perdido.

**Recomendação:** lotes de **3 a 5 documentos** equilibram bem economia de tokens e risco de falha.

---

## 10. Formato da saída

### JSON individual (`<nome_do_arquivo>.json`)

```json
{
  "arquivo": "10_SEI_4282227_Edital_18_2025.pdf",
  "id_arquivo": "10",
  "modelo": "gemini-flash-latest",
  "tokens": 39878,
  "prompt_utilizado": "prompt_extracao_regras_v4.md",
  "parametros_llm": {
    "provider": "google",
    "model": "gemini-flash-latest",
    "temperature": 0.0
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
      "id": "R03",
      "descricao": "Apresentar declaração de vínculo emitida pela DGRH.",
      "tipo": "condicional",
      "condicao": "Apenas para servidores cedidos ou em exercício provisório.",
      "referencia": "Item 1.4"
    }
  ]
}
```

### Tipos de regra

| Tipo | Descrição |
|------|-----------|
| `obrigatória` | Requisito que todos devem cumprir, sem exceção |
| `opcional` | Item que pode ou não ser apresentado |
| `restritiva` | Condição que veda a participação |
| `condicional` | Requisito que só se aplica sob uma condição |

---

## 11. Avaliação automática

O avaliador (`evaluate.py`) compara os JSONs gerados com a planilha `extracoes_manuais_validadas.xlsx` (gabarito). A comparação é **puramente algorítmica** — sem custo de API.

```bash
# Junto com a pipeline
python run.py --evaluate

# Em separado, sobre uma pasta já existente
python evaluate.py --results ../results/2026-06-09_14-32-05_gemini-flash-latest
```

### Como o score é calculado

Cada par de regras (extraída vs. referência) recebe um score composto:

```
score = 0.8 × Jaccard(descricao) + 0.1 × match_exato(tipo) + 0.1 × Jaccard(condicao)
```

O Jaccard mede a sobreposição de tokens entre dois textos normalizados (minúsculas, sem acentos, sem pontuação). Se o score ≥ `MATCH_THRESHOLD`, a regra é considerada encontrada.

As métricas finais são **Precisão**, **Revocação** e **F1** — calculadas somando os contadores brutos de todos os arquivos (média ponderada pelo volume, não média simples).

---

## 12. Modelos locais com Ollama (Docker)

```bash
# CPU
docker compose up -d

# GPU NVIDIA
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

Configure o `.env`:

```env
PROVIDER=ollama
MODEL=qwen2.5:3b
OLLAMA_BASE_URL=http://localhost:11434/v1
```

> Para uso com CPU, prefira `qwen2.5:3b` ou `llama3.2:3b`. Modelos maiores podem ser muito lentos sem GPU.

---

## 13. Como os exemplos few-shot funcionam

O arquivo `pipeline/prompts/prompt_extracao_regras_v4.md` é propositalmente enxuto (≈3KB). O "ensino" do padrão de extração acontece via **exemplos few-shot** montados dinamicamente por `build_examples_context()` em `extractor.py`.

Para cada par de arquivos em `pipeline/docs_for_prompt_examples/`, o texto do PDF e o JSON validado manualmente são concatenados no system prompt como um par **entrada → saída esperada**. O system prompt resultante (base + 4 exemplos) fica com ≈10–20KB.

| Exemplo | Tipo de documento |
|---------|------------------|
| `01_diploma` | Documento orientador |
| `02_edital_2024` | Edital de estágio |
| `10_SEI_edital_2025` | Edital de diárias |
| `28_edital_2025` | Edital de estágio (volume maior) |

---

## 14. Adicionando um novo provider

Qualquer serviço com endpoint compatível com a API da OpenAI pode ser adicionado em `config.py` usando `OpenAIModel` com um `base_url` customizado:

```python
# pipeline/config.py — adicione um novo bloco elif
elif provider == "novo_provider":
    from pydantic_ai.models.xxx import XxxModel
    return XxxModel(model_name)
```

Exemplos compatíveis: **Groq**, **Together AI**, **Mistral**, **LM Studio**.
