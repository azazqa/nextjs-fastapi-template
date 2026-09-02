FROM node:24-trixie-slim

WORKDIR /app

RUN npm install -g pnpm

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
ENV CI=true
RUN rm -rf .next && pnpm run build

EXPOSE 3000

CMD ["pnpm", "run", "start"]