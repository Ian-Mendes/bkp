import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";

export default function Landing() {
  const navigate = useNavigate();
  const [logado, setLogado] = useState(null); // null = checando, true/false = sabe

  useEffect(() => {
    // Sem token no JS: pergunta ao backend se o cookie de sessão está vivo.
    // Deslogado, o backend devolve 401 e o usuário vê os CTAs de login.
    api("/auth/me")
      .then(() => setLogado(true))
      .catch(() => setLogado(false));
  }, []);

  // Um CTA só para não repetir a lógica em dois lugares.
  const ctaDestino = logado ? "/dashboard" : "/login";

  return (
    <div className="landing">
      <header className="landing-header">
        <div className="landing-header-inner">
          <span className="landing-logo">BKP</span>
          <nav className="landing-nav">
            {logado === true ? (
              <button className="btn-hero" onClick={() => navigate("/dashboard")}>
                Ir para o app
              </button>
            ) : (
              <>
                <button className="btn-ghost" onClick={() => navigate("/login")}>
                  Entrar
                </button>
                <button className="btn-hero" onClick={() => navigate("/login")}>
                  Criar conta
                </button>
              </>
            )}
          </nav>
        </div>
      </header>

      <section className="hero">
        <span className="hero-badge">Nunca pedimos sua senha do Instagram</span>
        <h1>Sua rede não pode desaparecer da noite para o dia.</h1>
        <p>
          Backup enriquecido do Instagram para contas que precisam continuar de
          pé. Exporte, processe, guarde — em CSV ou XLSX, do jeito que você
          quiser.
        </p>
        <div className="hero-cta">
          <button className="btn-hero" onClick={() => navigate(ctaDestino)}>
            Criar backup agora
          </button>
          <button
            className="btn-ghost"
            onClick={() =>
              document.getElementById("como-funciona")?.scrollIntoView({ behavior: "smooth" })
            }
          >
            Como funciona
          </button>
        </div>
      </section>

      <section className="landing-section landing-section--gray">
        <div className="landing-section-inner">
          <h2>O risco é real</h2>
          <p className="landing-lead">
            Três coisas que acontecem com contas que não têm backup.
          </p>
          <div className="grid-3">
            <div className="feature">
              <h3>Contas derrubadas</h3>
              <p>
                Perdem seguidores, seguindo e bio. Sem aviso, sem volta.
              </p>
            </div>
            <div className="feature">
              <h3>Shadow ban</h3>
              <p>
                Alcance cai silenciosamente. Você não vê, mas a rede some.
              </p>
            </div>
            <div className="feature">
              <h3>Takeout confuso</h3>
              <p>
                A exportação oficial é confusa e vem em formatos que ninguém
                abre.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section id="como-funciona" className="landing-section">
        <h2>Como funciona</h2>
        <p className="landing-lead">
          Quatro passos. Cinco minutos. Sem senha do Instagram.
        </p>
        <ol className="steps">
          <li className="step">
            <span className="step-num">1</span>
            <div>
              <h3>Exporte do Instagram</h3>
              <p>
                Use o Takeout oficial. Escolha apenas "Seguidores e seguindo".
                O link está no final desta página.
              </p>
            </div>
          </li>
          <li className="step">
            <span className="step-num">2</span>
            <div>
              <h3>Suba o arquivo</h3>
              <p>
                Só o ZIP. A gente lê o que interessa e apaga o resto logo
                depois.
              </p>
            </div>
          </li>
          <li className="step">
            <span className="step-num">3</span>
            <div>
              <h3>Enriqueça os perfis</h3>
              <p>
                Dados públicos: seguidores, seguindo, bio. Nada de conteúdo
                privado.
              </p>
            </div>
          </li>
          <li className="step">
            <span className="step-num">4</span>
            <div>
              <h3>Baixe sua planilha</h3>
              <p>
                CSV ou XLSX, pronta para Excel, Google Sheets ou Numbers.
              </p>
            </div>
          </li>
        </ol>
      </section>

      <section className="landing-section landing-section--gray">
        <div className="landing-section-inner">
          <h2>Privacidade em primeiro lugar</h2>
          <ul className="privacy-list">
            <li>❌ Nunca pedimos sua senha do Instagram.</li>
            <li>✅ Seu arquivo é apagado depois de processado.</li>
            <li>✅ Retenção de 30 dias, ou até você excluir.</li>
            <li>✅ Você pode apagar tudo a qualquer momento.</li>
            <li>✅ Segue a LGPD (ANPD).</li>
          </ul>
        </div>
      </section>

      <section className="cta-final">
        <h2>Comece seu backup agora. Leva 5 minutos.</h2>
        <button className="btn-hero" onClick={() => navigate(ctaDestino)}>
          {logado ? "Ir para o app" : "Criar conta"}
        </button>
      </section>

      <footer className="landing-footer">
        <div className="landing-footer-inner">
          <span>BKP — backup enriquecido do Instagram</span>
          <nav>
            <a
              href="https://accountscenter.instagram.com/info_and_permissions/dyi/"
              target="_blank"
              rel="noreferrer"
            >
              Takeout do Instagram
            </a>
            <a
              href="https://www.gov.br/anpd/pt-br"
              target="_blank"
              rel="noreferrer"
            >
              LGPD
            </a>
            <a
              href="https://github.com/Ian-Mendes/bkp"
              target="_blank"
              rel="noreferrer"
            >
              GitHub
            </a>
          </nav>
        </div>
      </footer>
    </div>
  );
}


