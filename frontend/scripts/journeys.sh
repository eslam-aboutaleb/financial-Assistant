#!/usr/bin/env bash
#
# Tier C journey runner (Phase 0 stabilization plan, parts A3/A4).
#
# Runs the eight @journey Playwright specs against the live
# Docker stack with a real LLM. Console logs, network HARs,
# screenshots, and observations land in
# e2e/journeys/artifacts/<journey-slug>/.
#
# Usage:
#   frontend/scripts/journeys.sh                  # all journeys
#   frontend/scripts/journeys.sh -g "Journey 1"  # any playwright args pass through
#
# Prerequisites: the live stack (docker compose up --build)
# and a real LLM key in .env. See e2e/journeys/README.md.
set -uo pipefail

FRONTEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${FRONTEND_DIR}" || exit 1

mkdir -p e2e/journeys/artifacts

exec npx playwright test --config=playwright.journeys.config.ts "$@"
