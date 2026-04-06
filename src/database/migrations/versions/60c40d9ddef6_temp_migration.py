"""temp_migration

Revision ID: 60c40d9ddef6
Revises: 3d4543dc6d81
Create Date: 2026-03-28 14:57:54.913965

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '60c40d9ddef6'
down_revision: Union[str, None] = '3d4543dc6d81'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
