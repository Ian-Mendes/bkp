FROM node:20-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm install --no-audit --no-fund

# Etapa de dev: servidor do Vite com hot reload (usada via docker-compose.override.yml)
FROM deps AS dev
CMD ["npm", "run", "dev"]

# Etapa de build: gera dist/
FROM deps AS build
COPY . .
RUN npm run build

# Etapa de serviço: caddy serve os estáticos e encaminha /api ao backend
FROM caddy:alpine
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv
EXPOSE 80 443
