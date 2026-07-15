import { useEffect, useState } from "react";
import {
  iniciarBusca,
  aguardarJob,
  listarHistorico,
  statusCredenciais,
} from "../api.js";

function maskCnpj(v) {
  return v
    .replace(/\D/g, "")
    .slice(0, 14)
    .replace(/^(\d{2})(\d)/, "$1.$2")
    .replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3")
    .replace(/\.(\d{3})(\d)/, ".$1/$2")
    .replace(/(\d{4})(\d)/, "$1-$2");
}

export default function CnpjSearch({ configurado, onBuscaConcluida }) {
  const [cnpj, setCnpj] = useState("");
  const [emailConfig, setEmailConfig] = useState(null);
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState(null);
  const [job, setJob] = useState(null); // JobState em andamento/final
  const [historico, setHistorico] = useState([]);

  async function carregarHistorico() {
    // Sem argumento: o backend usa o e-mail configurado no cofre.
    try {
      setHistorico(await listarHistorico());
    } catch {
      /* silencioso */
    }
  }

  // Ao configurar/atualizar credenciais, mostra o e-mail e carrega o histórico.
  useEffect(() => {
    (async () => {
      try {
        const s = await statusCredenciais();
        if (s.configurado) {
          setEmailConfig(s.email_mascarado);
          carregarHistorico();
        } else {
          setEmailConfig(null);
          setHistorico([]);
        }
      } catch {
        /* silencioso */
      }
    })();
  }, [configurado]);

  async function onSubmit(e) {
    e.preventDefault();
    setErro(null);
    setJob(null);
    setLoading(true);
    try {
      const { job_id } = await iniciarBusca({ cnpj });
      const final = await aguardarJob(job_id, (j) => setJob(j));
      setJob(final);
      if (final.status === "error") setErro(final.error);
      carregarHistorico();
      // Uma busca pode ter criado/renovado a sessão — avisa o app para atualizar.
      onBuscaConcluida?.();
    } catch (err) {
      setErro(err.message);
    } finally {
      setLoading(false);
    }
  }

  function baixarJson() {
    const r = job?.result;
    if (!r) return;
    const blob = new Blob([JSON.stringify(r, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `cnpj-${(r.cnpj || "").replace(/\D/g, "")}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const result = job?.status === "done" ? job.result : null;
  const emAndamento = loading && job && job.status !== "done" && job.status !== "error";

  return (
    <div className="card">
      <h2>Consultar CNPJ no portal</h2>
      {emailConfig ? (
        <p className="hint">Usando credenciais configuradas: {emailConfig}</p>
      ) : (
        <div className="erro">
          ⚠️ Configure as credenciais do portal antes de buscar.
        </div>
      )}
      <form onSubmit={onSubmit} className="form">
        <label>
          CNPJ
          <input
            type="text"
            value={cnpj}
            onChange={(e) => setCnpj(maskCnpj(e.target.value))}
            placeholder="00.000.000/0000-00"
            required
          />
        </label>
        <button type="submit" disabled={loading || !emailConfig}>
          {loading ? "Processando..." : "Buscar"}
        </button>
      </form>

      {emAndamento && (
        <div className="progresso">
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${job.progress}%` }} />
          </div>
          <span className="step">
            {job.step} ({job.progress}%)
          </span>
        </div>
      )}

      {erro && <div className="erro">⚠️ {erro}</div>}

      {result && (
        <div className="resultado">
          <div className="resultado-head">
            <h3>Resultado</h3>
            <div className="acoes">
              <a
                className="btn-link"
                href={`/files/${result.job_id}/zip`}
                target="_blank"
                rel="noreferrer"
              >
                Baixar tudo (ZIP)
              </a>
              <button onClick={baixarJson} className="secondary">
                Baixar JSON
              </button>
            </div>
          </div>
          {result.empresa && (
            <p>
              <strong>Empresa:</strong> {result.empresa}
            </p>
          )}
          <p>
            <strong>Documentos:</strong> {result.documentos.length}
          </p>
          <ul className="docs">
            {result.documentos.map((d, i) => (
              <li key={i}>
                <a href={d.download_url} target="_blank" rel="noreferrer">
                  📄 {d.nome}
                </a>{" "}
                <span className="size">({Math.round(d.tamanho / 1024)} KB)</span>
              </li>
            ))}
          </ul>
          <pre className="json">{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}

      {historico.length > 0 && (
        <div className="historico">
          <h3>Histórico</h3>
          <ul>
            {historico.map((h) => (
              <li key={h.job_id}>
                <span className={`dot ${h.status}`} /> {h.cnpj}
                {h.empresa ? ` — ${h.empresa}` : ""} · {h.num_docs} doc(s) ·{" "}
                {new Date(h.created_at).toLocaleString("pt-BR")}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
