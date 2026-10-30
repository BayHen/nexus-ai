"""Establish the initial database migration baseline.

Revision ID: 20261030_0001
Revises:
Create Date: 2026-10-30
"""

from collections.abc import Sequence

revision: str = "20261030_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create no business tables in the foundation task."""


def downgrade() -> None:
    """Return to the pre-baseline migration state."""
