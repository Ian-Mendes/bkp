import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, setToken } from "../lib/api";

export default function Login() {
  const navigate = useNavigate();
  const [mode, setMode] = useState("login"); // login | register
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [needsVerify, setNeedsVerify] = useState(false);
  const [sent, setSent] = useState(false); // cadastro feito, aguardando confirmação
  const [loading, setLoading] = useState(false);

  const isRegister = mode === "register";

  async function submit(e) {
    e.preventDefault();
    setError("");
    setInfo("");
    setNeedsVerify(false);
    if (isRegister && password.length < 10) {
      setError("A senha precisa ter pelo menos 10 caracteres.");
      return;
    }
    if (isRegister && password !== confirm) {
      setError("As senhas não conferem.");
      return;
    }
    setLoading(true);
    try {
      const data = await api(isRegister ? "/auth/register" : "/auth/login", {
        method: "POST",
        body: { email, password },
      });
      if (isRegister) {
        setSent(true);
      } else {
        setToken(data.access_token);
        navigate("/dashboard");
      }
    } catch (err) {
      setError(err.message);
      if (err.status === 403) setNeedsVerify(true);
    } finally {
      setLoading(false);
    }
  }

  async function resend() {
    setError("");
    setInfo("");
    if (!email) {
      setError("Informe o e-mail.");
      return;
    }
    try {
      const data = await api("/auth/resend-verification", {
        method: "POST",
        body: { email },
      });
      setInfo(data.message);
    } catch (err) {
      setError(err.message);
    }
  }

  if (sent) {
    return (
      <main className="center">
        <div className="card">
          <h1>Verifique seu e-mail</h1>
          <p className="sub">
            Se o endereço <strong>{email}</strong> puder ser cadastrado, enviamos
            um link de confirmação. Confira também a caixa de spam.
          </p>
          {error && <div className="error" role="alert">{error}</div>}
          {info && <div className="notice" role="status">{info}</div>}
          <button type="button" onClick={resend}>Reenviar e-mail</button>
          <p className="switch">
            <button type="button" className="link"
                    onClick={() => { setSent(false); setMode("login"); setError(""); setInfo(""); }}>
              Voltar para o login
            </button>
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="center">
      <form className="card" onSubmit={submit}>
        <h1>{isRegister ? "Criar conta" : "Entrar"}</h1>
        <p className="sub">BKP — backup enriquecido do Instagram</p>

        {error && <div className="error" role="alert">{error}</div>}
        {info && <div className="notice" role="status">{info}</div>}
        {needsVerify && (
          <p className="switch" style={{ marginTop: 0, marginBottom: 16 }}>
            <button type="button" className="link" onClick={resend}>
              Reenviar e-mail de confirmação
            </button>
          </p>
        )}

        <label htmlFor="email">E-mail</label>
        <input id="email" type="email" required autoComplete="email"
               value={email} onChange={(e) => setEmail(e.target.value)} />

        <label htmlFor="password">Senha</label>
        <input id="password" type="password" required maxLength={128}
               autoComplete={isRegister ? "new-password" : "current-password"}
               value={password} onChange={(e) => setPassword(e.target.value)} />

        {isRegister && (
          <>
            <label htmlFor="confirm">Confirmar senha</label>
            <input id="confirm" type="password" required maxLength={128}
                   autoComplete="new-password"
                   value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          </>
        )}

        <button type="submit" disabled={loading}>
          {loading ? "Aguarde..." : isRegister ? "Cadastrar" : "Entrar"}
        </button>

        {!isRegister && (
          <p className="switch">
            <Link to="/forgot-password">Esqueci minha senha</Link>
          </p>
        )}

        <p className="switch">
          {isRegister ? "Já tem conta? " : "Não tem conta? "}
          <button type="button" className="link"
                  onClick={() => {
                    setMode(isRegister ? "login" : "register");
                    setError(""); setInfo(""); setNeedsVerify(false); setConfirm("");
                  }}>
            {isRegister ? "Entrar" : "Cadastre-se"}
          </button>
        </p>
      </form>
    </main>
  );
}
