"""
Shared test configuration.

Sets environment variables before any app module is imported so that:
  - VLLM_MODEL satisfies Settings.require_model()
  - DATABASE_URL points at the PostgreSQL test database

Set DATABASE_URL in your environment to override the default, e.g.:
  $env:DATABASE_URL = "postgresql://user:password@localhost/email_reminders_test"
"""

import os

os.environ.setdefault("VLLM_MODEL", "test-model")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://user:password@localhost/email_reminders_test",
)
