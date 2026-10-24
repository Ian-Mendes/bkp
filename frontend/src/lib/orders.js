// Rótulos e classes de exibição para pedidos e perfis (textos em pt-BR).

export const ORDER_STATUS = {
  parsed: "Analisado",
  queued: "Na fila",
  processing: "Processando",
  done: "Concluído",
  failed: "Falhou",
};

export const RELATION_LABELS = {
  seguidor: "Segue você",
  seguindo: "Você segue",
  ambos: "Mútuo",
};

export function orderStatusInfo(status) {
  const cls =
    status === "done" ? "status-done"
      : status === "queued" || status === "processing" ? "status-ongoing"
        : status === "failed" ? "status-failed"
          : "status-idle";
  return { text: ORDER_STATUS[status] || status, cls };
}

export function profileStatusInfo(status) {
  switch (status) {
    case "ok": return { text: "Enriquecido", tone: "ok" };
    case "not_enriched": return { text: "Não enriquecido", tone: "muted" };
    case "pending": return { text: "Pendente", tone: "muted" };
    case "private": return { text: "Privado", tone: "warn" };
    case "not_found": return { text: "Não encontrado", tone: "muted" };
    case "rate_limited": return { text: "Limite de consultas", tone: "warn" };
    case "error": return { text: "Erro", tone: "err" };
    default: return { text: status, tone: "muted" };
  }
}
