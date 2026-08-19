"""add_derived_metric_definitions_and_lineage

Revision ID: b39fd3c1a2e5
Revises: a81ee9c3eae7
Create Date: 2026-08-19 08:31:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b39fd3c1a2e5'
down_revision: Union[str, Sequence[str], None] = 'a81ee9c3eae7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create derived_metric_definitions table
    op.create_table(
        'derived_metric_definitions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('metric_name', sa.String(), nullable=False),
        sa.Column('display_name', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('formula_expression', sa.String(), nullable=False),
        sa.Column('unit', sa.String(), server_default='ratio', nullable=True),
        sa.Column('required_concepts', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_derived_metric_definitions_id'), 'derived_metric_definitions', ['id'], unique=False)
    op.create_index(op.f('ix_derived_metric_definitions_metric_name'), 'derived_metric_definitions', ['metric_name'], unique=True)
    op.create_index(op.f('ix_derived_metric_definitions_category'), 'derived_metric_definitions', ['category'], unique=False)

    # 2. Add columns to derived_metric_values
    op.add_column('derived_metric_values', sa.Column('metric_definition_id', sa.Integer(), nullable=True))
    op.add_column('derived_metric_values', sa.Column('status', sa.String(), server_default='AVAILABLE', nullable=False))
    op.add_column('derived_metric_values', sa.Column('status_reason', sa.Text(), nullable=True))
    op.create_foreign_key(
        'fk_derived_metric_values_metric_definition_id',
        'derived_metric_values', 'derived_metric_definitions',
        ['metric_definition_id'], ['id']
    )

    # 3. Create derived_metric_input_facts table (Relational Lineage)
    op.create_table(
        'derived_metric_input_facts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('derived_metric_id', sa.Integer(), nullable=False),
        sa.Column('fact_version_id', sa.Integer(), nullable=False),
        sa.Column('concept_name', sa.String(), nullable=False),
        sa.Column('relationship_role', sa.String(), server_default='INPUT', nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['derived_metric_id'], ['derived_metric_values.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['fact_version_id'], ['financial_fact_versions.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_derived_metric_input_facts_id'), 'derived_metric_input_facts', ['id'], unique=False)
    op.create_index(op.f('ix_derived_metric_input_facts_derived_metric_id'), 'derived_metric_input_facts', ['derived_metric_id'], unique=False)
    op.create_index(op.f('ix_derived_metric_input_facts_fact_version_id'), 'derived_metric_input_facts', ['fact_version_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_derived_metric_input_facts_fact_version_id'), table_name='derived_metric_input_facts')
    op.drop_index(op.f('ix_derived_metric_input_facts_derived_metric_id'), table_name='derived_metric_input_facts')
    op.drop_index(op.f('ix_derived_metric_input_facts_id'), table_name='derived_metric_input_facts')
    op.drop_table('derived_metric_input_facts')

    op.drop_constraint('fk_derived_metric_values_metric_definition_id', 'derived_metric_values', type_='foreignkey')
    op.drop_column('derived_metric_values', 'status_reason')
    op.drop_column('derived_metric_values', 'status')
    op.drop_column('derived_metric_values', 'metric_definition_id')

    op.drop_index(op.f('ix_derived_metric_definitions_category'), table_name='derived_metric_definitions')
    op.drop_index(op.f('ix_derived_metric_definitions_metric_name'), table_name='derived_metric_definitions')
    op.drop_index(op.f('ix_derived_metric_definitions_id'), table_name='derived_metric_definitions')
    op.drop_table('derived_metric_definitions')
