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

# Etapa de serviço: nginx serve os estáticos e encaminha /api ao backend
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
