import asyncio
import getpass
from pathlib import Path

import typer
from sqlalchemy import select

from .ai.provider import get_provider
from .config import get_settings
from .database import Base, SessionLocal, engine
from .models import User
from .security import create_user, normalize_email
from .services.rag import embed_missing_chunks, parse_knowledge_file, seed_knowledge_metadata, split_markdown


cli = typer.Typer(help="NVIDIA NIM RAG 平台管理工具")


@cli.command("init-db")
def init_db():
    settings = get_settings()
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        count = seed_knowledge_metadata(db, settings.knowledge_path)
    typer.echo(f"資料庫已初始化，知識文件：{count} 份。")


@cli.command("create-admin")
def create_admin(email: str = typer.Option(..., prompt=True), name: str = typer.Option("系統管理員", prompt=True)):
    Base.metadata.create_all(bind=engine)
    password = getpass.getpass("管理員密碼（至少 8 字元）：")
    confirmation = getpass.getpass("再次輸入密碼：")
    if password != confirmation:
        raise typer.BadParameter("兩次密碼不一致。")
    if len(password) < 8:
        raise typer.BadParameter("密碼至少需要 8 個字元。")
    with SessionLocal() as db:
        normalized = normalize_email(email)
        if db.scalar(select(User.id).where(User.email == normalized)):
            raise typer.BadParameter("此 Email 已存在。")
        create_user(db, normalized, name, password, role="admin")
    typer.echo("管理員建立完成。")


@cli.command("sync-knowledge")
def sync_knowledge():
    settings = get_settings()
    if not settings.ai_api_key:
        raise typer.BadParameter("請先在 .env 設定 AI_API_KEY。")

    async def run():
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            documents = seed_knowledge_metadata(db, settings.knowledge_path)
            chunks = await embed_missing_chunks(db, get_provider(settings), settings.ai_embedding_model)
            typer.echo(f"同步完成：更新 {documents} 份文件、建立 {chunks} 個向量。")

    asyncio.run(run())


@cli.command("validate-knowledge")
def validate_knowledge():
    """不呼叫 AI，先檢查 Markdown、frontmatter、slug 與分段結果。"""
    settings = get_settings()
    if not settings.knowledge_path.exists():
        raise typer.BadParameter(f"知識庫目錄不存在：{settings.knowledge_path}")
    files = sorted(settings.knowledge_path.rglob("*.md"))
    seen: set[str] = set()
    chunks = 0
    for path in files:
        meta, content = parse_knowledge_file(path)
        relative_slug = path.relative_to(settings.knowledge_path).with_suffix("").as_posix().replace("/", "-")
        slug = str(meta.get("slug") or relative_slug)
        if slug in seen:
            raise typer.BadParameter(f"知識文件 slug 重複：{slug}")
        seen.add(slug)
        chunks += len(split_markdown(content))
        typer.echo(f"OK  {path.relative_to(settings.knowledge_path)} -> {slug}")
    typer.echo(f"驗證完成：{len(files)} 份文件、預計 {chunks} 個片段，不會呼叫 NVIDIA API。")


if __name__ == "__main__":
    cli()
