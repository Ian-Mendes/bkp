import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, logout as apiLogout, refreshSession } from "../lib/api";

export default function Dashboard() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);

  useEffect(() => {
    let ativo = true;   // evita setState depois do unmount (StrictMode monta 2x em dev)
    async function carregar() {
      try {
        const u = await api("/auth/me");
        if (ativo) setUser(u);
      } catch (err) {
        // access token expirou (1h)? tenta renovar com o refresh (30 dias).
        if (err.status === 401 && (await refreshSession())) {
          try {
            const u = await api("/auth/me");
            if (ativo) setUser(u);
            return;
          } catch {
            // refresh "funcionou" mas o /me ainda falhou: cai no fluxo de logout
          }
        }
        if (ativo) navigate("/login", { replace: true });
      }
    }
    carregar();
    return () => { ativo = false; };
  }, [navigate]);

  async function sair() {
    await apiLogout();   // invalida os cookies no backend (httpOnly: só o servidor apaga)
    navigate("/login", { replace: true });
  }

  if (!user) return null;

  return (
    <main className="center">
      <div className="card">
        <h1>Olá!</h1>
        <p className="sub">Logado como {user.email}</p>
        <button className="out" onClick={sair}>Sair</button>
      </div>
    </main>
  );
}
