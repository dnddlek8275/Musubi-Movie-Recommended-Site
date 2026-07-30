FROM node:22-alpine AS build

WORKDIR /app

ARG VITE_API_BASE_URL=http://127.0.0.1:8080
ARG VITE_TMDB_IMAGE_BASE_URL=https://image.tmdb.org/t/p/w500

ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_TMDB_IMAGE_BASE_URL=$VITE_TMDB_IMAGE_BASE_URL

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
