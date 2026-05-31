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
  ├── System prompt: pipeline/prompts/prompt_extracao_regras_v3.md
  ├── Contexto adicional: PDFs em pipeline/docs_for_prompt_examples/
  └── User message: nome do arquivo + texto extraído
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
4. O agente usa o conteúdo de `pipeline/prompts/prompt_extracao_regras_v3.md` como system prompt, lê automaticamente os PDFs de exemplo em `pipeline/docs_for_prompt_examples/` e acrescenta esse material como contexto extra antes do documento atual.
5. O LLM responde com um JSON estruturado. O pydantic-ai valida automaticamente essa resposta contra o schema `ResultadoExtracao` — se vier malformado, tenta corrigir antes de falhar.
6. O resultado validado é salvo como `<nome_do_arquivo>.json` na pasta de saída.

### Sobre os parâmetros da LLM no JSON

Os valores salvos em `parametros_llm` refletem os parâmetros que a pipeline conseguiu determinar localmente. Quando o usuário não especifica um parâmetro, o código consegue guardar o valor explícito informado ou `null`.

O `pydantic-ai` não expõe, de forma genérica, os valores padrão internos de cada modelo/provider no objeto `ModelSettings` nem no objeto do modelo. Na prática, isso significa que não dá para garantir automaticamente os defaults reais de todo modelo sem manter uma tabela própria por provider/modelo. Se você quiser, dá para adicionar essa tabela depois para preencher defaults conhecidos e deixar `null` só para o que for realmente desconhecido.

---

## Estrutura dos arquivos

```
pipeline/
├── models.py        # Schemas Pydantic: Regra e ResultadoExtracao
├── config.py        # Seleção de provider e modelo via variáveis de ambiente
├── extractor.py     # Agente pydantic-ai responsável pela extração
├── run.py           # Entry point com interface de linha de comando (CLI)
├── requirements.txt # Dependências Python
├── .env.example     # Modelo do arquivo de configuração
└── README.md        # Este arquivo

# Fora da pasta pipeline/:
pipeline/prompts/prompt_extracao_regras_v3.md   # System prompt utilizado pela pipeline
pipeline/docs_for_prompt_examples/               # PDFs usados como contexto adicional durante a execução
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

O arquivo `.env` controla qual provider e modelo serão utilizados, além das chaves de API.

```env
# Provider ativo: google | anthropic | openai | ollama
PROVIDER=google
MODEL=gemini-2.0-flash

# Chaves de API (preencha apenas a do provider escolhido)
GEMINI_API_KEY=
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# Apenas se PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434/v1

# Parâmetros de execução (opcionais — remova o comentário para ativar)
# TEMPERATURE=0.0    # 0.0 = determinístico | 1.0 = criativo
# MAX_TOKENS=8192    # limite de tokens na resposta
# TIMEOUT=120        # timeout por requisição em segundos
# TOP_P=0.9          # nucleus sampling — não use junto com TEMPERATURE
# TOP_K=40           # limita amostragem aos K tokens mais prováveis
```

Se um parâmetro não estiver definido no `.env`, o provider usa seu próprio default. Para tarefas de extração estruturada, recomenda-se `TEMPERATURE=0.0` para resultados mais consistentes e reproduzíveis.

> **Atenção:** `TOP_P` e `TEMPERATURE` controlam a aleatoriedade por mecanismos diferentes — usar os dois ao mesmo tempo pode produzir comportamentos inesperados. Escolha um ou outro.

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
```

Os argumentos `--provider` e `--model` são opcionais. Se omitidos, a pipeline usa o que estiver definido no `.env`.

Cada execução cria automaticamente uma subpasta dentro de `--output` com o timestamp e o nome do modelo, por exemplo:

```
results/
├── 2025-06-01_14-32-05_gemini-2.0-flash/
│   ├── 01_diploma.json
│   └── 10_edital.json
└── 2025-06-02_09-15-40_llama3.2/
    ├── 01_diploma.json
    └── 10_edital.json
```

Durante a execução, a pipeline exibe o progresso no terminal:

```
Encontrados 2 PDFs.
Resultados serao salvos em: ../results/2025-06-01_14-32-05_gemini-2.0-flash

Processando: 01_diploma.pdf
  OK 12 regras extraidas -> 01_diploma.json
Processando: 10_edital.pdf
  ERRO ao processar 10_edital.pdf: <mensagem de erro>

Concluido.
```

Isso permite comparar facilmente os resultados entre modelos e entre execuções diferentes.

---

## Formato da saída

Cada PDF gera um arquivo `.json` com o seguinte formato:

```json
{
  "arquivo": "10_SEI_4282227_Edital_18_2025.pdf",
  "id_arquivo": "10",
  "modelo": "gemini-2.0-flash",
  "tokens": 3842,
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
      "descricao": "Não estar em gozo de férias no momento da participação no evento.",
      "tipo": "restritiva",
      "condicao": null,
      "referencia": "Item 1.3.1"
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

---

## Organização recomendada dos arquivos

```
inf022/
├── docs/                          # PDFs de entrada (criar manualmente)
├── results/                       # JSONs de saída (criado automaticamente)
├── pipeline/                      # Código da pipeline
│   ├── prompts/                   # Prompts usados pela pipeline
│   └── docs_for_prompt_examples/  # PDFs usados como contexto adicional
├── docker-compose.yml             # Ollama via Docker (CPU — padrão)
├── docker-compose.gpu.yml         # Override para habilitar GPU NVIDIA
├── exemplos_extracao.xlsx         # Exemplos de extrações validadas
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

Qualquer serviço com endpoint compatível com a API da OpenAI (como Groq, Together AI, etc.) pode ser adicionado usando `OpenAIModel` com um `base_url` customizado, da mesma forma que o Ollama.
