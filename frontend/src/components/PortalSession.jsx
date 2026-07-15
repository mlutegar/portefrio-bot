import { useEffect, useRef, useState } from "react";
import { statusSessao, ensureSessao, loginPortal, logoutPortal } from "../api.js";

// Reautentica proativamente quando faltar menos que isto para expirar (evita a
// janela em que uma busca pega a sessão já morta).
const REAUTH_ANTECIPADO_SEG = 120;
// Após N falhas consecutivas, para o reauth automático e exige clique manual
// (evita abrir Chromium a cada 30s para sempre quando a credencial está errada).
const MAX_FALHAS_AUTO = 3;

function formatarRestante(seg) {
  if (seg == null) return "";
  if (seg <= 0) return "expira em <1min";
  const min = Math.floor(seg / 60);
  const s = seg % 60;
  if (min <= 0) return `expira em ${s}s`;
  return `expira em ${min}min ${String(s).padStart(2, "0")}s`;
}

export default function PortalSession({ configurado, refresh, onChange, onSessionActiveChange }) {
  const [sessao, setSessao] = useState(null); // { ativa, expira_em_seg, existe, ... }
  const [restante, setRestante] = useState(null); // countdown local (segundos)
  const [loading, setLoading] = useState(false);
  const [carregandoStatus, setCarregandoStatus] = useState(true);
  const [reautenticando, setReautenticando] = useState(false);
  const [erro, setErro] = useState(null);
  const [aviso, setAviso] = useState(null); // toast discreto "sessão renovada"

  // Guarda de reentrância + contador de falhas do reauth automático.
  const reauthEmAndamento = useRef(false);
  const falhasAuto = useRef(0);

  function aplicarSessao(s) {
    setSessao(s);
    setRestante(s?.ativa ? s.expira_em_seg ?? null : null);
    onSessionActiveChange?.(!!s?.ativa);
  }

  // Dispara a reautenticação transparente (expirada OU perto de expirar).
  async function reautenticar({ automatico }) {
    if (reauthEmAndamento.current) return;
    reauthEmAndamento.current = true;
    setReautenticando(true);
    try {
      const r = await ensureSessao();
      aplicarSessao(r.sessao);
      if (r.ok) {
        falhasAuto.current = 0;
        setErro(null);
        if (automatico) {
          setAviso("Sessão renovada automaticamente.");
        }
      } else {
        falhasAuto.current += 1;
        setErro(r.mensagem);
      }
    } catch (err) {
      falhasAuto.current += 1;
      setErro(err.message);
    } finally {
      setReautenticando(false);
      reauthEmAndamento.current = false;
    }
  }

  async function carregar() {
    try {
      const s = await statusSessao();
      aplicarSessao(s);

      if (!configurado || falhasAuto.current >= MAX_FALHAS_AUTO) return;

      const expirada = s?.existe && !s?.ativa;
      const quaseExpirando =
        s?.ativa &&
        s.expira_em_seg != null &&
        s.expira_em_seg <= REAUTH_ANTECIPADO_SEG;

      // Reautenticação automática: sem intervenção do usuário.
      if (expirada || quaseExpirando) {
        await reautenticar({ automatico: true });
      }
    } catch {
      /* silencioso — provável API offline; próximo poll tenta de novo */
    } finally {
      setCarregandoStatus(false);
    }
  }

  useEffect(() => {
    carregar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [configurado, refresh]);

  // Poll do backend a cada 30s (fonte da verdade + gatilho do reauth).
  useEffect(() => {
    const id = setInterval(carregar, 30000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [configurado]);

  // Countdown local de 1s (sensação de tempo real sem bater no backend).
  useEffect(() => {
    if (restante == null) return;
    const id = setInterval(() => {
      setRestante((r) => (r == null ? null : Math.max(0, r - 1)));
    }, 1000);
    return () => clearInterval(id);
  }, [restante == null]);

  // Some com o aviso "sessão renovada" após alguns segundos.
  useEffect(() => {
    if (!aviso) return;
    const id = setTimeout(() => setAviso(null), 4000);
    return () => clearTimeout(id);
  }, [aviso]);

  async function entrar() {
    setErro(null);
    setLoading(true);
    try {
      const r = await loginPortal();
      aplicarSessao(r.sessao);
      falhasAuto.current = 0; // reset: usuário assumiu o controle manualmente.
      if (!r.ok) setErro(r.mensagem);
      onChange?.();
    } catch (err) {
      setErro(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function sair() {
    setErro(null);
    setLoading(true);
    try {
      aplicarSessao(await logoutPortal());
      falhasAuto.current = 0;
      onChange?.();
    } catch (err) {
      setErro(err.message);
    } finally {
      setLoading(false);
    }
  }

  const ativa = sessao?.ativa;
  const expirada = sessao?.existe && !ativa;
  const desistiu = falhasAuto.current >= MAX_FALHAS_AUTO;

  return (
    <div className="card">
      <h2>Sessão no portal</h2>

      {carregandoStatus ? (
        <div className="badge">⏳ Verificando sessão...</div>
      ) : ativa ? (
        <div className="badge online">
          🟢 Sessão ativa {formatarRestante(restante)}
        </div>
      ) : expirada ? (
        <div className="badge pending">
          {reautenticando
            ? "🟡 Sessão expirada — reautenticando…"
            : desistiu
            ? "🔴 Reautenticação falhou — entre manualmente"
            : "🟡 Sessão expirada"}
        </div>
      ) : (
        <div className="badge offline">⚪ Sem sessão ativa</div>
      )}

      <div className="acoes" style={{ marginTop: 12 }}>
        <button onClick={entrar} disabled={loading || !configurado}>
          {loading ? "Autenticando..." : "Entrar no portal"}
        </button>
        {ativa && (
          <button
            type="button"
            className="secondary"
            onClick={sair}
            disabled={loading}
          >
            Sair
          </button>
        )}
      </div>

      {!configurado && (
        <p className="hint">Configure as credenciais do portal para entrar.</p>
      )}
      {aviso && <div className="aviso">✅ {aviso}</div>}
      {erro && <div className="erro">⚠️ {erro}</div>}
    </div>
  );
}
