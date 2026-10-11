"use client";
import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api } from "../../lib/api";

function Verify() {
  const token = useSearchParams().get("token");
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
      <div className="card">
        <h1>Link inválido</h1>
        <p className="switch"><Link href="/login">Ir para o login</Link></p>
      </div>
    );
  }

  if (done) {
    return (
      <div className="card">
        <h1>E-mail confirmado</h1>
        <p className="sub">{done}</p>
        <p className="switch"><Link href="/login">Ir para o login</Link></p>
      </div>
    );
  }

  return (
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
      <p className="switch"><Link href="/login">Voltar para o login</Link></p>
    </form>
  );
}

export default function VerifyEmail() {
  return (
    <main className="center">
      <Suspense fallback={null}>
        <Verify />
      </Suspense>
    </main>
  );
}
