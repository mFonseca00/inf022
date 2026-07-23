import { useEffect, useState } from "react";
import type { Regra, TipoRegra } from "../api/client";
import s from "./RegraModal.module.css";

const TIPOS: TipoRegra[] = ["obrigatória", "opcional", "restritiva", "condicional"];

interface Props {
  regra: Regra | null;
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

  function handleSubmit(e: { preventDefault(): void }) {
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
    <div className={s.overlay} onClick={onFechar}>
      <div className={s.modal} onClick={(e) => e.stopPropagation()}>
        <div className={s.modalHeader}>
          <h2 className={s.modalTitulo}>{regra ? "Editar Regra" : "Nova Regra"}</h2>
          <button className={s.btnFechar} onClick={onFechar}>✕</button>
        </div>

        <form onSubmit={handleSubmit} className={s.form}>
          <label className={s.label}>
            Descrição *
            <textarea
              className={s.textarea}
              value={descricao}
              onChange={(e) => setDescricao(e.target.value)}
              rows={3}
              required
              autoFocus
            />
          </label>

          <label className={s.label}>
            Tipo
            <select
              className={s.select}
              value={tipo}
              onChange={(e) => setTipo(e.target.value as TipoRegra)}
            >
              {TIPOS.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </label>

          <label className={s.label}>
            Condição
            <input
              className={s.input}
              value={condicao}
              onChange={(e) => setCondicao(e.target.value)}
              placeholder="Ex: apenas para cursos subsequentes"
            />
          </label>

          <label className={s.label}>
            Referência
            <input
              className={s.input}
              value={referencia}
              onChange={(e) => setReferencia(e.target.value)}
              placeholder="Ex: Art. 5º, item I"
            />
          </label>

          <div className={s.acoes}>
            <button type="button" className={s.btnCancelar} onClick={onFechar}>
              Cancelar
            </button>
            <button type="submit" className={s.btnSalvar}>
              Salvar
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}