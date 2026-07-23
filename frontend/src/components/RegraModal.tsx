import { useEffect, useState } from "react";
import type { Regra, TipoRegra } from "../api/client";

const TIPOS: TipoRegra[] = ["obrigatória", "opcional", "restritiva", "condicional"];

interface Props {
  regra: Regra | null;      // null = nova regra
  onSalvar: (dados: Omit<Regra, "id">) => void;
  onFechar: () => void;
}

export default function RegraModal({ regra, onSalvar, onFechar }: Props) {
  const [descricao, setDescricao] = useState("");
  const [tipo, setTipo] = useState<TipoRegra>("obrigatória");
  const [condicao, setCondicao] = useState("");
  const [referencia, setReferencia] = useState("");

  useEffect(() => {
    if (regra) {
      setDescricao(regra.descricao);
      setTipo(regra.tipo);
      setCondicao(regra.condicao ?? "");
      setReferencia(regra.referencia ?? "");
    } else {
      setDescricao(""); setTipo("obrigatória");
      setCondicao(""); setReferencia("");
    }
  }, [regra]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!descricao.trim()) return;
    onSalvar({
      descricao: descricao.trim(),
      tipo,
      condicao: condicao.trim() || null,
      referencia: referencia.trim() || null,
    });
  }

  return (
    <div style={styles.overlay} onClick={onFechar}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div style={styles.modalHeader}>
          <h2 style={styles.modalTitulo}>{regra ? "Editar Regra" : "Nova Regra"}</h2>
          <button style={styles.btnFechar} onClick={onFechar}>✕</button>
        </div>

        <form onSubmit={handleSubmit} style={styles.form}>
          <label style={styles.label}>
            Descrição *
            <textarea
              style={styles.textarea}
              value={descricao}
              onChange={(e) => setDescricao(e.target.value)}
              rows={3}
              required
              autoFocus
            />
          </label>

          <label style={styles.label}>
            Tipo
            <select
              style={styles.select}
              value={tipo}
              onChange={(e) => setTipo(e.target.value as TipoRegra)}
            >
              {TIPOS.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </label>

          <label style={styles.label}>
            Condição
            <input
              style={styles.input}
              value={condicao}
              onChange={(e) => setCondicao(e.target.value)}
              placeholder="Ex: apenas para cursos subsequentes"
            />
          </label>

          <label style={styles.label}>
            Referência
            <input
              style={styles.input}
              value={referencia}
              onChange={(e) => setReferencia(e.target.value)}
              placeholder="Ex: Art. 5º, item I"
            />
          </label>

          <div style={styles.acoes}>
            <button type="button" style={styles.btnCancelar} onClick={onFechar}>
              Cancelar
            </button>
            <button type="submit" style={styles.btnSalvar}>
              Salvar
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  overlay: {
    position: "fixed", inset: 0, background: "rgba(0,0,0,.45)",
    display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100,
  },
  modal: {
    background: "#fff", borderRadius: 10, width: "100%", maxWidth: 500,
    padding: "24px 28px", boxShadow: "0 8px 32px rgba(0,0,0,.2)",
  },
  modalHeader: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 },
  modalTitulo: { margin: 0, fontSize: 18, fontWeight: 700 },
  btnFechar: {
    background: "none", border: "none", fontSize: 18,
    cursor: "pointer", color: "#666", lineHeight: 1,
  },
  form: { display: "flex", flexDirection: "column", gap: 14 },
  label: { display: "flex", flexDirection: "column", gap: 5, fontSize: 13, fontWeight: 600, color: "#333" },
  textarea: { borderRadius: 6, border: "1px solid #ccc", padding: "8px 10px", fontSize: 14, resize: "vertical" },
  input: { borderRadius: 6, border: "1px solid #ccc", padding: "8px 10px", fontSize: 14 },
  select: { borderRadius: 6, border: "1px solid #ccc", padding: "8px 10px", fontSize: 14 },
  acoes: { display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 8 },
  btnCancelar: {
    background: "#f5f5f5", color: "#333", border: "1px solid #ddd",
    borderRadius: 6, padding: "9px 20px", cursor: "pointer", fontSize: 14,
  },
  btnSalvar: {
    background: "#1a237e", color: "#fff", border: "none",
    borderRadius: 6, padding: "9px 20px", cursor: "pointer", fontWeight: 700, fontSize: 14,
  },
};
