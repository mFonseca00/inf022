import type { Regra } from "../api/client";
import s from "./RegraCard.module.css";

const BADGE_CLASS: Record<string, string> = {
  "obrigatória": s.obrigatoria,
  "restritiva":  s.restritiva,
  "condicional": s.condicional,
  "opcional":    s.opcional,
};

interface Props {
  regra: Regra;
  indice: number;
  onEditar: () => void;
  onRemover: () => void;
}

export default function RegraCard({ regra, indice, onEditar, onRemover }: Props) {
  return (
    <div className={s.card}>
      <div className={s.topo}>
        <span className={s.numero}>#{indice}</span>
        <span className={`${s.badge} ${BADGE_CLASS[regra.tipo] ?? ""}`}>
          {regra.tipo}
        </span>
        <div className={s.acoes}>
          <button className={s.btnEditar} onClick={onEditar} title="Editar">✎</button>
          <button className={s.btnRemover} onClick={onRemover} title="Remover">✕</button>
        </div>
      </div>

      <p className={s.descricao}>{regra.descricao}</p>

      {regra.condicao && (
        <p className={s.meta}><strong>Condição:</strong> {regra.condicao}</p>
      )}
      {regra.referencia && (
        <p className={s.meta}><strong>Referência:</strong> {regra.referencia}</p>
      )}
    </div>
  );
}