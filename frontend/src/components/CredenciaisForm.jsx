import { useEffect, useState } from "react";
import {
  statusCredenciais,
  salvarCredenciais,
  apagarCredenciais,
} from "../api.js";

export default function CredenciaisForm({ onChange }) {
  const [form, setForm] = useState({
    email: "",
    senha: "",
    senha_secundaria: "",
  });
  const [status, setStatus] = useState(null); // { configurado, email_mascarado }
  const [carregandoStatus, setCarregandoStatus] = useState(true);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState(null); // { ok, texto }

  function update(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function carregarStatus() {
    try {
      const s = await statusCredenciais();
      setStatus(s);
      onChange?.(s);
    } catch {
      /* silencioso */
    } finally {
      setCarregandoStatus(false);
    }
  }

  useEffect(() => {
    carregarStatus();
  }, []);

  async function onSubmit(e) {
    e.preventDefault();
    setMsg(null);
    setLoading(true);
    try {
      const r = await salvarCredenciais(form);
      setMsg({ ok: r.ok, texto: r.mensagem });
      if (r.ok) {
        setForm({ email: "", senha: "", senha_secundaria: "" });
        carregarStatus();
      }
    } catch (err) {
      setMsg({ ok: false, texto: err.message });
    } finally {
      setLoading(false);
    }
  }

  async function onApagar() {
    setMsg(null);
    setLoading(true);
    try {
      await apagarCredenciais();
      setMsg({ ok: true, texto: "Credenciais removidas." });
      carregarStatus();
    } catch (err) {
      setMsg({ ok: false, texto: err.message });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card">
      <h2>Credenciais do portal</h2>
      <p className="hint">
        As credenciais são cifradas e guardadas em cofre no servidor — nunca ficam
        em texto claro no navegador ou no código.
      </p>

      {carregandoStatus ? (
        <div className="badge">⏳ Carregando...</div>
      ) : status?.configurado ? (
        <div className="badge online">
          ✅ Configurado ({status.email_mascarado})
        </div>
      ) : (
        <div className="badge offline">⚠️ Nenhuma credencial cadastrada</div>
      )}

      <form onSubmit={onSubmit} className="form">
        <label>
          E-mail do portal
          <input
            type="email"
            value={form.email}
            onChange={(e) => update("email", e.target.value)}
            placeholder="financeiro@portefrio.com"
            required
          />
        </label>
        <label>
          Senha
          <input
            type="password"
            value={form.senha}
            onChange={(e) => update("senha", e.target.value)}
            required
          />
        </label>
        <label>
          Senha secundária / 2FA <span className="opt">(opcional)</span>
          <input
            type="password"
            value={form.senha_secundaria}
            onChange={(e) => update("senha_secundaria", e.target.value)}
          />
        </label>
        <div className="acoes">
          <button type="submit" disabled={loading}>
            {loading ? "Testando..." : "Salvar e testar"}
          </button>
          {status?.configurado && (
            <button
              type="button"
              className="secondary"
              onClick={onApagar}
              disabled={loading}
            >
              Remover
            </button>
          )}
        </div>
      </form>

      {msg && (
        <div className={msg.ok ? "resultado" : "erro"}>
          {msg.ok ? "✅ " : "⚠️ "}
          {msg.texto}
        </div>
      )}
    </div>
  );
}
