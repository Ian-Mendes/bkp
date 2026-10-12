const API = "/api";   // mesma origem; encaminhada pelo proxy (Vite em dev, reverse proxy em prod)

function errorMessage(data, status) {
  const d = data && data.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return "Dados inválidos. Confira os campos e tente novamente.";
  return `Erro ${status}`;
}

// A sessão vive em cookie httpOnly; o JS não lê nem escreve.
// `credentials: "include"` garante que o cookie vá em toda requisição.
async function request(path, { method = "GET", body } = {}) {
  const headers = {};
  const isForm = body instanceof FormData;   // multipart: o navegador define o Content-Type
  if (body && !isForm) headers["Content-Type"] = "application/json";
  let res;
  try {
    res = await fetch(`${API}${path}`, {
      method,
      headers,
      credentials: "include",
      body: isForm ? body : body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error("Não foi possível conectar à API.");
  }
  return res;
}

export async function api(path, opts = {}) {
  const res = await request(path, opts);
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const err = new Error(errorMessage(data, res.status));
    err.status = res.status;
    throw err;
  }
  return data;
}

export async function download(path) {
  // Baixa um arquivo (CSV/XLSX) e dispara o salvamento no navegador.
  const res = await request(path);
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    const err = new Error(errorMessage(data, res.status));
    err.status = res.status;
    throw err;
  }
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") || "";
  const name = (disposition.match(/filename="?([^";]+)"?/) || [])[1] || "download";
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// Tenta renovar o access token usando o refresh (cookie httpOnly).
// Devolve true se conseguiu; false se o refresh também expirou.
export async function refreshSession() {
  const res = await request("/auth/refresh", { method: "POST" });
  return res.ok;
}

export async function logout() {
  await request("/auth/logout", { method: "POST" }).catch(() => {});
}
