# Stage 1: Build Vite React application
FROM node:20-alpine AS builder

WORKDIR /app

ENV PNPM_CONFIG_MINIMUM_RELEASE_AGE=0
ENV PNPM_CONFIG_NODE_LINKER=hoisted

# Enable stable pnpm 9
RUN corepack enable && corepack prepare pnpm@9 --activate || npm install -g pnpm@9

# Copy package descriptors and install with hoisted linker for clean TypeScript resolution
COPY frontend/.npmrc* frontend/package.json frontend/pnpm-lock.yaml* ./
RUN pnpm config set node-linker hoisted && \
    pnpm install

# Copy source files (excluding node_modules via .dockerignore)
COPY frontend/ ./
RUN pnpm run build

# Stage 2: Serve via Nginx
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
