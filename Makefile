SHELL := /bin/sh

PUBLIC_VITE_ENV := \
	VITE_SUPABASE_URL=https://example.supabase.co \
	VITE_SUPABASE_ANON_KEY=dummy-anon-key \
	VITE_API_TARGET_URL=https://example.com \
	VITE_APP_ENV=web

.PHONY: help install-hooks dockerfile-check build docker-build quality test release-check prepush ci

help:
	@printf '%s\n' \
		'Targets:' \
		'  make dockerfile-check  Run Docker build checks, including ARG/ENV secret linting.' \
		'  make build             Run the production Vite build with dummy public client config.' \
		'  make docker-build      Run a Docker image build with dummy public client config.' \
		'  make quality           Run architecture, lint, and strict type checks.' \
		'  make test              Run the Vitest suite.' \
		'  make release-check     Run the full release gate before cutting a deployment.' \
		'  make prepush           Run the lightweight gate before pushing.' \
		'  make install-hooks     Install repo-managed git hooks.' \
		'  make ci                Alias for release-check.'

install-hooks:
	git config core.hooksPath scripts/git-hooks

dockerfile-check:
	@docker info >/dev/null 2>&1 || { \
		printf '%s\n' 'Docker is not running. Start Docker and rerun make dockerfile-check.' >&2; \
		exit 1; \
	}
	docker build --check .
	node scripts/quality/check-dockerfile-sensitive-env.mjs

build:
	$(PUBLIC_VITE_ENV) npm run build

docker-build:
	docker build \
		--build-arg VITE_SUPABASE_URL=https://example.supabase.co \
		--build-arg VITE_SUPABASE_ANON_KEY=dummy-anon-key \
		--build-arg VITE_API_TARGET_URL=https://example.com \
		--build-arg VITE_APP_ENV=web \
		.

quality:
	npm run quality:check

test:
	npm test

release-check: dockerfile-check docker-build build quality test

prepush: dockerfile-check

ci: release-check
