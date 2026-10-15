import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { authenticatedApi, logout as apiLogout } from "../lib/api";

function uploadError(err) {
  if (err.status === 401) return "Sua sessão expirou. Entre novamente para enviar o arquivo.";
  if (err.status === 403) return "Sua conta não tem acesso ao envio. Confira a confirmação do seu e-mail.";
  if (err.status >= 500) return "O servidor não conseguiu concluir o envio. Tente novamente mais tarde.";
  if (!err.status) return "A conexão falhou. O pedido pode ter sido recebido; confira antes de reenviar.";
  return err.message;
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [maxBytes, setMaxBytes] = useState(null);
  const [file, setFile] = useState(null);
  const [error, setError] = useState("");
  const [expired, setExpired] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [order, setOrder] = useState(null);
  const input = useRef(null);
  const chooser = useRef(null);
  const pending = useRef(false);
  const result = useRef(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const u = await authenticatedApi("/auth/me");
        if (active) setUser(u);
        const config = await authenticatedApi("/orders/upload-config");
        if (active) setMaxBytes(config.max_upload_bytes);
      } catch (err) {
        if (!active) return;
        if (err.status === 401) navigate("/login", { replace: true });
        else setError("Não foi possível carregar os dados do envio. Recarregue a página para tentar novamente.");
      }
    }
    load();
    return () => { active = false; };
  }, [navigate]);

  useEffect(() => {
    if (order) result.current?.focus();
  }, [order]);

  function selectFiles(files) {
    if (pending.current) return;
    setDragging(false);
    setError("");
    if (files.length !== 1) {
      setError("Selecione apenas um arquivo ZIP por envio.");
      return;
    }
    const selected = files[0];
    if (!/\.zip$/i.test(selected.name)) {
      setError("Formato inválido. Escolha o ZIP original exportado pelo Instagram.");
      return;
    }
    if (!selected.size) {
      setError("O arquivo está vazio. Baixe novamente a exportação.");
      return;
    }
    if (!maxBytes || selected.size > maxBytes) {
      setError(maxBytes ? `O arquivo excede o limite de ${maxBytes / 1024 / 1024} MB. Exporte apenas seguidores e seguindo.` : "Aguarde o carregamento do limite de envio.");
      return;
    }
    setFile(selected);
    setOrder(null);
  }

  async function submit(event) {
    event.preventDefault();
    if (pending.current || !file || !maxBytes || expired) return;
    pending.current = true;
    setBusy(true);
    setError("");
    setOrder(null);
    const body = new FormData();
    body.append("file", file);
    try {
      const created = await authenticatedApi("/orders", { method: "POST", body });
      setOrder(created);
      setFile(null);
    } catch (err) {
      setError(uploadError(err));
      setExpired(err.status === 401);
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }

  async function logout() {
    if (pending.current) return;
    pending.current = true;
    setLoggingOut(true);
    setError("");
    try {
      await apiLogout();
      navigate("/login", { replace: true });
    } catch {
      setError("Não foi possível encerrar sua sessão. Tente sair novamente.");
    } finally {
      pending.current = false;
      setLoggingOut(false);
    }
  }

  return (
    <main className="center">
      <div className="card upload-card">
        <h1>Envie sua exportação do Instagram</h1>
        {user && <p className="sub">Logado como {user.email}</p>}
        <details className="upload-guide" open>
          <summary>Como obter seu ZIP</summary>
          <ol>
            <li>No Instagram, abra as configurações e a Central de Contas da Meta. Localize a opção de baixar ou exportar suas informações e selecione seu perfil do Instagram.</li>
            <li>Solicite uma exportação para baixar no dispositivo, contendo apenas seguidores e seguindo.</li>
            <li>Para obter a lista mais completa, escolha todo o período. Recomendamos JSON, que permite analisar datas; HTML também é aceito pelo BKP.</li>
            <li>Quando a Meta avisar que o arquivo está pronto, volte à área de exportações e baixe o ZIP. Envie o arquivo original aqui, sem descompactar.</li>
          </ol>
          <p>Os nomes dos controles podem variar. Consulte a <a href="https://www.facebook.com/help/instagram/181231772500920" target="_blank" rel="noreferrer">ajuda oficial do Instagram</a>.</p>
          <p>O BKP nunca solicita login, senha ou código de acesso do Instagram. O MVP organiza os dados exportados; o enriquecimento real ainda não está disponível.</p>
        </details>
        <form onSubmit={submit} aria-busy={busy}>
          <fieldset disabled={busy || loggingOut || !maxBytes || expired} className="upload-fields">
            <legend>Arquivo da exportação</legend>
            <div className={`upload-drop${dragging ? " is-dragging" : ""}`}
              onDragOver={(event) => { event.preventDefault(); if (!pending.current) setDragging(true); }}
              onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setDragging(false); }}
              onDrop={(event) => { event.preventDefault(); if (maxBytes && !expired) selectFiles(event.dataTransfer.files); }}>
              <p id="upload-help">Arraste um único ZIP para esta área ou use o botão abaixo.</p>
              <p className="muted">{maxBytes ? `Limite: ${maxBytes / 1024 / 1024} MB por arquivo.` : "Carregando o limite de envio…"}</p>
              <input ref={input} type="file" id="upload-file" accept=".zip,application/zip,application/x-zip-compressed" hidden
                onChange={(event) => { if (event.target.files.length) selectFiles(event.target.files); event.target.value = ""; }} />
              <button ref={chooser} type="button" aria-describedby="upload-help" onClick={() => input.current.click()}>{file ? "Substituir ZIP" : "Selecionar ZIP"}</button>
            </div>
            <div aria-live="polite">
              {file && <p className="upload-filename">{file.name} — {file.size.toLocaleString("pt-BR")} bytes ({(file.size / 1024 / 1024).toLocaleString("pt-BR", { maximumFractionDigits: 2 })} MB)</p>}
            </div>
            {file && <button type="button" className="link" onClick={() => { setFile(null); setError(""); chooser.current.focus(); }}>Remover arquivo</button>}
            <button type="submit" disabled={!file} className="upload-submit">{busy ? "Enviando…" : "Enviar exportação"}</button>
          </fieldset>
        </form>
        <div role="status">
          {busy && <p>Enviando o arquivo e aguardando a análise do servidor. A transferência e a análise são etapas diferentes; esta conexão não informa quando a transferência termina.</p>}
        </div>
        {error && <div className="error" role="alert">{error} {expired && <Link to="/login">Entrar novamente</Link>}</div>}
        {order && <section className="notice" tabIndex={-1} ref={result} aria-labelledby="upload-success">
          <h2 id="upload-success">Exportação recebida</h2>
          <p className="upload-filename">Pedido: {order.order_id}</p>
          <p>{order.followers} seguidores e {order.following} perfis seguindo. Entradas inválidas: {order.invalid}. Duplicatas removidas: {order.duplicates}.</p>
          <p>Estado do pedido: {order.status === "parsed" ? "analisado" : order.status}. O recebimento não conclui o enriquecimento, que é uma etapa separada. No MVP, o provider não consulta novos dados.</p>
          {order.warnings?.length > 0 && <p>A análise apontou possíveis lacunas na exportação. Confira se você incluiu seguidores e seguindo de todo o período.</p>}
        </section>}
        {user && <div className="dashboard-actions">
          <button id="out" className="out" disabled={busy || loggingOut} onClick={logout}>{loggingOut ? "Saindo…" : "Sair"}</button>
        </div>}
      </div>
    </main>
  );
}
