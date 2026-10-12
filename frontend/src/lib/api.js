const API = "/api";   // mesma origem; encaminhada pelo proxy (Vite em dev, reverse proxy em prod)
const KEY = "bkp_token";

export const getToken = () => localStorage.getItem(KEY);
export const setToken = (t) => localStorage.setItem(KEY, t);
export const clearToken = () => localStorage.removeItem(KEY);

function errorMessage(data, status) {
  const d = data && data.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return "Dados inválidos. Confira os campos e tente novamente.";
  return `Erro ${status}`;
}

export async function api(path, { method = "GET", body, auth = false } = {}) {
  const headers = {};
  const isForm = body instanceof FormData;   // multipart: o navegador define o Content-Type
  if (body && !isForm) headers["Content-Type"] = "application/json";
  if (auth) headers["Authorization"] = `Bearer ${getToken()}`;
  let res;
  try {
    res = await fetch(`${API}${path}`, {
      method,
      headers,
      body: isForm ? body : body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error("Não foi possível conectar à API.");
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const err = new Error(errorMessage(data, res.status));
    err.status = res.status;
    throw err;
  }
  return data;
}

export async function download(path, { auth = true } = {}) {
  // Baixa um arquivo (CSV/XLSX) e dispara o salvamento no navegador.
  const headers = {};
  if (auth) headers["Authorization"] = `Bearer ${getToken()}`;
  let res;
  try {
    res = await fetch(`${API}${path}`, { headers });
  } catch {
    throw new Error("Não foi possível conectar à API.");
  }
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
