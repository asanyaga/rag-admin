"""add experiments table

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-02-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = 'a7b8c9d0e1f2'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create experiment_status enum
    experiment_status = sa.Enum('active', 'concluded', name='experiment_status', create_type=False)
    experiment_status.create(op.get_bind(), checkfirst=True)

    # Create experiments table
    op.create_table(
        'experiments',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('baseline_run_id', UUID(as_uuid=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', experiment_status, server_default='active', nullable=False),
        sa.Column('created_by', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['baseline_run_id'], ['eval_runs.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_experiments_project_id', 'experiments', ['project_id'])

    # Add experiment_id and variant_label to eval_runs
    op.add_column('eval_runs', sa.Column('experiment_id', UUID(as_uuid=True), nullable=True))
    op.add_column('eval_runs', sa.Column('variant_label', sa.String(255), nullable=True))
    op.create_foreign_key(
        'fk_eval_runs_experiment_id',
        'eval_runs', 'experiments',
        ['experiment_id'], ['id'],
        ondelete='SET NULL',
    )
    op.create_index('ix_eval_runs_experiment_id', 'eval_runs', ['experiment_id'])


def downgrade() -> None:
    op.drop_index('ix_eval_runs_experiment_id', table_name='eval_runs')
    op.drop_constraint('fk_eval_runs_experiment_id', 'eval_runs', type_='foreignkey')
    op.drop_column('eval_runs', 'variant_label')
    op.drop_column('eval_runs', 'experiment_id')
    op.drop_index('ix_experiments_project_id', table_name='experiments')
    op.drop_table('experiments')
    sa.Enum(name='experiment_status').drop(op.get_bind(), checkfirst=True)
