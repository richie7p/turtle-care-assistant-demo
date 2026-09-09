"""Preserve historical citation metadata independently of the search index."""

from alembic import op
import sqlalchemy as sa

revision = "4f6d9a21c830"
down_revision = "1a4f0fbd82c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("citation_snapshots", sa.JSON(), nullable=True))
    connection = op.get_bind()
    messages = sa.table("messages", sa.column("id", sa.String()), sa.column("citation_snapshots", sa.JSON()))
    # Use the schema at this revision, not application ORM models.
    rows = connection.execute(sa.text("""
        SELECT c.message_id, c.document_id, c.chunk_id, c.rank, c.score,
               d.title, d.source_name, d.source_url, k.section
        FROM message_citations c
        JOIN knowledge_documents d ON d.id = c.document_id
        JOIN knowledge_chunks k ON k.id = c.chunk_id
        ORDER BY c.message_id, c.rank
    """)).mappings()
    current_id = None
    snapshots = []
    for row in rows:
        if current_id is not None and row["message_id"] != current_id:
            connection.execute(messages.update().where(messages.c.id == current_id).values(citation_snapshots=snapshots))
            snapshots = []
        current_id = row["message_id"]
        snapshots.append({key: value for key, value in row.items() if key != "message_id"})
    if current_id is not None:
        connection.execute(messages.update().where(messages.c.id == current_id).values(citation_snapshots=snapshots))


def downgrade() -> None:
    op.drop_column("messages", "citation_snapshots")
