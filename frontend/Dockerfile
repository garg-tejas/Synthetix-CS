FROM node:20-slim

WORKDIR /app

# Install pnpm
RUN corepack enable && corepack prepare pnpm@latest --activate

# Copy package files
COPY package.json pnpm-lock.yaml ./
RUN pnpm install

# Copy source and build
COPY . .
RUN pnpm build

# Serve with a static file server
RUN pnpm add -g serve
EXPOSE 5173
CMD ["serve", "-s", "dist", "-l", "5173"]
