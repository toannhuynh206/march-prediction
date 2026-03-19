FROM node:22-alpine AS builder

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

# Final image: just the built files
FROM alpine:latest
COPY --from=builder /app/dist /dist
CMD ["echo", "Frontend built successfully"]
