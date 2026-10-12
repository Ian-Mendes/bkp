# AGENTS.md — Frontend

Complementa o `AGENTS.md` raiz.

## Stack

Vite 5 + React 18 + react-router-dom. JavaScript puro (sem TypeScript). Sem lib
de estado, UI kit ou testes. Node 20; dev na porta 3000.

## Regras de ouro

- Comentários/docs em pt-BR; identificadores em inglês. Textos de UI em pt-BR.
- Auth de rota: `getToken()` + `useNavigate` (padrão em `src/pages/Dashboard.jsx`).
- Nunca fixe a origem da API — use `lib/api.js` com `/api` (mesma origem).
- Código enxuto; funções curtas; sem CSS-in-JS.

## Estrutura (obrigatória)

- Rotas declaradas em `src/App.jsx` (react-router); uma página por arquivo em
  `src/pages/*.jsx`; entrypoint em `src/main.jsx`.
- Reuse as classes de `src/index.css`: `center`, `card`, `sub`, `error`,
  `notice`, `switch`, `link`, `out`.
- Não crie arquivo/rota novos se um existente resolve; siga o padrão das páginas de auth.

## API (`src/lib/api.js`)

- `api(path, { method, body, auth })` envia JSON e lança `Error` com `.status`.
- `download(path)` baixa arquivo (CSV/XLSX) e dispara o salvamento.
- Token em `localStorage`, chave `bkp_token`. Base fixa `/api`, encaminhada pelo
  proxy (Vite em dev, Caddy em prod) — sem CORS.

## Comandos

```bash
docker compose up -d --build frontend
npm run dev       # vite (hot reload, porta 3000)
npm run build     # vite build -> dist/
npm run preview   # serve a build localmente
```

## Convenções

- Formulários: `useState` para campos/erro/loading; validação no cliente; erro em
  `<div className="error" role="alert">`.
- Erros da API chegam em pt-BR do backend — exiba `err.message`.
- CSP em produção fica no `Caddyfile` (não há `next.config.js`); em dev o Vite
  faz o proxy de `/api`.

## Pendências

- Upload de ZIP (`POST /orders`, multipart); lista/detalhe/start/delete de
  pedidos; downloads (`/report`, `/export.csv`, `/export.xlsx`); substituir o
  placeholder `src/pages/Dashboard.jsx`.

## Pronto quando

Páginas com texto pt-BR, requests via `lib/api.js` e build OK
(`docker compose up -d --build frontend`). Não há suíte de testes no frontend.
