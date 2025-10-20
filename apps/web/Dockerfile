# Web Dockerfile (Next.js 15)
FROM node:22-alpine AS deps
WORKDIR /app
COPY package*.json ./
# Prefer npm ci if lockfile exists; fallback to npm install
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Build
RUN npm run build

FROM node:22-alpine AS runner
ENV NODE_ENV=production
WORKDIR /app
COPY --from=builder /app ./
EXPOSE 3000
# Ensure start script exists; otherwise fallback to next start
CMD ["npm", "start"]
