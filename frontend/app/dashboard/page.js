"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getToken, clearToken } from "../../lib/api";

export default function Dashboard() {
  const router = useRouter();
  const [user, setUser] = useState(null);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    api("/auth/me", { auth: true })
      .then(setUser)
      .catch(() => {
        clearToken();
        router.replace("/login");
      });
  }, [router]);

  function logout() {
    clearToken();
    router.replace("/login");
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
