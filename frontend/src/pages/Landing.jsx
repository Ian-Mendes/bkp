import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";

export default function Landing() {
  const navigate = useNavigate();
  const [logado, setLogado] = useState(null);

  useEffect(() => {
    api("/auth/me")
      .then(() => setLogado(true))
      .catch(() => setLogado(false));
  }, []);

  const ctaDestino = logado ? "/dashboard" : "/login";

  return (
    <div className="landing">
      <header className="landing-header">
        <div className="landing-header-inner">
          <span className="landing-logo">
            <span className="bracket">[</span> INSTA BKP <span className="bracket">]</span>
          </span>
          <nav className="landing-nav">
            {logado === true ? (
              <button className="btn-accent" onClick={() => navigate("/dashboard")}>
                Ir para o app
              </button>
            ) : (
              <button className="btn-accent" onClick={() => navigate("/login")}>
                Entrar
              </button>
            )}
          </nav>
        </div>
      </header>

      {/* ============ SESSÃO 1 — hero de largura total ============ */}
      <section className="session session-1">
        <div className="session-inner">
          <span className="kicker">A única solução de backup completo do seu Instagram</span>
          <h1>
            Sua rede não pode <span className="accent">desaparecer</span> da
            noite para o dia.
          </h1>
          <p>
            Você construiu sua audiência. Não deixe que decisões arbitrárias
            de plataforma apaguem isso de uma vez. Tenha controle sobre seus
            dados antes que seja tarde.
          </p>
          <div className="hero-cta">
            <button className="btn-accent" onClick={() => navigate(ctaDestino)}>
              {logado ? "Ir para o app" : "Entrar"}
            </button>
          </div>
        </div>
      </section>

      {/* ============ SESSÃO 2 — por que agora ============ */}
      <section className="session session-2">
        <div className="session-inner">
          <h2>Por que isso importa agora</h2>
          <p className="lead">
            As regras mudam sem aviso. O que é seu não pode ficar refém de
            uma decisão que não é sua.
          </p>
          <div className="facts">
            <div className="fact">
              <span className="fact-num">01</span>
              <h3>Plataformas mudam de uma hora para outra</h3>
              <p>
                Contas caem, alcance cai, políticas mudam. Sem uma cópia por
                perto, você perde anos de trabalho em uma tarde.
              </p>
            </div>
            <div className="fact">
              <span className="fact-num">02</span>
              <h3>Seus seguidores são o seu ativo</h3>
              <p>
                Não são só números. É a sua rede, o seu público, o seu
                trabalho. Isso vale mais do que o aplicativo quer admitir.
              </p>
            </div>
            <div className="fact">
              <span className="fact-num">03</span>
              <h3>Você merece a sua própria base</h3>
              <p>
                Ter os seus dados organizados do seu jeito muda como você
                trabalha. É a diferença entre depender e decidir.
              </p>
            </div>
            <div className="fact">
              <span className="fact-num">04</span>
              <h3>Autonomia não se improvisa</h3>
              <p>
                Quem constrói a própria base constrói a própria voz. Quem
                espera pelo bloqueio já perdeu tempo.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ============ SESSÃO 3 — como funciona, fluxo geral ============ */}
      <section id="como-funciona" className="session session-3">
        <div className="session-inner">
          <h2>Como funciona</h2>
          <p className="lead">
            Sem senha, sem burocracia. Um caminho direto entre você e a sua
            base.
          </p>
          <div className="facts">
            <div className="fact">
              <span className="fact-num">01</span>
              <h3>Você solicita à plataforma</h3>
              <p>
                Um pedido simples, feito por você, no seu tempo.
              </p>
            </div>
            <div className="fact">
              <span className="fact-num">02</span>
              <h3>Você nos envia com segurança</h3>
              <p>
                Confidencialidade do começo ao fim. Nada sai do seu controle.
              </p>
            </div>
            <div className="fact">
              <span className="fact-num">03</span>
              <h3>A gente organiza e valida</h3>
              <p>
                Tratamos os dados com cuidado e devolvemos tudo pronto para
                usar.
              </p>
            </div>
            <div className="fact">
              <span className="fact-num">04</span>
              <h3>Você recebe a sua base</h3>
              <p>
                A sua rede, do seu jeito, no seu controle. Pronta para o que
                vier.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ============ SESSÃO 4 — o que você recebe ============ */}
      <section className="session session-4">
        <div className="session-inner">
          <h2>O que você recebe</h2>
          <p className="lead">
            Cada perfil da sua rede, com o que importa, pronto para filtrar e
            acionar.
          </p>
          <div className="facts">
            <div className="fact">
              <span className="fact-num">👤</span>
              <h3>Usuário</h3>
              <p>O nome de cada perfil da sua rede, sem repetição.</p>
            </div>
            <div className="fact">
              <span className="fact-num">📈</span>
              <h3>Alcance</h3>
              <p>Quem tem mais seguidores, pronto para ordenar.</p>
            </div>
            <div className="fact">
              <span className="fact-num">📝</span>
              <h3>Bio</h3>
              <p>O que cada perfil diz sobre si, para segmentar.</p>
            </div>
            <div className="fact">
              <span className="fact-num">🔗</span>
              <h3>Link</h3>
              <p>Quando houver, o endereço que cada perfil aponta.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ============ SESSÃO 5 — privacidade ============ */}
      <section className="session session-5">
        <div className="session-inner">
          <h2>Privacidade em primeiro lugar</h2>
          <p className="lead">
            Isso começa pelo que a gente se recusa a fazer.
          </p>
          <div className="privacy-grid">
            <div className="privacy-item is-danger">
              <span className="mark">❌</span>
              <h3>Nunca pedimos sua senha</h3>
              <p>
                Em momento nenhum a gente pede sua senha ou seu código. Se
                alguém pedir em nome do BKP, é golpe.
              </p>
            </div>
            <div className="privacy-item is-good">
              <span className="mark">🗑️</span>
              <h3>O que você envia é descartado</h3>
              <p>
                Assim que a sua base está pronta, o material enviado deixa de
                existir. Sem cópias, sem uso paralelo.
              </p>
            </div>
            <div className="privacy-item is-warm">
              <span className="mark">⏳</span>
              <h3>Você decide por quanto tempo</h3>
              <p>
                A sua base fica disponível enquanto você quiser usá-la. Não
                quer mais? É só apagar.
              </p>
            </div>
            <div className="privacy-item is-info">
              <span className="mark">🛡️</span>
              <h3>Feito pensando na LGPD</h3>
              <p>
                Cada conta vê apenas o que é seu. Nada é compartilhado, nada
                é vendido.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ============ CTA final ============ */}
      <section className="session cta-final">
        <div className="session-inner">
          <h2>Não espere o bloqueio para valorizar o que é seu.</h2>
          <p>Leva cinco minutos. Não precisa entender de tecnologia.</p>
          <div className="hero-cta">
            <button className="btn-accent" onClick={() => navigate(ctaDestino)}>
              {logado ? "Ir para o app" : "Entrar"}
            </button>
          </div>
        </div>
      </section>

      <footer className="landing-footer">
        <span>INSTA BKP — backup enriquecido do Instagram</span>
        <nav>
          <a
            href="https://accountscenter.instagram.com/info_and_permissions/dyi/"
            target="_blank"
            rel="noreferrer"
          >
            Solicitar seus dados
          </a>
          <a href="https://www.gov.br/anpd/pt-br" target="_blank" rel="noreferrer">
            LGPD
          </a>
          <a href="https://github.com/Ian-Mendes/bkp" target="_blank" rel="noreferrer">
            GitHub
          </a>
        </nav>
      </footer>
    </div>
  );
}
