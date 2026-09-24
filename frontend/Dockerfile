# syntax=docker/dockerfile:1

# ==============================================================================
# STAGE 1: Dependencies Installation
# ==============================================================================
FROM node:20-alpine AS deps
# libc6-compat is needed for alpine compatibility with certain native dependencies
RUN apk add --no-cache libc6-compat
WORKDIR /app

# Copy dependency manifests
COPY package.json package-lock.json* yarn.lock* pnpm-lock.yaml* bun.lockb* ./

# Install project dependencies based on available lockfile
RUN \
  if [ -f yarn.lock ]; then yarn --frozen-lockfile; \
  elif [ -f package-lock.json ]; then npm ci; \
  elif [ -f pnpm-lock.yaml ]; then corepack enable pnpm && pnpm i --frozen-lockfile; \
  else npm install; \
  fi

# ==============================================================================
# STAGE 2: Next.js Standalone Build
# ==============================================================================
FROM node:20-alpine AS builder
WORKDIR /app

# Copy installed dependencies from deps stage
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Disable Next.js anonymous telemetry during build
ENV NEXT_TELEMETRY_DISABLED=1

# Expose build-time API URL variable to Next.js client bundle
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# Ensure public directory exists
RUN mkdir -p /app/public

# Build Next.js application with standalone output
RUN \
  if [ -f yarn.lock ]; then yarn build; \
  elif [ -f package-lock.json ]; then npm run build; \
  elif [ -f pnpm-lock.yaml ]; then corepack enable pnpm && pnpm run build; \
  else npm run build; \
  fi

# ==============================================================================
# STAGE 3: Production Runner
# ==============================================================================
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Create a secure non-root user and group
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy static assets and public assets
COPY --from=builder /app/public ./public

# Set up prerender cache directory permissions
RUN mkdir .next && chown nextjs:nodejs .next

# Copy standalone output and static files with correct ownership
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# Drop root privileges
USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]
