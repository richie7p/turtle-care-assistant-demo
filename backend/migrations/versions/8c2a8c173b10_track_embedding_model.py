"""track embedding model

Revision ID: 8c2a8c173b10
Revises: 2bab21d5fb0e
Create Date: 2026-08-12 16:34:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8c2a8c173b10"
down_revision: Union[str, Sequence[str], None] = "2bab21d5fb0e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("knowledge_chunks", sa.Column("embedding_model", sa.String(length=160), nullable=True))
    op.create_index(
        op.f("ix_knowledge_chunks_embedding_model"),
        "knowledge_chunks",
        ["embedding_model"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_knowledge_chunks_embedding_model"), table_name="knowledge_chunks")
    op.drop_column("knowledge_chunks", "embedding_model")
