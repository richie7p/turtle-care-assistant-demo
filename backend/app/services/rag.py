from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session, joinedload

from ..ai.provider import ModelProvider
from ..config import Settings
from ..models import KnowledgeChunk, KnowledgeDocument


EMBEDDING_SCHEMA_VERSION = "passage-v2"


def embedding_signature(model: str) -> str:
    return f"{model}@{EMBEDDING_SCHEMA_VERSION}"


def embedding_text(chunk: KnowledgeChunk) -> str:
    return f"{chunk.document.title}\n{chunk.section}\n{chunk.content}"


@dataclass
class RetrievedChunk:
    chunk: KnowledgeChunk
    document: KnowledgeDocument
    score: float
    rank: int


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def lexical_boost(query: str, passage: str) -> float:
    stop_terms = {"怎麼", "應該", "哪些", "可以", "需要", "龜龜", "什麼", "如何"}

    def terms(value: str) -> set[str]:
        found = {token.casefold() for token in re.findall(r"[A-Za-z0-9]+", value) if len(token) >= 2}
        for sequence in re.findall(r"[\u3400-\u9fff]+", value):
            found.update(sequence[index : index + 2] for index in range(len(sequence) - 1))
        return found - stop_terms

    query_terms = terms(query)
    if not query_terms:
        return 0.0
    overlap = query_terms & terms(passage)
    return min(0.12, 0.6 * len(overlap) / len(query_terms))


def heading_boost(query: str, heading: str) -> float:
    query_ascii = {token.casefold() for token in re.findall(r"[A-Za-z0-9]+", query) if len(token) >= 2}
    heading_ascii = {token.casefold() for token in re.findall(r"[A-Za-z0-9]+", heading) if len(token) >= 2}
    bonus = 0.18 if query_ascii & heading_ascii else 0.0

    def cjk_bigrams(value: str) -> set[str]:
        result: set[str] = set()
        for sequence in re.findall(r"[\u3400-\u9fff]+", value):
            result.update(sequence[index : index + 2] for index in range(len(sequence) - 1))
        return result

    if cjk_bigrams(query) & cjk_bigrams(heading):
        bonus += 0.04
    return min(0.22, bonus)


def split_markdown(content: str, target_chars: int = 900, overlap: int = 100) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    heading = "重點"
    buffer = ""
    for line in content.splitlines():
        if line.startswith("#"):
            if buffer.strip():
                sections.extend(_split_long(heading, buffer.strip(), target_chars, overlap))
            heading = line.lstrip("#").strip() or "重點"
            buffer = ""
        else:
            buffer += line + "\n"
    if buffer.strip():
        sections.extend(_split_long(heading, buffer.strip(), target_chars, overlap))
    return sections


def _split_long(section: str, text: str, target: int, overlap: int) -> list[tuple[str, str]]:
    if len(text) <= target:
        return [(section, text)]
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    chunks: list[tuple[str, str]] = []
    current = ""
    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) + 2 > target:
            chunks.append((section, current))
            current = current[-overlap:] + "\n\n" + paragraph
        else:
            current = f"{current}\n\n{paragraph}".strip()
    if current:
        chunks.append((section, current))
    return chunks


def parse_knowledge_file(path: Path) -> tuple[dict, str]:
    raw = path.read_text(encoding="utf-8")
    match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", raw, re.DOTALL)
    if match:
        frontmatter, content = match.groups()
        meta = yaml.safe_load(frontmatter) or {}
        if not isinstance(meta, dict):
            raise ValueError(f"{path.name} 的 YAML frontmatter 必須是物件")
    else:
        meta, content = {}, raw
    content = content.strip()
    if not content:
        raise ValueError(f"{path.name} 沒有可索引的內容")
    first_heading = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    meta.setdefault("title", first_heading.group(1).strip() if first_heading else path.stem.replace("-", " "))
    meta.setdefault("description", "")
    meta.setdefault("source_url", "")
    meta.setdefault("source_name", "本機知識庫")
    meta.setdefault("reviewed_at", "")
    meta.setdefault("tags", [])
    if not isinstance(meta["tags"], list):
        raise ValueError(f"{path.name} 的 tags 必須是 YAML 清單")
    return meta, content


def seed_knowledge_metadata(db: Session, knowledge_dir: Path) -> int:
    count = 0
    if not knowledge_dir.exists():
        return 0
    seen: set[str] = set()
    for path in sorted(knowledge_dir.rglob("*.md")):
        meta, content = parse_knowledge_file(path)
        relative_slug = path.relative_to(knowledge_dir).with_suffix("").as_posix().replace("/", "-")
        slug = str(meta.get("slug") or relative_slug)
        if slug in seen:
            raise ValueError(f"知識文件 slug 重複：{slug}")
        seen.add(slug)
        digest = hashlib.sha256((path.read_text(encoding="utf-8")).encode("utf-8")).hexdigest()
        document = db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.slug == slug))
        if document and document.content_hash == digest:
            document.is_active = True
            continue
        if not document:
            document = KnowledgeDocument(
                slug=slug,
                title=meta["title"],
                description=meta.get("description", ""),
                source_url=meta["source_url"],
                source_name=meta["source_name"],
                reviewed_at=str(meta.get("reviewed_at", "")),
                tags=meta.get("tags", []),
                content_hash=digest,
            )
            db.add(document)
            db.flush()
        document.title = meta["title"]
        document.description = meta.get("description", "")
        document.source_url = meta["source_url"]
        document.source_name = meta["source_name"]
        document.reviewed_at = str(meta.get("reviewed_at", ""))
        document.tags = meta.get("tags", [])
        document.content_hash = digest
        document.is_active = True
        db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id))
        for index, (section, chunk_content) in enumerate(split_markdown(content)):
            db.add(
                KnowledgeChunk(
                    document_id=document.id,
                    chunk_index=index,
                    section=section,
                    content=chunk_content,
                )
            )
        count += 1
    if seen:
        missing_query = select(KnowledgeDocument).where(KnowledgeDocument.slug.not_in(seen))
    else:
        missing_query = select(KnowledgeDocument)
    for document in db.scalars(missing_query):
        document.is_active = False
    db.commit()
    return count


async def embed_missing_chunks(
    db: Session, provider: ModelProvider, embedding_model: str, batch_size: int = 16
) -> int:
    signature = embedding_signature(embedding_model)
    chunks = list(
        db.scalars(
            select(KnowledgeChunk)
            .options(joinedload(KnowledgeChunk.document))
            .where(
                or_(
                    KnowledgeChunk.embedding.is_(None),
                    KnowledgeChunk.embedding_model.is_(None),
                    KnowledgeChunk.embedding_model != signature,
                )
            )
            .order_by(KnowledgeChunk.id)
        )
    )
    completed = 0
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        vectors = await provider.embed([embedding_text(chunk) for chunk in batch], input_type="passage")
        if len(vectors) != len(batch):
            raise RuntimeError("Embedding 回傳數量與知識片段不一致")
        for chunk, vector in zip(batch, vectors, strict=True):
            chunk.embedding = vector
            chunk.embedding_model = signature
            completed += 1
        db.commit()
    return completed


async def retrieve(
    db: Session, provider: ModelProvider, settings: Settings, query: str
) -> tuple[list[RetrievedChunk], int]:
    vector = (await provider.embed([query], input_type="query"))[0]
    chunks = list(
        db.scalars(
            select(KnowledgeChunk)
            .options(joinedload(KnowledgeChunk.document))
            .join(KnowledgeDocument)
            .where(
                KnowledgeDocument.is_active.is_(True),
                KnowledgeChunk.embedding.is_not(None),
                KnowledgeChunk.embedding_model == embedding_signature(settings.ai_embedding_model),
            )
        ).unique()
    )
    scored = [
        (
            chunk,
            min(
                1.0,
                cosine_similarity(vector, chunk.embedding or [])
                + lexical_boost(query, embedding_text(chunk))
                + heading_boost(query, f"{chunk.document.title}\n{chunk.section}"),
            ),
        )
        for chunk in chunks
    ]
    scored.sort(key=lambda item: item[1], reverse=True)
    results: list[RetrievedChunk] = []
    seen_documents: set[str] = set()
    for chunk, score in scored:
        if score < settings.rag_min_score:
            break
        if chunk.document_id in seen_documents:
            continue
        seen_documents.add(chunk.document_id)
        results.append(
            RetrievedChunk(chunk=chunk, document=chunk.document, score=score, rank=len(results) + 1)
        )
        if len(results) >= settings.rag_top_k:
            break
    return results, len(query)
