"""Merge 0008 and 0009 heads

Revision ID: ac30987306bc
Revises: 0008, 0009
Create Date: 2026-07-18 09:18:44.259757
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'ac30987306bc'
down_revision: Union[str, None] = ('0008', '0009')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass
