import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Swal from "sweetalert2";
import { api } from "../api/client";
import type { ProcessoResumo } from "../api/client";
import s from "./ProcessosList.module.css";

export default function ProcessosList() {
  const navigate = useNavigate();
  const [processos, setProcessos] = useState<ProcessoResumo[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    api.listarProcessos()
      .then(setProcessos)
      .catch((e: Error) => setErro(e.message))
      .finally(() => setCarregando(false));
  }, []);

  async function handleRenomear(p: ProcessoResumo) {
    const { value: novoNome } = await Swal.fire({
      title: "Renomear processo",
      input: "text",
      inputValue: p.arquivo,
      inputLabel: "Novo nome",
      showCancelButton: true,
      confirmButtonText: "Salvar",
      cancelButtonText: "Cancelar",
      confirmButtonColor: "#1a237e",
      inputValidator: (v) => (!v.trim() ? "O nome não pode ser vazio." : null),
    });
    if (!novoNome) return;
    try {
      const atualizado = await api.renomearProcesso(p.id, novoNome.trim());
      setProcessos((prev) =>
        prev.map((x) => (x.id === p.id ? { ...x, arquivo: atualizado.arquivo } : x))
      );
    } catch (e: unknown) {
      Swal.fire({ icon: "error", title: "Erro", text: (e as Error).message, confirmButtonColor: "#1a237e" });
    }
  }

  async function handleExcluir(p: ProcessoResumo) {
    const { isConfirmed } = await Swal.fire({
      title: "Excluir processo?",
      html: `O processo <strong>${p.arquivo}</strong> será removido permanentemente.`,
      icon: "warning",
      showCancelButton: true,
      confirmButtonText: "Excluir",
      cancelButtonText: "Cancelar",
      confirmButtonColor: "#b71c1c",
    });
    if (!isConfirmed) return;
    try {
      await api.excluirProcesso(p.id);
      setProcessos((prev) => prev.filter((x) => x.id !== p.id));
    } catch (e: unknown) {
      Swal.fire({ icon: "error", title: "Erro", text: (e as Error).message, confirmButtonColor: "#1a237e" });
    }
  }

  return (
    <div className={s.page}>
      <header className={s.header}>
        <div />
        <h1 className={s.titulo}>Extrator de Regras IFBA</h1>
        <div className={s.headerRight}>
          <button className={s.btnNovo} onClick={() => navigate("/novo")}>
            + Novo Processo
          </button>
        </div>
      </header>

      <main className={s.main}>
        {carregando && <p className={s.info}>Carregando processos...</p>}
        {erro && <p className={s.erro}>{erro}</p>}
        {!carregando && !erro && processos.length === 0 && (
          <p className={s.info}>Nenhum processo encontrado. Crie um novo.</p>
        )}
        <div className={s.lista}>
          {processos.map((p) => (
            <div key={p.id} className={s.card}>
              <div className={s.cardInfo}>
                <span className={s.cardNome}>{p.arquivo}</span>
                <span className={s.cardMeta}>
                  {p.modelo} &nbsp;·&nbsp; {p.total_regras} regras
                </span>
                <span className={s.cardDir}>{p.run_dir}</span>
              </div>
              <div className={s.cardAcoes}>
                <button className={s.btnEditar} onClick={() => handleRenomear(p)} title="Renomear">✎</button>
                <button className={s.btnExcluir} onClick={() => handleExcluir(p)} title="Excluir">✕</button>
                <button
                  className={s.btnAbrir}
                  onClick={() => navigate(`/processo/${encodeURIComponent(p.id)}`)}
                >
                  Abrir →
                </button>
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}