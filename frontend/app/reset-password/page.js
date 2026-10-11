"use client";
import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api } from "../../lib/api";

function ResetForm() {
  const token = useSearchParams().get("token");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);

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
      await api("/auth/reset-password", { method: "POST", body: { token, password } });
      setDone(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <div className="card">
        <h1>Link inválido</h1>
        <p className="sub">Peça um novo link de recuperação.</p>
        <p className="switch"><Link href="/forgot-password">Recuperar senha</Link></p>
      </div>
    );
  }

  if (done) {
    return (
      <div className="card">
        <h1>Senha alterada</h1>
        <p className="sub">Você já pode entrar com a nova senha.</p>
        <p className="switch"><Link href="/login">Ir para o login</Link></p>
      </div>
    );
  }

  return (
    <form className="card" onSubmit={submit}>
      <h1>Nova senha</h1>
      <p className="sub">Escolha uma senha com pelo menos 10 caracteres.</p>
      {error && <div className="error" role="alert">{error}</div>}
      <label htmlFor="password">Nova senha</label>
      <input id="password" type="password" required maxLength={128}
             autoComplete="new-password"
             value={password} onChange={(e) => setPassword(e.target.value)} />
      <label htmlFor="confirm">Confirmar senha</label>
      <input id="confirm" type="password" required maxLength={128}
             autoComplete="new-password"
             value={confirm} onChange={(e) => setConfirm(e.target.value)} />
      <button type="submit" disabled={loading}>
        {loading ? "Aguarde..." : "Salvar nova senha"}
      </button>
      {error.includes("expirado") && (
        <p className="switch"><Link href="/forgot-password">Pedir novo link</Link></p>
      )}
    </form>
  );
}

export default function ResetPassword() {
  return (
    <main className="center">
      <Suspense fallback={null}>
        <ResetForm />
      </Suspense>
    </main>
  );
}
