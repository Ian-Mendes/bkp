import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      // O backend seta o cookie httpOnly no login; nada a guardar no JS.
      await api("/auth/login", { method: "POST", body: { email, password } });
      navigate("/dashboard");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="center">
      <form className="card" onSubmit={submit}>
        <h1>Entrar</h1>
        <p className="sub">BKP — backup enriquecido do Instagram</p>

        {error && <div className="error" role="alert">{error}</div>}

        <label htmlFor="email">E-mail</label>
        <input id="email" type="email" required autoComplete="email"
               value={email} onChange={(e) => setEmail(e.target.value)} />

        <label htmlFor="password">Senha</label>
        <input id="password" type="password" required maxLength={128}
               autoComplete="current-password"
               value={password} onChange={(e) => setPassword(e.target.value)} />

        <button type="submit" disabled={loading}>
          {loading ? "Aguarde..." : "Entrar"}
        </button>
      </form>
    </main>
  );
}
