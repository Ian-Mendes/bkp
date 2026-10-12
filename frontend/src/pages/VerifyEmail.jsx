import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";

export default function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const d = await api("/auth/verify-email", {
        method: "POST",
        body: { token, password },
      });
      setDone(d.message);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <main className="center">
        <div className="card">
          <h1>Link inválido</h1>
          <p className="switch"><Link to="/login">Ir para o login</Link></p>
        </div>
      </main>
    );
  }

  if (done) {
    return (
      <main className="center">
        <div className="card">
          <h1>E-mail confirmado</h1>
          <p className="sub">{done}</p>
          <p className="switch"><Link to="/login">Ir para o login</Link></p>
        </div>
      </main>
    );
  }

  return (
    <main className="center">
      <form className="card" onSubmit={submit}>
        <h1>Confirmar e-mail</h1>
        <p className="sub">
          Para ativar a conta, digite a senha que você definiu no cadastro.
        </p>
        {error && <div className="error" role="alert">{error}</div>}
        <label htmlFor="password">Senha</label>
        <input id="password" type="password" required maxLength={128}
               autoComplete="current-password"
               value={password} onChange={(e) => setPassword(e.target.value)} />
        <button type="submit" disabled={loading}>
          {loading ? "Aguarde..." : "Confirmar"}
        </button>
        <p className="switch"><Link to="/login">Voltar para o login</Link></p>
      </form>
    </main>
  );
}
