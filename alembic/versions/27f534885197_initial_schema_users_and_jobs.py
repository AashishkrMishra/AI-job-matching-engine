"""initial schema: users and jobs

Baseline migration. This replaces the previous `Base.metadata.create_all()`
call in app/main.py, which could only ever create missing tables and silently
ignored changes to existing ones.

`upgrade()` skips tables that already exist, so it can be applied to a database
that predates Alembic. Later migrations should not copy that pattern — it is
here only because this revision has to adopt schema it did not create.

Revision ID: 27f534885197
Revises:
Create Date: 2026-08-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '27f534885197'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Existing deployments already have these tables: they were built by the
    # `Base.metadata.create_all()` this migration replaces, and that call left
    # no alembic_version row behind. Creating them unconditionally would abort
    # with "table already exists", and because render.yaml chains migration and
    # server with `&&`, the service would never come up at all. The definitions
    # below and create_all's both come from app/models.py, so a table that is
    # already present is already correct.
    existing = set(sa.inspect(op.get_bind()).get_table_names())

    if 'users' not in existing:
        op.create_table(
            'users',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('email', sa.String(), nullable=False),
            sa.Column('hashed_password', sa.String(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_users_id', 'users', ['id'], unique=False)
        op.create_index('ix_users_email', 'users', ['email'], unique=True)

    if 'jobs' not in existing:
        op.create_table(
            'jobs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('company', sa.String(), nullable=False),
            sa.Column('role', sa.String(), nullable=False),
            sa.Column('status', sa.String(), server_default='applied', nullable=False),
            sa.Column('owner_id', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_jobs_id', 'jobs', ['id'], unique=False)
        op.create_index('ix_jobs_owner_id', 'jobs', ['owner_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_jobs_owner_id', table_name='jobs')
    op.drop_index('ix_jobs_id', table_name='jobs')
    op.drop_table('jobs')

    op.drop_index('ix_users_email', table_name='users')
    op.drop_index('ix_users_id', table_name='users')
    op.drop_table('users')
