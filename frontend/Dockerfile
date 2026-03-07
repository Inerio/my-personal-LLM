FROM node:20-alpine AS build

WORKDIR /app

# Installer les dépendances
COPY package.json package-lock.json* ./
RUN npm install

# Copier le code source
COPY . .

# Build de production
RUN npm run build

# Serveur de production avec nginx
FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html

# Configuration nginx pour SPA (toutes les routes vers index.html)
RUN echo 'server { \
    listen 3000; \
    root /usr/share/nginx/html; \
    index index.html; \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
