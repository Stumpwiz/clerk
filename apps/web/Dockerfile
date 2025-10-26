# ---- deps: install node_modules once, cached by lockfile
FROM node:22-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

# ---- build: copy source and build Next.js
FROM node:22-alpine AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
ARG NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_dummy
ENV NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY}

COPY --from=deps /app/node_modules ./node_modules
COPY . .

ENV NODE_ENV=production
# (Optional) quick diag to ensure the proxy route is present in context
RUN ls -la app/api/proxy || true

RUN npm run build

# ---- runner: non-standalone (copies full app + .next + node_modules)
FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000

# Copy everything the Next server needs at runtime
COPY --from=build /app /app

EXPOSE 3000
CMD ["npm","run","start"]
