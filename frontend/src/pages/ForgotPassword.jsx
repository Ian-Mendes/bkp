import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api("/auth/forgot-password", { method: "POST", body: { email } });
      setDone(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="center">
      <form className="card" onSubmit={submit}>
        <h1>Recuperar senha</h1>
        {done ? (
          <>
            <p className="sub">
              Se o e-mail estiver cadastrado, enviamos um link para definir uma
              nova senha. Ele vale por 30 minutos.
            </p>
            <p className="switch"><Link to="/login">Voltar para o login</Link></p>
          </>
        ) : (
          <>
            <p className="sub">Informe seu e-mail para receber o link de redefinição.</p>
            {error && <div className="error" role="alert">{error}</div>}
            <label htmlFor="email">E-mail</label>
            <input id="email" type="email" required autoComplete="email"
                   value={email} onChange={(e) => setEmail(e.target.value)} />
            <button type="submit" disabled={loading}>
              {loading ? "Aguarde..." : "Enviar link"}
            </button>
            <p className="switch"><Link to="/login">Voltar para o login</Link></p>
          </>
        )}
      </form>
    </main>
  );
}
