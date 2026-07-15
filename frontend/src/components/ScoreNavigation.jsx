import { useEffect, useRef, useState } from "react";
import {
  iniciarScoreNavigation,
  obterHistoricoScore,
  obterScoreNavigationStatus,
  urlDiagnostico,
} from "../api.js";

export default function ScoreNavigation({ configurado, sessionAtiva }) {
  const [status, setStatus] = useState("idle"); // idle, running, done, error
  const [step, setStep] = useState("");
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState(null);
  const [diagnosticsBase, setDiagnosticsBase] = useState(null);
  const [livePreview, setLivePreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [historico, setHistorico] = useState([]);

  const pollingInterval = useRef(null);

  async function carregarHistorico() {
    try {
      const data = await obterHistoricoScore();
      setHistorico(data);
    } catch (err) {
      console.error("Erro ao carregar histórico do Score:", err);
    }
  }

  async function atualizarStatus() {
    try {
      const res = await obterScoreNavigationStatus();
      setStatus(res.status);
      setStep(res.step);
      setProgress(res.progress);
      setError(res.error);
      setDiagnosticsBase(res.diagnostics_base);
      setLivePreview(res.live_preview);

      if (res.status !== "running") {
        pararPolling();
        carregarHistorico(); // Recarrega histórico ao terminar o job
      }
    } catch (err) {
      console.error("Erro ao obter status do Score Navigation:", err);
    }
  }

  function iniciarPolling() {
    if (pollingInterval.current) return;
    pollingInterval.current = setInterval(atualizarStatus, 1500);
  }

  function pararPolling() {
    if (pollingInterval.current) {
      clearInterval(pollingInterval.current);
      pollingInterval.current = null;
    }
  }

  useEffect(() => {
    atualizarStatus().then(() => {
      if (status === "running") {
        iniciarPolling();
      }
    });
    carregarHistorico();

    return () => pararPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (status === "running") {
      iniciarPolling();
    } else {
      pararPolling();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  async function iniciarNavegacao() {
    setError(null);
    setDiagnosticsBase(null);
    setLivePreview(null);
    setLoading(true);
    try {
      const res = await iniciarScoreNavigation();
      setStatus(res.status);
      setStep(res.step);
      setProgress(res.progress);
      setError(res.error);
      setDiagnosticsBase(res.diagnostics_base);
      setLivePreview(res.live_preview);
    } catch (err) {
      setError(err.message);
      setStatus("error");
    } finally {
      setLoading(false);
    }
  }

  const executando = status === "running";
  const concluido = status === "done";
  const erro = status === "error";

  return (
    <div className="card" style={{ marginTop: 24 }}>
      <h2>Score Multiplike</h2>
      <p className="hint">
        Navega de forma automatizada partindo da sessão ativa até a tela de consulta de Score.
      </p>

      <div className="acoes" style={{ marginBottom: executando || concluido || erro ? 16 : 0 }}>
        <button
          onClick={iniciarNavegacao}
          disabled={loading || executando || !configurado || !sessionAtiva}
        >
          {loading ? "Iniciando..." : executando ? "Navegando..." : "Abrir Score Multiplike"}
        </button>

        {concluido && (
          <span className="badge online">🟢 Tela de consulta alcançada</span>
        )}
        {executando && (
          <span className="badge pending">⏳ Navegação em andamento</span>
        )}
        {erro && (
          <span className="badge offline">🔴 Falha na navegação</span>
        )}
      </div>

      {executando && (
        <div className="progresso">
          <div className="progress-bar" style={{ marginBottom: 12 }}>
            <div className="progress-fill" style={{ width: `${progress}%` }}></div>
          </div>
          <span className="step" style={{ display: "block", marginBottom: 12 }}>
            {step} ({progress}%)
          </span>
        </div>
      )}

      {executando && livePreview && (
        <div className="live-preview-container" style={{ marginTop: 16, marginBottom: 16 }}>
          <h4 style={{ margin: "0 0 8px 0", fontSize: "0.9rem", color: "var(--muted)" }}>
            Visualização em tempo real (Navegador Headless)
          </h4>
          <div style={{
            position: "relative",
            borderRadius: "8px",
            border: "2px solid #334155",
            overflow: "hidden",
            background: "#000",
            boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.4)"
          }}>
            <span style={{
              position: "absolute",
              top: 8,
              left: 8,
              background: "rgba(239, 68, 68, 0.85)",
              color: "#fff",
              padding: "4px 8px",
              borderRadius: "4px",
              fontSize: "0.7rem",
              fontWeight: "bold",
              zIndex: 10,
              textTransform: "uppercase",
              display: "flex",
              alignItems: "center",
              gap: 4
            }}>
              <span style={{
                display: "inline-block",
                width: 6,
                height: 6,
                background: "#fff",
                borderRadius: "50%"
              }}></span>
              Ao Vivo
            </span>
            <img
              src={livePreview}
              alt="Visualização do Robô"
              style={{
                display: "block",
                width: "100%",
                maxHeight: "320px",
                objectFit: "contain"
              }}
            />
          </div>
        </div>
      )}

      {erro && (
        <div className="erro">
          <strong>Falha no passo:</strong> {step || "Desconhecido"}
          {error && <div style={{ marginTop: 6, fontSize: "0.9em", opacity: 0.85 }}>{error}</div>}
          {diagnosticsBase && (
            <div style={{ marginTop: 12 }}>
              <button
                type="button"
                className="secondary"
                style={{ fontSize: "0.85rem", padding: "6px 12px" }}
                onClick={() => window.open(urlDiagnostico(diagnosticsBase, "png"), "_blank")}
              >
                Ver Screenshot de Diagnóstico ↗
              </button>
              <button
                type="button"
                className="secondary"
                style={{ fontSize: "0.85rem", padding: "6px 12px", marginLeft: 8 }}
                onClick={() => window.open(urlDiagnostico(diagnosticsBase, "html"), "_blank")}
              >
                Ver HTML de Diagnóstico ↗
              </button>
            </div>
          )}
        </div>
      )}

      {concluido && diagnosticsBase && (
        <div className="aviso">
          <strong>Sucesso!</strong> A tela de consulta foi alcançada com êxito.
          <div style={{ marginTop: 12 }}>
            <button
              type="button"
              className="secondary"
              style={{ fontSize: "0.85rem", padding: "6px 12px" }}
              onClick={() => window.open(urlDiagnostico(diagnosticsBase, "png"), "_blank")}
            >
              Ver Screenshot do Score ↗
            </button>
          </div>
        </div>
      )}

      {!sessionAtiva && configurado && (
        <p className="hint" style={{ color: "var(--red)", marginTop: 8 }}>
          ⚠️ É necessário estabelecer uma sessão ativa no portal primeiro.
        </p>
      )}
      {!configurado && (
        <p className="hint" style={{ color: "var(--muted)", marginTop: 8 }}>
          ⚠️ Configure e salve as credenciais do portal primeiro.
        </p>
      )}

      <div className="historico" style={{ marginTop: 28, borderTop: "1px solid #334155", paddingTop: 16 }}>
        <h3 style={{ fontSize: "1.1rem", marginBottom: 12 }}>Histórico de Navegações</h3>
        {historico.length === 0 ? (
          <p className="hint" style={{ margin: 0 }}>Nenhuma tentativa de navegação registrada.</p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {historico.map((h) => {
              const dataStr = new Date(h.created_at).toLocaleString("pt-BR");
              return (
                <li key={h.id} style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "8px 0",
                  borderBottom: "1px solid #1e293b",
                  fontSize: "0.88rem"
                }}>
                  <div>
                    <span className={`dot ${h.status === "done" ? "done" : "error"}`}></span>
                    <strong style={{ color: h.status === "done" ? "var(--green)" : "var(--red)" }}>
                      {h.status === "done" ? "Sucesso" : "Falha"}
                    </strong>
                    {" - "}
                    <span style={{ color: "var(--text)" }}>{h.ultimo_passo}</span>
                    {h.error && (
                      <div style={{ fontSize: "0.8rem", color: "var(--muted)", marginLeft: 14, marginTop: 2 }}>
                        {h.error}
                      </div>
                    )}
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <span className="size" style={{ fontSize: "0.78rem" }}>{dataStr}</span>
                    {h.diagnostics_base && (
                      <a
                        href={urlDiagnostico(h.diagnostics_base, "png")}
                        target="_blank"
                        rel="noreferrer"
                        style={{ fontSize: "0.82rem", color: "var(--accent)", textDecoration: "none", fontWeight: "bold" }}
                      >
                        Ver Print ↗
                      </a>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
