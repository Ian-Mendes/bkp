import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { authenticatedApi, download, logout as apiLogout } from "../lib/api";
import { orderStatusInfo } from "../lib/orders";

export default function Orders() {
  const navigate = useNavigate();
  const [orders, setOrders] = useState(null);
  const [error, setError] = useState("");
  const [loggingOut, setLoggingOut] = useState(false);
  const [downloadingId, setDownloadingId] = useState(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const data = await authenticatedApi("/orders");
        if (active) setOrders(data);
      } catch (err) {
        if (!active) return;
        if (err.status === 401) navigate("/login", { replace: true });
        else setError(err.message);
      }
    })();
    return () => {
      active = false;
    };
  }, [navigate]);

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

  async function handleDownload(orderId, ext) {
    setDownloadingId(orderId);
    setError("");
    try {
      await download(`/orders/${orderId}/export.${ext}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setDownloadingId(null);
    }
  }

  return (
    <main className="app-page">
      <header className="app-topbar">
        <h1>Meus pedidos</h1>
        <nav className="app-nav">
          <Link to="/dashboard" className="link">Novo backup</Link>
          <button className="out" onClick={logout} disabled={loggingOut}>
            {loggingOut ? "Saindo…" : "Sair"}
          </button>
        </nav>
      </header>

      {error && <div className="error" role="alert">{error}</div>}
      {!orders && !error && <p className="muted">Carregando…</p>}

      {orders && orders.length === 0 && (
        <section className="panel">
          <p className="muted">Você ainda não enviou nenhuma exportação.</p>
          <p><Link to="/dashboard">Enviar meu primeiro backup</Link></p>
        </section>
      )}

      {orders && orders.length > 0 && (
        <section className="panel">
          <ul className="orders-list">
            {orders.map((o) => {
              const st = orderStatusInfo(o.status);
              return (
                <li key={o.order_id} className="order-row">
                  <div className="order-main">
                    <Link to={`/orders/${o.order_id}`} className="order-link">
                      Pedido {o.order_id}
                    </Link>
                    <div className="muted">
                      {o.followers} seguidores · {o.following} seguindo ·{" "}
                      criado em {new Date(o.created_at).toLocaleDateString("pt-BR")}
                    </div>
                  </div>
                  <span className={`order-status ${st.cls}`}>{st.text}</span>
                  <Link to={`/orders/${o.order_id}`} className="link">Ver prévia</Link>
                  {o.status === "done" && (
                    <div className="row-downloads" aria-label="Baixar relatório">
                      <button
                        className="link"
                        disabled={downloadingId === o.order_id}
                        onClick={() => handleDownload(o.order_id, "csv")}
                      >
                        {downloadingId === o.order_id ? "Baixando…" : "CSV"}
                      </button>
                      <button
                        className="link"
                        disabled={downloadingId === o.order_id}
                        onClick={() => handleDownload(o.order_id, "xlsx")}
                      >
                        {downloadingId === o.order_id ? "Baixando…" : "XLSX"}
                      </button>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </main>
  );
}
