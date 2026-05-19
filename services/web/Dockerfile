# Multi-stage Next.js Dockerfile (production-ready, standalone output).
# --- deps stage ---
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json ./
RUN npm install --omit=dev=false --legacy-peer-deps

# --- builder stage ---
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# --- runner stage ---
FROM node:20-alpine AS runner
WORKDIR /app
# HOSTNAME=0.0.0.0 is CRITICAL — without it, Next.js standalone binds to
# localhost inside the container and nothing outside Docker can reach it.
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN addgroup -S nodejs && adduser -S nextjs -G nodejs

# Standalone output bundles only what's needed
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000

CMD ["node", "server.js"]
