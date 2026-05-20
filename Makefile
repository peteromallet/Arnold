SHELL := /bin/sh

PUBLIC_VITE_ENV := \
	VITE_SUPABASE_URL=https://example.supabase.co \
	VITE_SUPABASE_ANON_KEY=dummy-anon-key \
	VITE_API_TARGET_URL=https://example.com \
	VITE_APP_ENV=web

.PHONY: help install-hooks dockerfile-check build-context-check build docker-build deploy-check quality test slot-first-unit slot-first-edge slot-first-db slot-first-e2e slot-first-health slot-first-schema-drift slot-first-test-fixture-legacy slot-first-audit release-check prepush ci

help:
	@printf '%s\n' \
		'Targets:' \
		'  make dockerfile-check     Run Docker build checks, including ARG/ENV secret linting.' \
		'  make build-context-check  Verify package.json file: deps and config aliases stay inside the build context.' \
		'  make build                Run the production Vite build with dummy public client config.' \
		'  make docker-build         Run a Docker image build with dummy public client config.' \
		'  make deploy-check         Reproduce the Railway build end-to-end (catches the breakage that --check misses).' \
		'  make quality              Run architecture, lint, and strict type checks.' \
		'  make test                 Run the Vitest suite.' \
		'  make slot-first-audit     Run M0 slot-first audit-mode tests and gates.' \
		'  make release-check        Run the full release gate before cutting a deployment.' \
		'  make prepush              Run the lightweight gate before pushing.' \
		'  make install-hooks        Install repo-managed git hooks.' \
		'  make ci                   Alias for release-check.'

install-hooks:
	git config core.hooksPath scripts/git-hooks

dockerfile-check:
	@docker info >/dev/null 2>&1 || { \
		printf '%s\n' 'Docker is not running. Start Docker and rerun make dockerfile-check.' >&2; \
		exit 1; \
	}
	docker build --check .
	node scripts/quality/check-dockerfile-sensitive-env.mjs

# Static guard against the class of bug that took prod down on commit c99e760ec:
# the Railway build context is the repo root, so any file: dependency in
# package.json or any vite/vitest alias pointing outside the repo silently breaks
# `npm ci` and the bundler with misleading errors. Catches the issue in <1s,
# without spinning up Docker.
build-context-check:
	node scripts/quality/check-build-context.mjs

build:
	$(PUBLIC_VITE_ENV) npm run build

docker-build:
	docker build \
		--build-arg VITE_SUPABASE_URL=https://example.supabase.co \
		--build-arg VITE_SUPABASE_ANON_KEY=dummy-anon-key \
		--build-arg VITE_API_TARGET_URL=https://example.com \
		--build-arg VITE_APP_ENV=web \
		.

# Real Railway-equivalent build (Dockerfile + npm ci + vite build). Run before
# pushing changes that touch the Dockerfile, package.json deps, or vite config —
# this is the gate that would have caught the c99e760ec breakage.
deploy-check: build-context-check docker-build

quality:
	npm run quality:check

test:
	npm test

slot-first-unit:
	npm run test:slot:unit

slot-first-edge:
	npm run test:slot:edge

# pgTAP-only DB coverage. This target does not run readiness checks.
slot-first-db:
	npm run test:slot:db -- --audit

slot-first-e2e:
	npm run test:slot:e2e

# Readiness diagnostics only. This target must not be counted as DB coverage.
slot-first-health:
	npm run slot:first:health -- --audit

slot-first-schema-drift:
	npm run quality:schema-drift -- --audit

slot-first-test-fixture-legacy:
	npm run quality:test-fixture-legacy -- --audit

slot-first-audit: slot-first-unit slot-first-edge slot-first-db slot-first-schema-drift slot-first-test-fixture-legacy slot-first-health slot-first-e2e

release-check: dockerfile-check build-context-check docker-build build quality test

prepush: dockerfile-check build-context-check

ci: release-check
