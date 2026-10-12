import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, getToken, clearToken } from "../lib/api";

export default function Dashboard() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);

  useEffect(() => {
    if (!getToken()) {
      navigate("/login", { replace: true });
      return;
    }
    api("/auth/me", { auth: true })
      .then(setUser)
      .catch(() => {
        clearToken();
        navigate("/login", { replace: true });
      });
  }, [navigate]);

  function logout() {
    clearToken();
    navigate("/login", { replace: true });
  }

  if (!user) return null;

  return (
    <main className="center">
      <div className="card">
        <h1>Olá!</h1>
        <p className="sub">Logado como {user.email}</p>
        <button className="out" onClick={logout}>Sair</button>
      </div>
    </main>
  );
}
