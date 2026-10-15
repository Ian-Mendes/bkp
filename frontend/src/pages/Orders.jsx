import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { authenticatedApi, download } from "../lib/api";

const labels = {
  uploaded: "Recebido", parsed: "Analisado", queued: "Na fila",
  processing: "Em processamento", done: "Concluído", failed: "Falhou",
  pending: "Pendente", not_enriched: "Sem enriquecimento",
  enriched: "Enriquecido", rate_limited: "Limite de consultas atingido",
};
const count = value => value == null ? "Não disponível" : value.toLocaleString("pt-BR");
const statusLabel = value => labels[value] || value || "Não disponível";

function dateLabel(value) {
  if (!value) return "Não disponível";
  // Datas sem fuso vindas do SQLite também representam UTC no backend.
  const date = new Date(/(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : `${value}Z`);
  return Number.isNaN(date.getTime()) ? "Não disponível" : date.toLocaleString("pt-BR");
}

function message(err) {
  if (err.status === 401) return "Sua sessão expirou. Entre novamente para acessar seus pedidos.";
  if (err.status === 404) return "Pedido não encontrado ou indisponível para esta conta.";
  return err.message || "Não foi possível carregar os pedidos. Tente novamente.";
}

export default function Orders() {
  const { orderId } = useParams();
  return <OrdersView key={orderId || "list"} orderId={orderId} />;
}

function OrdersView({ orderId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [revision, setRevision] = useState(0);
  const [downloading, setDownloading] = useState("");
  const [downloadNotice, setDownloadNotice] = useState("");
  const downloadPending = useRef(false);
  const mounted = useRef(false);
  const heading = useRef(null);

  useEffect(() => {
    mounted.current = true;
    heading.current?.focus();
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    async function load() {
      try {
        await authenticatedApi("/auth/me");
        const response = await authenticatedApi(orderId ? `/orders/${encodeURIComponent(orderId)}` : "/orders");
        if (active) setData(response);
      } catch (err) {
        if (active) {
          setError(err);
          setData(null);
        }
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => { active = false; };
  }, [orderId, revision]);

  async function save(suffix, filename) {
    if (downloadPending.current || loading || error) return;
    downloadPending.current = true;
    setDownloading(suffix);
    setDownloadNotice("");
    try {
      await download(`/orders/${encodeURIComponent(orderId)}/${suffix}`, filename);
      if (mounted.current) setDownloadNotice("Arquivo enviado ao navegador para salvar.");
    } catch (err) {
      if (mounted.current) {
        setError(err);
        if (err.status === 401 || err.status === 404) setData(null);
      }
    } finally {
      downloadPending.current = false;
      if (mounted.current) setDownloading("");
    }
  }

  const unavailable = error?.status === 404;
  const expiredSession = error?.status === 401;
  return (
    <main className="center">
      <div className="card orders-card">
        <nav className="orders-actions" aria-label="Navegação de pedidos">
          {orderId && <Link to="/orders">Voltar para meus pedidos</Link>}
          <Link to="/dashboard">Enviar nova exportação</Link>
        </nav>
        <h1 ref={heading} tabIndex={-1}>{orderId ? "Detalhe do pedido" : "Meus pedidos"}</h1>
        <p className="sub">Consulte os dados importados e baixe seus arquivos.</p>
        <button className="out" disabled={loading || !!downloading} onClick={() => setRevision(value => value + 1)}>
          {loading ? "Atualizando…" : orderId ? "Atualizar pedido" : "Atualizar lista"}
        </button>
        <div role="status">{loading && <p>Carregando {orderId ? "pedido" : "pedidos"}…</p>}</div>
        {error && <div className="error" role="alert">
          <p>{message(error)}</p>
          {expiredSession ? <Link to="/login">Entrar novamente</Link> :
            <button className="link" disabled={loading || !!downloading} onClick={() => setRevision(value => value + 1)}>Tentar novamente</button>}
        </div>}
        {unavailable && <p>Pedidos removidos pelo prazo de retenção deixam de estar disponíveis. A API não informa o motivo deste pedido estar indisponível. Você pode enviar uma nova exportação.</p>}
        {!orderId && data && <>
          {data.length === 0 ? <p>Nenhum pedido encontrado. Envie sua primeira exportação para começar.</p> :
            <ul className="orders-list">{data.map(order => <li key={order.order_id}>
              <h2><Link className="upload-filename" to={`/orders/${order.order_id}`}>Pedido {order.order_id}</Link></h2>
              <p>Status: {statusLabel(order.status)}</p>
              <p>Criado em: {dateLabel(order.created_at)}</p>
              <p>Prazo de retenção: {dateLabel(order.expires_at)}</p>
              <p>Seguidores: {count(order.followers)} · Seguindo: {count(order.following)}</p>
            </li>)}</ul>}
          <p className="muted">Após o prazo de retenção, pedidos são removidos pela rotina do servidor, exceto enquanto estão na fila ou em processamento. A disponibilidade é confirmada ao abrir ou baixar o pedido.</p>
        </>}
        {orderId && data && <>
          <p className="upload-filename">Identificação: {data.order_id}</p>
          <p role="status">Status: {statusLabel(data.status)}</p>
          <dl className="order-counts">
            <dt>Seguidores no arquivo</dt><dd>{count(data.followers)}</dd>
            <dt>Seguindo no arquivo</dt><dd>{count(data.following)}</dd>
            {Object.entries(data.profiles_by_status || {}).map(([status, value]) =>
              <div key={status}><dt>{statusLabel(status)}</dt><dd>{count(value)}</dd></div>)}
          </dl>
          {["queued", "processing"].includes(data.status) && <p>O pedido está em andamento. Use “Atualizar pedido” para acompanhar. Os downloads disponíveis representam os dados atuais e podem estar incompletos.</p>}
          <p className="muted">O enriquecimento real ainda não está disponível. Os arquivos contêm os dados da exportação enviada.</p>
          <section aria-labelledby="order-downloads">
            <h2 id="order-downloads">Baixar arquivos</h2>
            <div className="orders-actions">
              {[["export.csv", "CSV", "backup_enriquecido.csv"], ["export.xlsx", "XLSX", "backup_enriquecido.xlsx"], ["report", "relatório JSON", `relatorio-${data.order_id}.json`]].map(([suffix, label, filename]) =>
                <button key={suffix} disabled={loading || !!downloading || !!error} onClick={() => save(suffix, filename)}>
                  {downloading === suffix ? "Baixando…" : `Baixar ${label}`}
                </button>)}
            </div>
            <p role="status">{downloading ? "Preparando o arquivo para download…" : downloadNotice}</p>
          </section>
          <section aria-labelledby="order-preview">
            <h2 id="order-preview">Prévia dos perfis</h2>
            <p>A prévia paginada ainda não está disponível nesta versão. Você pode consultar os perfis nas planilhas CSV e XLSX.</p>
          </section>
        </>}
      </div>
    </main>
  );
}
