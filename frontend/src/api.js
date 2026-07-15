export async function checkHealth() {
  const res = await fetch("/health");
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function iniciarBusca(payload) {
  const res = await fetch("/cnpj/buscar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data; // { job_id, status }
}

export async function statusJob(jobId) {
  const res = await fetch(`/jobs/${jobId}`);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data; // JobState
}

export async function statusCredenciais() {
  const res = await fetch("/credenciais");
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json(); // { configurado, email_mascarado }
}

export async function salvarCredenciais(payload) {
  const res = await fetch("/credenciais/salvar-e-testar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data; // { ok, mensagem }
}

export async function apagarCredenciais() {
  const res = await fetch("/credenciais", { method: "DELETE" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function statusSessao() {
  const res = await fetch("/portal/session");
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json(); // { ativa, expira_em_seg, email_mascarado }
}

export async function loginPortal() {
  const res = await fetch("/portal/login", { method: "POST" });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data; // { ok, mensagem, sessao }
}

// Reautentica apenas se a sessão estiver expirada/ausente (idempotente).
export async function ensureSessao() {
  const res = await fetch("/portal/session/ensure", { method: "POST" });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data; // { ok, mensagem, sessao }
}

export async function logoutPortal() {
  const res = await fetch("/portal/session", { method: "DELETE" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function listarHistorico(email) {
  const url = email ? `/history?email=${encodeURIComponent(email)}` : "/history";
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// Faz polling do job até terminar (done/error) ou estourar o tempo.
export async function aguardarJob(jobId, onUpdate, { intervalMs = 1500, timeoutMs = 180000 } = {}) {
  const inicio = Date.now();
  while (true) {
    const job = await statusJob(jobId);
    if (onUpdate) onUpdate(job);
    if (job.status === "done" || job.status === "error") return job;
    if (Date.now() - inicio > timeoutMs) {
      throw new Error("Tempo limite excedido aguardando o resultado.");
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
}

export async function iniciarScoreNavigation() {
  const res = await fetch("/portal/score-navigation", { method: "POST" });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data; // { status, step, error, diagnostics_base, updated_at }
}

export async function obterScoreNavigationStatus() {
  const res = await fetch("/portal/score-navigation");
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data; // { status, step, error, diagnostics_base, updated_at }
}

export function urlDiagnostico(baseName, ext) {
  return `/portal/diagnostics/${encodeURIComponent(baseName)}/${encodeURIComponent(ext)}`;
}

export async function obterHistoricoScore(email) {
  const url = email ? `/portal/score-navigation/history?email=${encodeURIComponent(email)}` : "/portal/score-navigation/history";
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}


