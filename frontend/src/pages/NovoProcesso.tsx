import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { Processo, Regra } from "../api/client";
import RegraCard from "../components/RegraCard";
import RegraModal from "../components/RegraModal";

type Fase = "upload" | "processando" | "editando";

export default function NovoProcesso() {
  const navigate = useNavigate();
  const { processoId } = useParams<{ processoId: string }>();

  const [fase, setFase] = useState<Fase>(processoId ? "editando" : "upload");
  const [processo, setProcesso] = useState<Processo | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  // Modal de edição/criação de regra
  const [modalAberto, setModalAberto] = useState(false);
  const [regraEditando, setRegraEditando] = useState<Regra | null>(null);

  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Carrega processo já existente (rota /processo/:processoId)
  useEffect(() => {
    if (!processoId) return;
    api.obterProcesso(decodeURIComponent(processoId))
      .then((p) => { setProcesso(p); setFase("editando"); })
      .catch((e) => setErro(e.message));
  }, [processoId]);

  // Polling do job após upload
  useEffect(() => {
    if (!jobId) return;
    pollingRef.current = setInterval(async () => {
      try {
        const job = await api.statusJob(jobId);
        if (job.status === "pronto" && job.processo_id) {
          clearInterval(pollingRef.current!);
          const p = await api.obterProcesso(job.processo_id);
          setProcesso(p);
          setFase("editando");
        } else if (job.status === "erro") {
          clearInterval(pollingRef.current!);
          setErro(job.erro ?? "Erro desconhecido na extração.");
          setFase("upload");
        }
      } catch {
        // ignora erros de rede durante polling
      }
    }, 2000);
    return () => clearInterval(pollingRef.current!);
  }, [jobId]);

  async function handleFile(file: File) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setErro("Apenas arquivos PDF são aceitos.");
      return;
    }
    setErro(null);
    setFase("processando");
    try {
      const { job_id } = await api.enviarPDF(file);
      setJobId(job_id);
    } catch (e: unknown) {
      setErro((e as Error).message);
      setFase("upload");
    }
  }

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, []);

  // Handlers de regras
  function abrirModalNova() { setRegraEditando(null); setModalAberto(true); }
  function abrirModalEditar(r: Regra) { setRegraEditando(r); setModalAberto(true); }

  async function handleSalvarRegra(dados: Omit<Regra, "id">) {
    if (!processo) return;
    try {
      if (regraEditando) {
        const atualizada = await api.atualizarRegra(processo.id, regraEditando.id, dados);
        setProcesso((p) => p && {
          ...p,
          regras: p.regras.map((r) => r.id === regraEditando.id ? atualizada : r),
        });
      } else {
        const nova = await api.adicionarRegra(processo.id, dados);
        setProcesso((p) => p && { ...p, regras: [...p.regras, nova] });
      }
      setModalAberto(false);
    } catch (e: unknown) {
      setErro((e as Error).message);
    }
  }

  async function handleRemoverRegra(regraId: string) {
    if (!processo) return;
    if (!confirm("Remover esta regra?")) return;
    try {
      await api.removerRegra(processo.id, regraId);
      setProcesso((p) => p && { ...p, regras: p.regras.filter((r) => r.id !== regraId) });
    } catch (e: unknown) {
      setErro((e as Error).message);
    }
  }

  return (
    <div style={styles.page}>
      <header style={styles.header}>
        <button style={styles.btnVoltar} onClick={() => navigate("/")}>← Voltar</button>
        <h1 style={styles.titulo}>
          {processo ? processo.arquivo : "Novo Processo"}
        </h1>
        <span />
      </header>

      {erro && <div style={styles.erroBar}>{erro}</div>}

      <main style={styles.main}>

        {/* FASE: upload */}
        {fase === "upload" && (
          <div
            style={{ ...styles.dropzone, ...(dragging ? styles.dropzoneDrag : {}) }}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
          >
            <p style={styles.dropTexto}>Arraste um PDF aqui</p>
            <p style={styles.dropOu}>ou</p>
            <label style={styles.btnUpload}>
              Selecionar arquivo
              <input
                type="file" accept=".pdf" hidden
                onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
              />
            </label>
          </div>
        )}

        {/* FASE: processando */}
        {fase === "processando" && (
          <div style={styles.processando}>
            <div style={styles.spinner} />
            <p style={styles.processandoTexto}>Extraindo regras com IA...</p>
            <p style={styles.processandoSub}>Isso pode levar alguns segundos.</p>
          </div>
        )}

        {/* FASE: editando */}
        {fase === "editando" && processo && (
          <>
            <div style={styles.barraRegras}>
              <span style={styles.totalRegras}>
                {processo.regras.length} {processo.regras.length === 1 ? "regra" : "regras"} extraídas
              </span>
              <button style={styles.btnAddRegra} onClick={abrirModalNova}>
                + Adicionar Regra
              </button>
            </div>

            <div style={styles.listaRegras}>
              {processo.regras.map((r, i) => (
                <RegraCard
                  key={r.id}
                  regra={r}
                  indice={i + 1}
                  onEditar={() => abrirModalEditar(r)}
                  onRemover={() => handleRemoverRegra(r.id)}
                />
              ))}
              {processo.regras.length === 0 && (
                <p style={styles.semRegras}>Nenhuma regra. Adicione manualmente.</p>
              )}
            </div>
          </>
        )}
      </main>

      {modalAberto && (
        <RegraModal
          regra={regraEditando}
          onSalvar={handleSalvarRegra}
          onFechar={() => setModalAberto(false)}
        />
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { minHeight: "100vh", background: "#f5f5f5", fontFamily: "sans-serif" },
  header: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    padding: "16px 32px", background: "#1a237e", color: "#fff",
  },
  titulo: { margin: 0, fontSize: 18, fontWeight: 700, maxWidth: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  btnVoltar: {
    background: "none", border: "1px solid rgba(255,255,255,.5)",
    color: "#fff", borderRadius: 6, padding: "7px 14px", cursor: "pointer", fontSize: 13,
  },
  erroBar: {
    background: "#ffebee", color: "#b71c1c", padding: "10px 32px",
    fontSize: 14, borderBottom: "1px solid #ef9a9a",
  },
  main: { maxWidth: 760, margin: "40px auto", padding: "0 16px" },

  // Upload
  dropzone: {
    background: "#fff", border: "2px dashed #bbb", borderRadius: 12,
    padding: "60px 40px", textAlign: "center", transition: "border-color .2s",
  },
  dropzoneDrag: { borderColor: "#1a237e", background: "#e8f0fe" },
  dropTexto: { fontSize: 18, color: "#555", margin: 0 },
  dropOu: { color: "#aaa", margin: "12px 0" },
  btnUpload: {
    display: "inline-block", background: "#1a237e", color: "#fff",
    borderRadius: 6, padding: "10px 24px", cursor: "pointer", fontWeight: 700, fontSize: 14,
  },

  // Processando
  processando: { textAlign: "center", padding: 60 },
  spinner: {
    width: 48, height: 48, border: "5px solid #e0e0e0",
    borderTop: "5px solid #1a237e", borderRadius: "50%",
    animation: "spin 1s linear infinite", margin: "0 auto 24px",
  },
  processandoTexto: { fontSize: 18, fontWeight: 600, color: "#1a237e", margin: 0 },
  processandoSub: { fontSize: 13, color: "#888", marginTop: 8 },

  // Edição
  barraRegras: {
    display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16,
  },
  totalRegras: { fontSize: 15, fontWeight: 600, color: "#333" },
  btnAddRegra: {
    background: "#1a237e", color: "#fff", border: "none",
    borderRadius: 6, padding: "9px 18px", cursor: "pointer", fontWeight: 700, fontSize: 13,
  },
  listaRegras: { display: "flex", flexDirection: "column", gap: 10 },
  semRegras: { textAlign: "center", color: "#888", fontSize: 14 },
};
