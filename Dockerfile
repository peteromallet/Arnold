# check=skip=SecretsUsedInArgOrEnv
# VITE_SUPABASE_ANON_KEY is public Vite client config. Docker's stock secret
# check flags the ARG name, so scripts/quality/check-dockerfile-sensitive-env.mjs
# enforces the narrower rule this app needs: no sensitive Docker ENV layers.
# Pinned to satisfy package-lock.json's ^20.19.0 || >=22.12.0 engine constraint.
# Bumping the FROM tag is the ONLY Node-version authority for production —
# .nvmrc and engines.node must track this value.
FROM node:20.19.0-alpine AS build
WORKDIR /app

# vendor/ is copied with package*.json because devDependency fake-indexeddb
# is "file:vendor/fake-indexeddb" — npm ci needs it present at install time.
COPY package.json package-lock.json ./
COPY vendor ./vendor
RUN npm ci --no-audit --no-fund --legacy-peer-deps

COPY . .

# Vite inlines VITE_* vars into the JS bundle at build time, so they must be
# present during `npm run build`, not just at runtime. Railway passes service
# variables matching declared ARGs as build args automatically.
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ARG VITE_API_TARGET_URL
ARG VITE_APP_ENV
RUN VITE_SUPABASE_URL="$VITE_SUPABASE_URL" \
    VITE_SUPABASE_ANON_KEY="$VITE_SUPABASE_ANON_KEY" \
    VITE_API_TARGET_URL="$VITE_API_TARGET_URL" \
    VITE_APP_ENV="$VITE_APP_ENV" \
    npm run build

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
