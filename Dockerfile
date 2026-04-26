# Pinned to satisfy package-lock.json's ^20.19.0 || >=22.12.0 engine constraint.
# Bumping the FROM tag is the ONLY Node-version authority for production —
# .nvmrc and engines.node must track this value.
FROM node:20.19.0-alpine AS build
WORKDIR /app

# vendor/ is copied with package*.json because devDependency fake-indexeddb
# is "file:vendor/fake-indexeddb" — npm ci needs it present at install time.
COPY package.json package-lock.json ./
COPY vendor ./vendor
RUN npm ci --no-audit --no-fund

COPY . .
RUN npm run build

FROM node:20.19.0-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production

# `npm run serve` is `vite preview`, which loads config/vite/vite.config.ts
# at runtime. That config imports @vitejs/plugin-react-swc (a devDependency),
# so we need the full install — copying node_modules from the build stage
# is simpler and more reliable than reinstalling with pinned versions here.
COPY package.json package-lock.json ./
COPY --from=build /app/node_modules ./node_modules
COPY config ./config
COPY --from=build /app/dist ./dist

EXPOSE 8080
CMD ["npm", "run", "serve"]
