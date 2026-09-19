FROM node:24-bookworm-slim

RUN npm install --global pnpm@10.32.1

ENV NODE_ENV=production

WORKDIR /app/brain

COPY packages/brain/package.json packages/brain/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile --prod=false

COPY packages/brain/src ./src
COPY packages/brain/config ./config
COPY packages/contract/fixtures /app/contract/fixtures

CMD ["pnpm", "start"]
