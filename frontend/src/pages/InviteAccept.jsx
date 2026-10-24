import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../lib/api";

export default function InviteAccept() {
  const { token } = useParams();
  const navigate = useNavigate();
  const [email, setEmail] = useState(null);
  const [status, setStatus] = useState("loading"); // loading | invalid | ready
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let active = true;
    if (!token) {
      setStatus("invalid");
      return;
    }
    api(`/auth/invite/${token}`)
      .then((d) => {
        if (!active) return;
        setEmail(d.email);
        setStatus("ready");
      })
      .catch(() => {
        if (active) setStatus("invalid");
      });
    return () => { active = false; };
  }, [token]);

  async function submit(e) {
    e.preventDefault();
    setError("");
    if (password.length < 10) {
      setError("A senha precisa ter pelo menos 10 caracteres.");
      return;
    }
    if (password !== confirm) {
      setError("As senhas não conferem.");
      return;
    }
    setLoading(true);
    try {
      await api("/auth/accept-invite", { method: "POST", body: { token, password } });
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  if (status === "invalid") {
    return (
      <main className="center">
        <div className="card">
          <h1>Convite inválido</h1>
          <p className="sub">Este link não é válido, expirou ou já foi utilizado.</p>
          <p className="switch"><Link to="/login">Ir para o login</Link></p>
        </div>
      </main>
    );
  }

  if (status === "loading") {
    return (
      <main className="center">
        <div className="card">
          <p className="sub">Verificando convite…</p>
        </div>
      </main>
    );
  }

  return (
    <main className="center">
      <form className="card" onSubmit={submit}>
        <h1>Criar sua conta</h1>
        <p className="sub">
          Defina uma senha para ativar o acesso de <strong>{email}</strong>.
        </p>

        {error && <div className="error" role="alert">{error}</div>}

        <label htmlFor="password">Senha</label>
        <input id="password" type="password" required maxLength={128}
               autoComplete="new-password"
               value={password} onChange={(e) => setPassword(e.target.value)} />

        <label htmlFor="confirm">Confirmar senha</label>
        <input id="confirm" type="password" required maxLength={128}
               autoComplete="new-password"
               value={confirm} onChange={(e) => setConfirm(e.target.value)} />

        <button type="submit" disabled={loading}>
          {loading ? "Aguarde..." : "Ativar acesso"}
        </button>
      </form>
    </main>
  );
}
