import { useState } from "react";
import { checkHealth } from "../api.js";

export default function HealthBadge() {
  const [status, setStatus] = useState(null); // "online" | "offline" | null
  const [loading, setLoading] = useState(false);

  async function verificar() {
    setLoading(true);
    try {
      await checkHealth();
      setStatus("online");
    } catch {
      setStatus("offline");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="health">
      <button onClick={verificar} disabled={loading}>
        {loading ? "Verificando..." : "Verificar API"}
      </button>
      {status && (
        <span className={`badge ${status}`}>
          {status === "online" ? "API online" : "API offline"}
        </span>
      )}
    </div>
  );
}
