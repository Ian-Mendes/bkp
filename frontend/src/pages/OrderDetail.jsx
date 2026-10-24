import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { authenticatedApi, download, logout as apiLogout } from "../lib/api";
import { orderStatusInfo, profileStatusInfo, RELATION_LABELS } from "../lib/orders";

const PAGE_SIZE = 50;

export default function OrderDetail() {
  const { orderId } = useParams();
  const navigate = useNavigate();

  const [order, setOrder] = useState(null);
  const [profiles, setProfiles] = useState([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [tipo, setTipo] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [q, setQ] = useState("");
  const [error, setError] = useState("");
  const [downloading, setDownloading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);

  const loadOrder = useCallback(async () => {
    try {
      const data = await authenticatedApi(`/orders/${orderId}`);
      setOrder(data);
      setError("");
      return data;
    } catch (err) {
      if (err.status === 401) navigate("/login", { replace: true });
      else setError(err.message);
      return null;
    }
  }, [orderId, navigate]);

  // Carrega o pedido e, enquanto estiver em processamento, acompanha até concluir.
  useEffect(() => {
    let active = true;
    let timer = null;
    async function refresh() {
      const o = await loadOrder();
      if (!active || !o) return;
      if (o.status === "queued" || o.status === "processing") {
        timer = setTimeout(refresh, 3000);
      }
    }
    refresh();
    return () => {
      active = false;
      if (timer) clearTimeout(timer);
    };
  }, [loadOrder, order?.status]);

  // Carrega a página de perfis (refaz quando offset/tipo/q/mudança de status mudam).
  useEffect(() => {
    let active = true;
    async function loadProfiles() {
      try {
        const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
        if (tipo) params.set("tipo", tipo);
        if (q) params.set("q", q);
        const data = await authenticatedApi(`/orders/${orderId}/profiles?${params}`);
        if (!active) return;
        setProfiles(data.profiles);
        setTotal(data.total);
      } catch (err) {
        if (!active) return;
        if (err.status === 401) navigate("/login", { replace: true });
        else setError(err.message);
      }
    }
    loadProfiles();
    return () => {
      active = false;
    };
  }, [orderId, offset, tipo, q, navigate, order?.status]);

  async function start() {
    setStarting(true);
    setError("");
    try {
      await authenticatedApi(`/orders/${orderId}/start`, { method: "POST" });
      await loadOrder();
    } catch (err) {
      setError(err.message);
    } finally {
      setStarting(false);
    }
  }

  async function handleDownload(ext) {
    setDownloading(true);
    setError("");
    try {
      await download(`/orders/${orderId}/export.${ext}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setDownloading(false);
    }
  }

  async function logout() {
    setLoggingOut(true);
    setError("");
    try {
      await apiLogout();
      navigate("/login", { replace: true });
    } catch {
      setError("Não foi possível encerrar sua sessão.");
      setLoggingOut(false);
    }
  }

  const done = order?.status === "done";
  const ongoing = order && (order.status === "queued" || order.status === "processing");
  const canStart = order && (order.status === "parsed" || order.status === "failed");
  const byStatus = order?.profiles_by_status || {};
  const totalUnique = Object.values(byStatus).reduce((a, b) => a + b, 0);
  const enrichedCount = byStatus.ok || 0;

  return (
    <main className="app-page">
      <header className="app-topbar">
        <h1>Prévia do pedido</h1>
        <nav className="app-nav">
          <Link to="/orders" className="link">Meus pedidos</Link>
          <button className="out" onClick={logout} disabled={loggingOut}>
            {loggingOut ? "Saindo…" : "Sair"}
          </button>
        </nav>
      </header>

      {error && <div className="error" role="alert">{error}</div>}
      {!order && !error && <p className="muted">Carregando…</p>}

      {order && (
        <section className="panel">
          <div className="order-head">
            <h2>Pedido <span className="order-id">{order.order_id}</span></h2>
            <span className={`order-status ${orderStatusInfo(order.status).cls}`}>
              {orderStatusInfo(order.status).text}
            </span>
          </div>

          <div className="summary-grid">
            <div className="summary-item">
              <div className="num">{order.followers}</div>
              <div className="label">Seguidores</div>
            </div>
            <div className="summary-item">
              <div className="num">{order.following}</div>
              <div className="label">Seguindo</div>
            </div>
            <div className="summary-item">
              <div className="num">{totalUnique}</div>
              <div className="label">Perfis únicos</div>
            </div>
            <div className="summary-item">
              <div className="num">{enrichedCount}</div>
              <div className="label">Enriquecidos</div>
            </div>
          </div>

          {ongoing && (
            <p className="notice" role="status">
              O enriquecimento está em andamento. Esta página atualiza automaticamente.
            </p>
          )}

          <div className="download-bar">
            {canStart && (
              <button className="btn-sm" onClick={start} disabled={starting}>
                {starting ? "Iniciando…" : "Iniciar enriquecimento"}
              </button>
            )}
            <button className="btn-sm" onClick={() => handleDownload("csv")} disabled={!done || downloading}>
              {downloading ? "Baixando…" : "Baixar CSV"}
            </button>
            <button className="btn-sm" onClick={() => handleDownload("xlsx")} disabled={!done || downloading}>
              {downloading ? "Baixando…" : "Baixar XLSX"}
            </button>
            {!done && <span className="hint">O download libera quando o relatório estiver concluído.</span>}
          </div>
        </section>
      )}

      {order && (
        <section className="panel">
          <h2>Perfis relacionados</h2>
          <form
            className="filters"
            onSubmit={(e) => {
              e.preventDefault();
              setOffset(0);
              setQ(searchInput);
            }}
          >
            <select
              value={tipo}
              onChange={(e) => {
                setTipo(e.target.value);
                setOffset(0);
              }}
              aria-label="Filtrar por relação"
            >
              <option value="">Todos</option>
              <option value="seguidor">Segue você</option>
              <option value="seguindo">Você segue</option>
              <option value="ambos">Mútuo</option>
            </select>
            <input
              type="search"
              placeholder="Buscar por bio…"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
            />
            <button type="submit" className="btn-sm">Buscar</button>
          </form>

          {profiles.length === 0 ? (
            <p className="muted">Nenhum perfil encontrado.</p>
          ) : (
            <ul className="profile-list">
              {profiles.map((p) => {
                const ps = profileStatusInfo(p.status);
                return (
                  <li key={p.username} className="profile-row">
                    <div className="profile-head">
                      <span className="profile-username">
                        {p.full_name ? `${p.full_name} (@${p.username})` : `@${p.username}`}
                      </span>
                      {p.is_verified && <span className="badge badge-info">Verificado</span>}
                      {p.is_business && <span className="badge badge-muted">Comercial</span>}
                      {p.tipo && (
                        <span className={`badge badge-rel-${p.tipo}`}>
                          {RELATION_LABELS[p.tipo] || p.tipo}
                        </span>
                      )}
                      <span className={`badge badge-${ps.tone}`}>{ps.text}</span>
                      <span className="profile-stats">
                        seguidores {p.followers_count ?? "∅"} · seguindo {p.following_count ?? "∅"} · posts {p.posts_count ?? "∅"}
                      </span>
                    </div>
                    {(p.bio || p.category || p.profile_url || p.external_url || p.profile_pic_url) && (
                      <div className="profile-detail">
                        {p.category && <span className="profile-category">{p.category}</span>}
                        {p.bio && <p className="profile-bio">{p.bio}</p>}
                        {p.profile_url && (
                          <a className="profile-link" href={p.profile_url} target="_blank" rel="noreferrer">{p.profile_url}</a>
                        )}
                        {p.external_url && (
                          <a className="profile-link" href={p.external_url} target="_blank" rel="noreferrer">{p.external_url}</a>
                        )}
                        {p.profile_pic_url && (
                          <a className="profile-link" href={p.profile_pic_url} target="_blank" rel="noreferrer">Foto do perfil</a>
                        )}
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}

          {total > 0 && (
            <div className="pager">
              <button className="link" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
                ← Anterior
              </button>
              <span className="muted">
                {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} de {total}
              </span>
              <button className="link" disabled={offset + PAGE_SIZE >= total} onClick={() => setOffset(offset + PAGE_SIZE)}>
                Próxima →
              </button>
            </div>
          )}
        </section>
      )}
    </main>
  );
}
