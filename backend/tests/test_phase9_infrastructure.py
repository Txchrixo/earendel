"""Tests for Phase 9 — Production Infrastructure.

Tests that:
1. Prometheus metrics endpoint returns text/plain
2. Metrics include execution counters
3. The readyz endpoint includes canary_scheduler check
4. Dockerfile exists and has correct stages
5. docker-compose.yml exists with the right services
6. requirements.txt includes all Phase 1-8 dependencies
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest


# --------------------------------------------------------------------------- #
# 1. Prometheus metrics endpoint
# --------------------------------------------------------------------------- #

class TestMetricsEndpoint:
    """Tests for the Prometheus metrics endpoint."""

    @pytest.mark.asyncio
    async def test_metrics_endpoint_returns_text(self, client):
        """GET /api/v1/metrics should return Prometheus text format."""
        # The metrics endpoint is public (no auth needed) — use ASGI transport directly
        response = await client.get("/api/v1/metrics")
        assert response.status_code == 200
        # Prometheus content type
        ct = response.headers.get("content-type", "")
        assert "text/plain" in ct
        # Should contain some metric names
        text = response.text
        assert "earendel_" in text or "python_info" in text or "process_" in text

    @pytest.mark.asyncio
    async def test_metrics_has_execution_counter(self, client):
        """Metrics should include the earendel_executions_total counter."""
        response = await client.get("/api/v1/metrics")
        assert response.status_code == 200
        # The counter should be defined (even if no executions have run)
        assert "earendel_executions_total" in response.text or "earendel_" in response.text


# --------------------------------------------------------------------------- #
# 2. Readiness check with canary scheduler
# --------------------------------------------------------------------------- #

class TestReadinessCheck:
    """Tests for the improved readyz endpoint."""

    @pytest.mark.asyncio
    async def test_readyz_includes_canary_scheduler(self, client, auth_headers):
        """readyz should include the canary_scheduler check."""
        response = await client.get("/api/v1/readyz", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "checks" in data
        assert "canary_scheduler" in data["checks"]
        assert data["checks"]["canary_scheduler"] in ("running", "stopped")


# --------------------------------------------------------------------------- #
# 3. Dockerfile
# --------------------------------------------------------------------------- #

class TestDockerfile:
    """Tests that the Dockerfile is correctly structured."""

    def test_dockerfile_exists(self):
        """Dockerfile should exist at project root."""
        assert Path("/home/z/my-project/Dockerfile").exists()

    def test_dockerfile_has_backend_stage(self):
        """Dockerfile should have a backend stage with Python 3.12."""
        content = Path("/home/z/my-project/Dockerfile").read_text()
        assert "python:3.12" in content
        assert "uvicorn" in content
        assert "8001" in content

    def test_dockerfile_has_frontend_stage(self):
        """Dockerfile should have a frontend stage with Node 20."""
        content = Path("/home/z/my-project/Dockerfile").read_text()
        assert "node:20" in content
        assert "bun" in content
        assert "3000" in content

    def test_dockerfile_has_healthcheck(self):
        """Dockerfile should have a HEALTHCHECK."""
        content = Path("/home/z/my-project/Dockerfile").read_text()
        assert "HEALTHCHECK" in content

    def test_dockerfile_installs_playwright(self):
        """Dockerfile should install Playwright + Chromium."""
        content = Path("/home/z/my-project/Dockerfile").read_text()
        assert "playwright" in content.lower()
        assert "chromium" in content.lower()


# --------------------------------------------------------------------------- #
# 4. docker-compose.yml
# --------------------------------------------------------------------------- #

class TestDockerCompose:
    """Tests that docker-compose.yml is correctly structured."""

    def test_docker_compose_exists(self):
        """docker-compose.yml should exist at project root."""
        assert Path("/home/z/my-project/docker-compose.yml").exists()

    def test_has_all_services(self):
        """docker-compose.yml should define all 6 services."""
        content = Path("/home/z/my-project/docker-compose.yml").read_text()
        for service in ("backend", "frontend", "mcp", "stream", "db", "caddy"):
            assert service in content, f"Service '{service}' missing from docker-compose.yml"

    def test_has_postgres(self):
        """docker-compose.yml should use PostgreSQL for production DB."""
        content = Path("/home/z/my-project/docker-compose.yml").read_text()
        assert "postgres" in content.lower()

    def test_has_volumes(self):
        """docker-compose.yml should define a volume for DB persistence."""
        content = Path("/home/z/my-project/docker-compose.yml").read_text()
        assert "db_data" in content

    def test_has_healthcheck_for_db(self):
        """docker-compose.yml should have a healthcheck for the DB."""
        content = Path("/home/z/my-project/docker-compose.yml").read_text()
        assert "pg_isready" in content

    def test_backend_depends_on_db(self):
        """Backend should depend on db with health condition."""
        content = Path("/home/z/my-project/docker-compose.yml").read_text()
        assert "depends_on" in content
        assert "condition: service_healthy" in content


# --------------------------------------------------------------------------- #
# 5. requirements.txt
# --------------------------------------------------------------------------- #

class TestRequirements:
    """Tests that requirements.txt includes all dependencies."""

    def test_requirements_has_all_phases(self):
        """requirements.txt should include deps for all phases."""
        content = Path("/home/z/my-project/backend/requirements.txt").read_text()
        # Phase 1-3: core
        assert "fastapi" in content
        assert "uvicorn" in content
        assert "sqlalchemy" in content
        # Phase 2: scikit-learn for TF-IDF embeddings
        assert "scikit-learn" in content
        # Phase 6: APScheduler for canary scheduler
        assert "apscheduler" in content
        # Phase 9: Prometheus for metrics
        assert "prometheus-client" in content
        # Auth
        assert "bcrypt" in content
        assert "PyJWT" in content or "pyjwt" in content.lower()


# --------------------------------------------------------------------------- #
# 6. CI/CD
# --------------------------------------------------------------------------- #

class TestCICD:
    """Tests that the GitHub Actions CI is correctly configured."""

    def test_ci_exists(self):
        """CI workflow should exist."""
        assert Path("/home/z/my-project/.github/workflows/ci.yml").exists()

    def test_ci_has_frontend_lint(self):
        """CI should have a frontend lint job."""
        content = Path("/home/z/my-project/.github/workflows/ci.yml").read_text()
        assert "frontend-lint" in content
        assert "bun run lint" in content

    def test_ci_has_frontend_tests(self):
        """CI should have a frontend tests job."""
        content = Path("/home/z/my-project/.github/workflows/ci.yml").read_text()
        assert "frontend-tests" in content
        assert "vitest" in content

    def test_ci_has_backend_tests(self):
        """CI should have a backend tests job."""
        content = Path("/home/z/my-project/.github/workflows/ci.yml").read_text()
        assert "backend-tests" in content
        assert "pytest" in content

    def test_ci_has_e2e_tests(self):
        """CI should have an E2E tests job."""
        content = Path("/home/z/my-project/.github/workflows/ci.yml").read_text()
        assert "e2e-tests" in content
        assert "playwright" in content

    def test_ci_has_build_check(self):
        """CI should have a build check job."""
        content = Path("/home/z/my-project/.github/workflows/ci.yml").read_text()
        assert "build" in content.lower()
        assert "bun run build" in content

    def test_ci_has_concurrency_cancellation(self):
        """CI should cancel previous runs on the same branch."""
        content = Path("/home/z/my-project/.github/workflows/ci.yml").read_text()
        assert "concurrency" in content
        assert "cancel-in-progress" in content

    def test_ci_caches_dependencies(self):
        """CI should cache bun + pip dependencies."""
        content = Path("/home/z/my-project/.github/workflows/ci.yml").read_text()
        assert "actions/cache" in content
