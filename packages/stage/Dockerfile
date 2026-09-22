FROM node:24-bookworm-slim

ENV NODE_ENV=production

WORKDIR /app/stage

# No dependencies at runtime and no build: the server is plain Node, the page is plain
# files. Only the sources are copied — the dev tooling never enters the image.
COPY packages/stage/package.json ./
COPY packages/stage/src ./src
COPY packages/stage/public ./public

ENV HOST=0.0.0.0
ENV PORT=8793
EXPOSE 8793

CMD ["node", "src/server.ts"]
