import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Swal from "sweetalert2";
import { api } from "../api/client";
import type { Processo, Regra } from "../api/client";
import RegraCard from "../components/RegraCard";
import RegraModal from "../components/RegraModal";
import s from "./NovoProcesso.module.css";

type Fase = "upload" | "processando" | "editando";

export default function NovoProcesso() {
  const navigate = useNavigate();
  const { processoId } = useParams<{ processoId: string }>();

  const [fase, setFase] = useState<Fase>(processoId ? "editando" : "upload");
  const [processo, setProcesso] = useState<Processo | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  const [modalAberto, setModalAberto] = useState(false);
  const [regraEditando, setRegraEditando] = useState<Regra | null>(null);

  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!processoId) return;
    api.obterProcesso(decodeURIComponent(processoId))
      .then((p) => { setProcesso(p); setFase("editando"); })
      .catch((e: Error) => setErro(e.message));
  }, [processoId]);

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
      } catch { /* ignora erros de rede durante polling */ }
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

  function abrirModalNova() { setRegraEditando(null); setModalAberto(true); }

  function abrirModalEditar(r: Regra) {
    setRegraEditando(r);
    setModalAberto(true);
  }

  async function handleSalvarRegra(dados: Omit<Regra, "id">) {
    if (!processo) return;
    if (regraEditando) {
      const { isConfirmed } = await Swal.fire({
        title: "Salvar alterações?",
        text: "Confirma a edição desta regra?",
        icon: "question",
        showCancelButton: true,
        confirmButtonText: "Salvar",
        cancelButtonText: "Cancelar",
        confirmButtonColor: "#1a237e",
      });
      if (!isConfirmed) return;
    }
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
      Swal.fire({ icon: "error", title: "Erro", text: (e as Error).message, confirmButtonColor: "#1a237e" });
    }
  }

  async function handleRemoverRegra(regraId: string) {
    if (!processo) return;
    const { isConfirmed } = await Swal.fire({
      title: "Remover regra?",
      text: "Esta ação não pode ser desfeita.",
      icon: "warning",
      showCancelButton: true,
      confirmButtonText: "Remover",
      cancelButtonText: "Cancelar",
      confirmButtonColor: "#b71c1c",
    });
    if (!isConfirmed) return;
    try {
      await api.removerRegra(processo.id, regraId);
      setProcesso((p) => p && { ...p, regras: p.regras.filter((r) => r.id !== regraId) });
    } catch (e: unknown) {
      Swal.fire({ icon: "error", title: "Erro", text: (e as Error).message, confirmButtonColor: "#1a237e" });
    }
  }

  return (
    <div className={s.page}>
      <header className={s.header}>
        <div className={s.headerLeft}>
          <button className={s.btnVoltar} onClick={() => navigate("/")}>← Voltar</button>
        </div>
        <h1 className={s.titulo}>
          {processo ? processo.arquivo : "Novo Processo"}
        </h1>
        <div className={s.headerRight} />
      </header>

      {erro && <div className={s.erroBar}>{erro}</div>}

      <main className={s.main}>

        {fase === "upload" && (
          <div
            className={`${s.dropzone} ${dragging ? s.dropzoneDrag : ""}`}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
          >
            <p className={s.dropTexto}>Arraste um PDF aqui</p>
            <p className={s.dropOu}>ou</p>
            <label className={s.btnUpload}>
              Selecionar arquivo
              <input
                type="file" accept=".pdf" hidden
                onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
              />
            </label>
          </div>
        )}

        {fase === "processando" && (
          <div className={s.processando}>
            <div className={s.spinner} />
            <p className={s.processandoTexto}>Extraindo regras com IA...</p>
            <p className={s.processandoSub}>Isso pode levar alguns segundos.</p>
          </div>
        )}

        {fase === "editando" && processo && (
          <>
            <div className={s.barraRegras}>
              <span className={s.totalRegras}>
                {processo.regras.length} {processo.regras.length === 1 ? "regra" : "regras"} extraídas
              </span>
              <button className={s.btnAddRegra} onClick={abrirModalNova}>
                + Adicionar Regra
              </button>
            </div>

            <div className={s.listaRegras}>
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
                <p className={s.semRegras}>Nenhuma regra. Adicione manualmente.</p>
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