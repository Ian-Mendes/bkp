import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";

export default function Home() {
  const navigate = useNavigate();
  useEffect(() => {
    // Sem token no JS: pergunta ao backend se o cookie de sessão está vivo.
    // Deslogado, o backend devolve 401 e o catch manda para /login.
    api("/auth/me")
      .then(() => navigate("/dashboard", { replace: true }))
      .catch(() => navigate("/login", { replace: true }));
  }, [navigate]);
  return null;
}
