FROM node:22-alpine AS build

WORKDIR /app

ARG VITE_API_BASE_URL=/api
ARG VITE_TMDB_IMAGE_BASE_URL=https://image.tmdb.org/t/p/w500
ARG VITE_TTS_BASE_URL=http://127.0.0.1:5001
ARG VITE_TTS_ENABLED=false

ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_TMDB_IMAGE_BASE_URL=$VITE_TMDB_IMAGE_BASE_URL
ENV VITE_TTS_BASE_URL=$VITE_TTS_BASE_URL
ENV VITE_TTS_ENABLED=$VITE_TTS_ENABLED

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
RUN chmod -R a+rX /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
