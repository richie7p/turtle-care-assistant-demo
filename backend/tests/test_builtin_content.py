from pathlib import Path

from sqlalchemy import select

from app.models import KnowledgeChunk, KnowledgeDocument
from app.services.rag import parse_knowledge_file, seed_knowledge_metadata


def test_builtin_knowledge_has_unique_parseable_demo_metadata(db_session):
    directory = Path(__file__).resolve().parents[2] / "knowledge"
    files = sorted(directory.glob("*.md"))
    assert len(files) == 12
    slugs = set()
    for file in files:
        meta, content = parse_knowledge_file(file)
        assert meta["slug"] not in slugs
        slugs.add(meta["slug"])
        assert meta["title"] and meta["description"] and meta["tags"] and content
        assert "示範" in meta["source_name"]
        assert "未經獸醫審閱" in meta["source_name"]
        assert not meta["reviewed_at"]
    assert seed_knowledge_metadata(db_session, directory) == 12
    assert len(list(db_session.scalars(select(KnowledgeDocument)))) == 12
    ids = list(db_session.scalars(select(KnowledgeChunk.id).order_by(KnowledgeChunk.id)))
    assert len(ids) >= 12
    assert seed_knowledge_metadata(db_session, directory) == 0
    assert list(db_session.scalars(select(KnowledgeChunk.id).order_by(KnowledgeChunk.id))) == ids


def test_hygiene_source_survives_knowledge_indexing(db_session):
    directory = Path(__file__).resolve().parents[2] / "knowledge"
    seed_knowledge_metadata(db_session, directory)
    chunks = list(db_session.scalars(select(KnowledgeChunk).join(KnowledgeDocument).where(
        KnowledgeDocument.slug == "enclosure-safety",
        KnowledgeChunk.section == "照護者的清潔與食品區域",
    )))
    assert len(chunks) == 1
    assert "沙門氏菌" in chunks[0].content
    assert "https://www.cdc.gov/healthy-pets/about/reptiles-and-amphibians.html" in chunks[0].content
