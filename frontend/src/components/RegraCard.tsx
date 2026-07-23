import type { Regra } from "../api/client";

const COR_TIPO: Record<string, { bg: string; text: string }> = {
  "obrigatória": { bg: "#fde8e8", text: "#b71c1c" },
  "restritiva":  { bg: "#fff3e0", text: "#e65100" },
  "condicional": { bg: "#e3f2fd", text: "#0d47a1" },
  "opcional":    { bg: "#e8f5e9", text: "#1b5e20" },
};

interface Props {
  regra: Regra;
  indice: number;
  onEditar: () => void;
  onRemover: () => void;
}

export default function RegraCard({ regra, indice, onEditar, onRemover }: Props) {
  const cor = COR_TIPO[regra.tipo] ?? { bg: "#f5f5f5", text: "#333" };

  return (
    <div style={styles.card}>
      <div style={styles.topo}>
        <span style={styles.numero}>#{indice}</span>
        <span style={{ ...styles.badge, background: cor.bg, color: cor.text }}>
          {regra.tipo}
        </span>
        <div style={styles.acoes}>
          <button style={styles.btnEditar} onClick={onEditar} title="Editar">✎</button>
          <button style={styles.btnRemover} onClick={onRemover} title="Remover">✕</button>
        </div>
      </div>

      <p style={styles.descricao}>{regra.descricao}</p>

      {regra.condicao && (
        <p style={styles.meta}>
          <strong>Condição:</strong> {regra.condicao}
        </p>
      )}
      {regra.referencia && (
        <p style={styles.meta}>
          <strong>Referência:</strong> {regra.referencia}
        </p>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  card: {
    background: "#fff", borderRadius: 8, padding: "14px 18px",
    boxShadow: "0 1px 3px rgba(0,0,0,.1)", display: "flex", flexDirection: "column", gap: 8,
  },
  topo: { display: "flex", alignItems: "center", gap: 10 },
  numero: { fontWeight: 700, color: "#aaa", fontSize: 13, minWidth: 24 },
  badge: {
    borderRadius: 20, padding: "2px 10px", fontSize: 11,
    fontWeight: 700, textTransform: "capitalize",
  },
  acoes: { marginLeft: "auto", display: "flex", gap: 6 },
  btnEditar: {
    background: "#e8f0fe", border: "none", borderRadius: 5,
    padding: "4px 10px", cursor: "pointer", color: "#1a237e", fontSize: 15,
  },
  btnRemover: {
    background: "#fde8e8", border: "none", borderRadius: 5,
    padding: "4px 10px", cursor: "pointer", color: "#b71c1c", fontSize: 13,
  },
  descricao: { margin: 0, fontSize: 14, color: "#1a1a1a", lineHeight: 1.5 },
  meta: { margin: 0, fontSize: 12, color: "#666" },
};
