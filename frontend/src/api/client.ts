const BASE_URL = "http://localhost:8000/api";

export type TipoRegra = "obrigatória" | "opcional" | "restritiva" | "condicional";

export interface Regra {
  id: string;
  descricao: string;
  tipo: TipoRegra;
  condicao: string | null;
  referencia: string | null;
}

export interface ProcessoResumo {
  id: string;
  arquivo: string;
  modelo: string;
  total_regras: number;
  run_dir: string;
}

export interface Processo extends ProcessoResumo {
  regras: Regra[];
  tokens: number | null;
  id_arquivo: string;
}

export interface JobStatus {
  status: "processando" | "pronto" | "erro";
  processo_id: string | null;
  erro: string | null;
}

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, options);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Erro na requisição");
  }
  return res.json();
}

export const api = {
  listarProcessos: () => req<ProcessoResumo[]>("/processos"),

  obterProcesso: (id: string) => req<Processo>(`/processos/${encodeURIComponent(id)}`),

  enviarPDF: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return req<{ job_id: string; status: string }>("/processos", {
      method: "POST",
      body: form,
    });
  },

  statusJob: (jobId: string) => req<JobStatus>(`/processos/jobs/${jobId}`),

  adicionarRegra: (processoId: string, regra: Omit<Regra, "id">) =>
    req<Regra>(`/processos/${encodeURIComponent(processoId)}/regras`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(regra),
    }),

  atualizarRegra: (processoId: string, regraId: string, dados: Partial<Omit<Regra, "id">>) =>
    req<Regra>(`/processos/${encodeURIComponent(processoId)}/regras/${regraId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(dados),
    }),

  removerRegra: (processoId: string, regraId: string) =>
    req<{ detail: string }>(`/processos/${encodeURIComponent(processoId)}/regras/${regraId}`, {
      method: "DELETE",
    }),

  renomearProcesso: (processoId: string, nome: string) =>
    req<{ id: string; arquivo: string }>(`/processos/${encodeURIComponent(processoId)}/nome`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nome }),
    }),

  excluirProcesso: (processoId: string) =>
    req<{ detail: string }>(`/processos/${encodeURIComponent(processoId)}`, {
      method: "DELETE",
    }),
};
