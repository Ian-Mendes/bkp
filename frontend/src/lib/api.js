const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
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
  if (body) headers["Content-Type"] = "application/json";
  if (auth) headers["Authorization"] = `Bearer ${getToken()}`;
  let res;
  try {
    res = await fetch(`${API}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
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
