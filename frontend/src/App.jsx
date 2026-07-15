import { useState } from "react";
import HealthBadge from "./components/HealthBadge.jsx";
import CnpjSearch from "./components/CnpjSearch.jsx";
import CredenciaisForm from "./components/CredenciaisForm.jsx";
import PortalSession from "./components/PortalSession.jsx";
import ScoreNavigation from "./components/ScoreNavigation.jsx";

export default function App() {
  const [configurado, setConfigurado] = useState(false);
  const [sessionAtiva, setSessionAtiva] = useState(false);
  // Incrementa a cada mudança de credenciais/sessão para os filhos recarregarem.
  const [version, setVersion] = useState(0);

  function bump() {
    setVersion((v) => v + 1);
  }

  return (
    <div className="page">
      <header className="topbar">
        <h1>Portefrio · Consulta de CNPJ</h1>
        <HealthBadge />
      </header>
      <main>
        <CredenciaisForm
          onChange={(status) => {
            setConfigurado(!!status?.configurado);
            bump();
          }}
        />
        <PortalSession
          configurado={configurado}
          refresh={version}
          onChange={bump}
          onSessionActiveChange={setSessionAtiva}
        />
        <ScoreNavigation configurado={configurado} sessionAtiva={sessionAtiva} />
        <CnpjSearch configurado={version} onBuscaConcluida={bump} />
      </main>
    </div>
  );
}

