"""Pytest configuration for the backend.

Sets AUTH_PROVIDER=dev for every backend test run (auth-context.md §Testing posture)."""

from __future__ import annotations

import os

os.environ.setdefault("AUTH_PROVIDER", "dev")
os.environ.setdefault("APP_ENV", "development")
