FROM node:24-alpine AS deps
WORKDIR /app
COPY package*.json ./
# react-leaflet@4.2.1 peers on React 18; project uses React 19.
# --legacy-peer-deps is a temporary workaround. Track upstream:
# https://github.com/PaulLeCam/react-leaflet/issues
RUN npm ci --legacy-peer-deps

FROM node:24-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:24-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]
