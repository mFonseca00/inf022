# Pipeline de Extração de Regras Institucionais

Pipeline em Python para extrair automaticamente regras de processos institucionais do IFBA a partir de documentos PDF, utilizando LLMs via [pydantic-ai](https://ai.pydantic.dev/).

---

## Como funciona

```
PDFs de entrada
     │
     ▼
[1] Extração de texto (pdfplumber)
     │
     ▼
[2] Envio ao LLM (pydantic-ai)
  ├── System prompt: pipeline/prompts/prompt_extracao_regras_v4.md
  ├── Exemplos few-shot: pares (texto do PDF + JSON esperado) montados a partir de
  │     pipeline/docs_for_prompt_examples/*.pdf  +  *.json
  └── User message: nome do arquivo + id + texto extraído do PDF atual
     │
     ▼
[3] Validação da saída (Pydantic)
     │
     ▼
JSONs de saída (um por PDF)
```

**Passo a passo detalhado:**

1. `run.py` varre a pasta de entrada em busca de arquivos `.pdf`, em ordem alfabética.
2. Para cada PDF, `pdfplumber` extrai o texto de todas as páginas e concatena em uma string.
3. O texto é enviado ao agente pydantic-ai junto com o nome do arquivo e o `id_arquivo` inferido pelo prefixo numérico do nome (ex: `10_SEI_edital.pdf` → `id_arquivo = "10"`).
4. O agente usa o conteúdo de `pipeline/prompts/prompt_extracao_regras_v4.md` como system prompt. A ele são concatenados os exemplos few-shot, montados dinamicamente pela pipeline: para cada arquivo em `docs_for_prompt_examples/`, o texto extraído do PDF é pareado com o JSON de extração validada (arquivo `.json` de mesmo nome), formando pares **texto do documento → extração esperada** lado a lado.
5. A `user_message` contém apenas o arquivo atual: nome do arquivo, `id_arquivo` e o texto extraído do PDF.
6. O LLM responde com um JSON estruturado. O pydantic-ai valida automaticamente essa resposta contra o schema `ResultadoExtracao` — se vier malformado, tenta corrigir antes de falhar.
7. O resultado validado é salvo como `<nome_do_arquivo>.json` na pasta de saída.

---

## Estrutura dos arquivos

```
pipeline/
├── models.py        # Schemas Pydantic: Regra e ResultadoExtracao
├── config.py        # Seleção de provider e modelo via variáveis de ambiente
├── extractor.py     # Agente pydantic-ai responsável pela extração
├── run.py           # Entry point com interface de linha de comando (CLI)
├── evaluate.py      # Avaliador: compara JSONs gerados com a planilha de referência
├── requirements.txt # Dependências Python
├── .env.example     # Modelo do arquivo de configuração
└── README.md        # Este arquivo

# Fora da pasta pipeline/:
pipeline/prompts/prompt_extracao_regras_v4.md   # System prompt utilizado pela pipeline
pipeline/docs_for_prompt_examples/               # Exemplos few-shot: um .pdf + um .json por exemplo
```

---

## Instalação

**Pré-requisitos:** Python 3.11+

Antes de rodar, crie a pasta `docs/` na raiz do repositório e coloque os PDFs que deseja processar:

```
inf022/
└── docs/        ← crie esta pasta e coloque os PDFs aqui
```

```bash
# Entre na pasta da pipeline
cd pipeline

# Crie e ative o ambiente virtual
python -m venv .venv

# Linux/macOS
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Instale as dependências
pip install -r requirements.txt

# Crie o arquivo de configuração a partir do exemplo
# Linux/macOS
cp .env.example .env

# Windows
copy .env.example .env
```

---

## Configuração do `.env`

O arquivo `.env` centraliza toda a configuração da pipeline — provider, modelo, parâmetros de execução e avaliação. Com ele preenchido, basta rodar `python run.py` sem nenhum argumento.

```env
# Provider ativo: google | anthropic | openai | ollama
PROVIDER=google
MODEL=gemini-flash-latest

# Chaves de API (preencha apenas a do provider escolhido)
GEMINI_API_KEY=
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# Apenas se PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434/v1

# Parâmetros de execução do LLM (opcionais — remova o comentário para ativar)
# TEMPERATURE=0.0    # 0.0 = determinístico | 1.0 = criativo (recomendado: 0.0 para extração)
# MAX_TOKENS=8192    # limite de tokens na resposta do modelo
# TIMEOUT=120        # timeout por requisição em segundos
# TOP_P=0.9          # nucleus sampling — não use junto com TEMPERATURE
# TOP_K=40           # limita amostragem aos K tokens mais prováveis

# Parâmetros de execução da pipeline (opcionais — remova o comentário para ativar)
# INPUT_DIR=../docs        # pasta com os PDFs de entrada (default: ../docs)
# OUTPUT_DIR=../results    # pasta base de saída (default: ../results)
# BATCH_SIZE=0             # documentos por lote (0 = individual, ≥2 = batch)
# EVALUATE=false           # avaliação automática ao final (true | false)

# Parâmetros de avaliação (opcionais — remova o comentário para ativar)
# MATCH_THRESHOLD=0.5      # score mínimo (0.0–1.0) para considerar uma regra como encontrada
```

**Prioridade:** argumentos de linha de comando sempre sobrepõem o `.env` — `--batch-size 5` no terminal ignora `BATCH_SIZE=3` do `.env`.

Se um parâmetro de LLM não estiver definido, o provider usa seu próprio default. Para extração estruturada, recomenda-se `TEMPERATURE=0.0` para resultados consistentes e reproduzíveis.

> **Atenção:** `TOP_P` e `TEMPERATURE` controlam a aleatoriedade por mecanismos diferentes — usar os dois ao mesmo tempo pode produzir comportamentos inesperados. Escolha um ou outro.

### Sobre o `MATCH_THRESHOLD`

Define o score mínimo para que uma regra extraída seja considerada equivalente a uma regra da planilha de referência. O score é calculado como:

```
score = 0.8 × Jaccard(descricao) + 0.1 × match_exato(tipo) + 0.1 × Jaccard(condicao)
```

O valor padrão é **0.5**. Com o peso de 80% na descrição, o score reflete principalmente a similaridade textual — um score ≥ 0.5 exige que a descrição tenha Jaccard de pelo menos 0.375, evitando matches por coincidência de tipo e condição.

---

## Providers suportados

### Google Gemini (padrão)

Opção recomendada para começar — possui nível gratuito generoso.

```env
PROVIDER=google
MODEL=gemini-2.0-flash
GEMINI_API_KEY=sua_chave_aqui
```

Obtenha sua chave em: [aistudio.google.com](https://aistudio.google.com/app/apikey)

Outros modelos disponíveis: `gemini-1.5-pro`, `gemini-2.0-flash-lite`

---

### Anthropic Claude

```env
PROVIDER=anthropic
MODEL=claude-3-5-haiku-latest
ANTHROPIC_API_KEY=sua_chave_aqui
```

Obtenha sua chave em: [console.anthropic.com](https://console.anthropic.com/)

Outros modelos disponíveis: `claude-3-5-sonnet-latest`, `claude-3-opus-latest`

---

### OpenAI GPT

```env
PROVIDER=openai
MODEL=gpt-4o-mini
OPENAI_API_KEY=sua_chave_aqui
```

Outros modelos disponíveis: `gpt-4o`, `gpt-4-turbo`

---

### Ollama (modelos locais via Docker)

Permite rodar modelos localmente sem custo e sem enviar dados para serviços externos. O projeto já inclui os arquivos Docker Compose na raiz do repositório.

**1. Suba o Ollama com Docker Compose:**

```bash
# CPU (padrão)
docker compose up -d

# GPU NVIDIA (override)
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

O serviço `ollama-setup` baixa automaticamente o modelo `qwen2.5:3b` na primeira execução.

> **Atenção:** `qwen2.5:14b` rodando apenas em CPU pode ser muito lento. Para uso com CPU, considere versões menores como `qwen2.5:3b` ou `llama3.2:3b` — troque o nome do modelo no `entrypoint` do serviço `ollama-setup` em `docker-compose.yml`.

**2. Configure o `.env`:**

```env
PROVIDER=ollama
MODEL=qwen2.5:3b
OLLAMA_BASE_URL=http://localhost:11434/v1
```

> **Nota:** O Ollama expõe uma API compatível com OpenAI, então não é necessária nenhuma chave de API — o campo é preenchido automaticamente com o valor `"ollama"` internamente.

---

## Como rodar

```bash
# Uso básico
python run.py --input ../docs --output ../results

# Sobrepondo provider e modelo direto na linha de comando
# (tem prioridade sobre o .env)
python run.py --input ../docs --output ../results --provider ollama --model llama3.2
python run.py --input ../docs --output ../results --provider google --model gemini-2.0-flash

# Com avaliação automática ao final (requer extracoes_manuais_validadas.xlsx)
python run.py --input ../docs --output ../results --evaluate

# Com processamento em lote (N documentos por chamada ao LLM)
python run.py --input ../docs --output ../results --batch-size 3 --evaluate
```

Os argumentos `--provider`, `--model`, `--evaluate` e `--batch-size` são opcionais. Se omitidos, a pipeline usa o que estiver definido no `.env`, não executa a avaliação e processa um documento por vez.

### Modo batch (`--batch-size`)

Por padrão, a pipeline envia um documento por chamada ao LLM. Com `--batch-size N`, ela agrupa os documentos em lotes de até N arquivos e processa cada lote em uma única chamada:

```
[system prompt — pago 1×]
  + exemplos few-shot

[user message — lote de N documentos]
  === DOCUMENTO: 01_... | ID: 01 ===
  <texto>
  === DOCUMENTO: 02_... | ID: 02 ===
  <texto>
  ...
```

O system prompt (que inclui os exemplos few-shot) é cobrado apenas uma vez por lote, em vez de uma vez por documento — reduzindo o consumo de tokens quando há muitos arquivos para processar.

**O que muda nos arquivos gerados:**

- O campo `tokens` fica `null` e é substituído por `tokens_media_lote` (média do total de tokens do lote dividido pelo número de arquivos)
- O campo `arquivos_no_lote` indica quantos documentos compuseram o lote
- A pasta de saída recebe o sufixo `_batch` (ex: `2026-06-09_11-46-44_gemini-flash-latest_batch`)
- Um arquivo `_lotes.json` é criado na pasta de saída, registrando para cada lote: arquivos processados, quantidade, total de tokens e média por arquivo

**Fallback automático:** se uma chamada em lote falhar (resposta malformada, timeout, output truncado), a pipeline reprocessa automaticamente cada documento do lote individualmente, garantindo que nenhum arquivo seja perdido.

**Recomendação:** lotes de 3 a 5 documentos equilibram bem a economia de tokens com o risco de falha. Lotes maiores podem estourar o limite de tokens de saída (`MAX_TOKENS`) se os documentos gerarem muitas regras.

### Avaliação em separado

O avaliador pode ser executado independentemente sobre qualquer pasta de resultados já existente:

```bash
python evaluate.py --results ../results/2025-06-01_14-32-05_gemini-2.0-flash

# Apontando para uma planilha em caminho diferente do padrão
python evaluate.py --results ../results/2025-06-01_14-32-05_gemini-2.0-flash --spreadsheet /outro/caminho/planilha.xlsx
```

O avaliador compara cada regra extraída com as extrações manuais da planilha e salva `_avaliacao.json` na mesma pasta com o percentual de confiabilidade por arquivo e o total de tokens gastos na extração. Não usa LLM — a comparação é puramente algorítmica, sem custo de API.

Cada execução cria automaticamente uma subpasta dentro de `--output` com o timestamp e o nome do modelo. Em modo batch, o sufixo `_batch` é adicionado ao nome da pasta:

```
results/
├── 2025-06-01_14-32-05_gemini-2.0-flash/          # modo individual
│   ├── 01_diploma.json
│   └── 10_edital.json
└── 2025-06-02_09-15-40_gemini-flash-latest_batch/ # modo batch
    ├── 01_diploma.json
    ├── 10_edital.json
    ├── _lotes.json
    └── _avaliacao.json
```

Durante a execução, a pipeline exibe o progresso no terminal:

```
# Modo individual
Encontrados 2 PDFs.
Resultados serao salvos em: ../results/2025-06-01_14-32-05_gemini-2.0-flash

Processando: 01_diploma.pdf
  OK 12 regras extraidas -> 01_diploma.json
Processando: 10_edital.pdf
  ERRO ao processar 10_edital.pdf: <mensagem de erro>

Concluido.

# Modo batch (--batch-size 3)
Encontrados 6 PDFs.
Resultados serao salvos em: ../results/2025-06-02_09-15-40_gemini-flash-latest_batch

Processando lote [1]: 01_diploma.pdf, 02_edital.pdf, 10_sei.pdf
  OK 8 regras extraidas -> 01_diploma.json
  OK 9 regras extraidas -> 02_edital.json
  OK 13 regras extraidas -> 10_sei.json
Processando lote [2]: 28_edital.pdf, 36_resolucao.pdf
  OK 22 regras extraidas -> 28_edital.json
  OK 11 regras extraidas -> 36_resolucao.json

Concluido.
```

Isso permite comparar facilmente os resultados entre modelos, modos de execução e execuções diferentes.

---

## Formato da saída

Cada PDF gera um arquivo `.json` com o seguinte formato:

**Modo individual** — `tokens` contém o custo real da chamada:

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
    }
  ]
}
```

**Modo batch** — `tokens` é `null`; `tokens_media_lote` e `arquivos_no_lote` indicam o custo médio e o tamanho do lote:

```json
{
  "arquivo": "10_SEI_4282227_Edital_18_2025.pdf",
  "id_arquivo": "10",
  "modelo": "gemini-flash-latest",
  "tokens": null,
  "tokens_media_lote": 16402,
  "arquivos_no_lote": 4,
  "prompt_utilizado": "prompt_extracao_regras_v4.md",
  "parametros_llm": { "..." },
  "regras": [ "..." ]
}
```

O arquivo `_lotes.json` (gerado apenas em modo batch) registra as estatísticas por lote:

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

**Tipos de regra possíveis:**

| Tipo | Descrição |
|------|-----------|
| `obrigatória` | Requisito que deve ser cumprido por todos, sem exceção |
| `opcional` | Item que pode ou não ser apresentado, a critério do candidato |
| `restritiva` | Condição que impede ou veda a participação |
| `condicional` | Requisito que só se aplica se uma determinada condição for verdadeira |

### Formato do `_avaliacao.json`

Gerado pelo `evaluate.py` dentro da mesma pasta dos JSONs individuais. Em execuções batch, inclui uma seção `lotes` entre o `resumo` e as `avaliacoes`:

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
      "modelo": "gemini-flash-latest",
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
          "descricao": "Ser servidor/a efetivo/a do IFBA...",
          "tipo": "obrigatória",
          "condicao": null,
          "encontrada_na_referencia": true,
          "melhor_score_combinado": 1.0,
          "score_descricao": 1.0,
          "score_tipo": 1.0,
          "score_condicao": 1.0
        }
      ],
      "fora_da_referencia": [
        {
          "id": "R14",
          "descricao": "Regra extraída que não tem correspondente na planilha...",
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
          "descricao": "Regra da planilha que o modelo não extraiu...",
          "tipo": "restritiva",
          "condicao": null,
          "melhor_score_combinado": 0.05
        }
      ]
    }
  ]
}
```

**Métricas calculadas:**

O avaliador computa três métricas complementares por documento e no resumo geral:

| Métrica | Fórmula | Pergunta respondida |
|---------|---------|---------------------|
| **Precisão** | `extraidas_com_match / total_extraidas` | Das regras que o modelo extraiu, quantas existem na referência? |
| **Revocação** | `gabarito_cobertas / total_no_gabarito` | Das regras da referência, quantas o modelo capturou? |
| **F1** | `2 × P × R / (P + R)` | Nota única que equilibra as duas métricas anteriores — penaliza tanto extrair regras erradas quanto deixar regras passar |

Precisão e revocação se comportam de forma oposta: um modelo que extrai poucas regras mas sempre certas tem precisão alta e revocação baixa; um modelo que extrai tudo que existe (e mais) tem revocação alta e precisão baixa. O F1 é a média harmônica entre as duas — sobe apenas quando ambas estão boas ao mesmo tempo. O nome vem da literatura de recuperação de informação (F-score com β=1, ou seja, peso igual para precisão e revocação).

**Campos de diagnóstico por arquivo:**

- `fora_da_referencia`: regras extraídas que **não** encontraram match na referência — indica o que o modelo inventou ou subdividiu em excesso
- `referencia_nao_coberta`: regras da planilha que **não** foram cobertas por nenhuma regra extraída — indica o que o modelo deixou passar
- `melhor_score_combinado`: score composto do melhor match encontrado (ver cálculo abaixo)
- `score_descricao`, `score_tipo`, `score_condicao`: sub-scores individuais para diagnóstico de casos borderline
- `threshold_match`: score mínimo para considerar um match válido — lido do `.env` via `MATCH_THRESHOLD` (padrão: `0.5`)

**Como funciona o cálculo (score composto):**

O avaliador não usa LLM — compara estruturalmente cada regra extraída com cada regra da planilha. Para cada par, calcula um **score composto** com pesos por campo:

| Campo | Peso | Método |
|-------|------|--------|
| `descricao` | 80% | Jaccard sobre tokens normalizados |
| `tipo` | 10% | Match exato após normalização (`obrigatória`, `restritiva`, etc.) |
| `condicao` | 10% | Jaccard se ambos preenchidos; 1.0 se ambos `null`; 0.0 se só um é `null` |

```
score_combinado = 0.8 × score_descricao + 0.1 × score_tipo + 0.1 × score_condicao
```

O maior `score_combinado` obtido contra qualquer regra de referência vira `melhor_score_combinado`. Se esse valor for ≥ `threshold_match`, a regra é marcada como encontrada (para precisão) ou coberta (para revocação).

> **Limitação:** o Jaccard não reconhece sinônimos nem paráfrases — `estar` e `estejam` são palavras distintas para o algoritmo. Os sub-scores no JSON permitem inspecionar esses casos borderline.

---

## Organização recomendada dos arquivos

```
inf022/
├── docs/                          # PDFs de entrada (criar manualmente)
├── results/                       # JSONs de saída (criado automaticamente)
├── pipeline/                      # Código da pipeline
│   ├── prompts/                   # Prompts usados pela pipeline
│   └── docs_for_prompt_examples/  # Exemplos few-shot: um .pdf + um .json por exemplo
├── docker-compose.yml             # Ollama via Docker (CPU — padrão)
├── docker-compose.gpu.yml         # Override para habilitar GPU NVIDIA
├── exemplos_extracao.xlsx         # Fonte das extrações validadas usadas nos exemplos
└── 00_Lista de Resolucoes.xlsx    # Lista de documentos a processar
```

---

## Adicionando um novo provider

Para suportar um novo provider, basta editar `config.py` e adicionar um novo bloco `elif`:

```python
elif provider == "novo_provider":
    from pydantic_ai.models.xxx import XxxModel
    return XxxModel(model_name)
```

Qualquer serviço com endpoint compatível com a API da OpenAI (como Grok, Together AI, etc.) pode ser adicionado usando `OpenAIModel` com um `base_url` customizado, da mesma forma que o Ollama.
