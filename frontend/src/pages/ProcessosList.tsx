import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { ProcessoResumo } from "../api/client";

export default function ProcessosList() {
  const navigate = useNavigate();
  const [processos, setProcessos] = useState<ProcessoResumo[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    api.listarProcessos()
      .then(setProcessos)
      .catch((e) => setErro(e.message))
      .finally(() => setCarregando(false));
  }, []);

  return (
    <div style={styles.page}>
      <header style={styles.header}>
        <h1 style={styles.titulo}>Extrator de Regras IFBA</h1>
        <button style={styles.btnNovo} onClick={() => navigate("/novo")}>
          + Novo Processo
        </button>
      </header>

      <main style={styles.main}>
        {carregando && <p style={styles.info}>Carregando processos...</p>}
        {erro && <p style={styles.erro}>{erro}</p>}
        {!carregando && !erro && processos.length === 0 && (
          <p style={styles.info}>Nenhum processo encontrado. Crie um novo.</p>
        )}
        <div style={styles.lista}>
          {processos.map((p) => (
            <div key={p.id} style={styles.card}>
              <div style={styles.cardInfo}>
                <span style={styles.cardNome}>{p.arquivo}</span>
                <span style={styles.cardMeta}>
                  {p.modelo} &nbsp;·&nbsp; {p.total_regras} regras
                </span>
                <span style={styles.cardDir}>{p.run_dir}</span>
              </div>
              <button
                style={styles.btnAbrir}
                onClick={() => navigate(`/processo/${encodeURIComponent(p.id)}`)}
              >
                Abrir →
              </button>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { minHeight: "100vh", background: "#f5f5f5", fontFamily: "sans-serif" },
  header: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    padding: "20px 32px", background: "#1a237e", color: "#fff",
  },
  titulo: { margin: 0, fontSize: 22, fontWeight: 700 },
  btnNovo: {
    background: "#fff", color: "#1a237e", border: "none",
    borderRadius: 6, padding: "10px 20px", fontWeight: 700,
    fontSize: 14, cursor: "pointer",
  },
  main: { maxWidth: 860, margin: "40px auto", padding: "0 16px" },
  info: { textAlign: "center", color: "#666", fontSize: 15 },
  erro: { textAlign: "center", color: "#d32f2f", fontSize: 15 },
  lista: { display: "flex", flexDirection: "column", gap: 12 },
  card: {
    background: "#fff", borderRadius: 8, padding: "16px 20px",
    display: "flex", alignItems: "center", justifyContent: "space-between",
    boxShadow: "0 1px 3px rgba(0,0,0,.12)",
  },
  cardInfo: { display: "flex", flexDirection: "column", gap: 4 },
  cardNome: { fontWeight: 600, fontSize: 15, color: "#1a1a1a" },
  cardMeta: { fontSize: 13, color: "#555" },
  cardDir: { fontSize: 11, color: "#aaa" },
  btnAbrir: {
    background: "#1a237e", color: "#fff", border: "none",
    borderRadius: 6, padding: "8px 18px", cursor: "pointer",
    fontWeight: 600, fontSize: 13,
  },
};
