"""Opt-in real NVIDIA API smoke test; synthetic data and temporary local storage only."""
import argparse
import asyncio
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, help="Optional sanitized JSON report path")
    args = parser.parse_args()
    original = get_settings()
    if not original.ai_api_key:
        parser.error("Set AI_API_KEY in the process environment or an ignored .env file first.")
    report = {
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "app": original.app_name,
        "models": {"text": original.ai_model, "fallback": original.ai_fallback_model,
                   "vision": original.ai_vision_model, "embedding": original.ai_embedding_model},
        "data": "Synthetic fixture; temporary SQLite database and image files; real NVIDIA requests.",
        "tests": [],
    }

    with tempfile.TemporaryDirectory(prefix="nim-live-smoke-") as directory:
        root = Path(directory)
        knowledge = root / "knowledge"
        knowledge.mkdir()
        knowledge.joinpath("synthetic-test.md").write_text(
            "# 合成測試知識文件\n\n## 測試代碼\n這是合成軟體測試文件。"
            "知識庫的測試代碼是 RAG-739。此代碼不是醫療、飼養或組織政策建議。\n", encoding="utf-8")
        os.environ.update({"DATABASE_URL": "sqlite:///" + (root / "test.db").as_posix(),
                           "UPLOAD_DIR": str(root / "uploads"), "KNOWLEDGE_DIR": str(knowledge)})
        get_settings.cache_clear()
        settings = get_settings()

        from fastapi.testclient import TestClient
        from PIL import Image, ImageDraw
        from sqlalchemy import select
        from app.ai.provider import NvidiaNimProvider
        from app.database import SessionLocal, engine
        from app.main import app
        from app.models import AIUsageLog
        from app.services.rag import embed_missing_chunks

        def check(name, function):
            started = time.perf_counter()
            try:
                details = function()
                entry = {"name": name, "passed": True, "latency_ms": round((time.perf_counter()-started)*1000), **details}
            except Exception as exc:
                entry = {"name": name, "passed": False, "latency_ms": round((time.perf_counter()-started)*1000),
                         "error_type": type(exc).__name__, "message": str(exc).replace(settings.ai_api_key, "[REDACTED]")}
            report["tests"].append(entry)
            print(json.dumps({"name": name, "passed": entry["passed"], "latency_ms": entry["latency_ms"]}), flush=True)
            return entry["passed"]

        def events(response):
            assert response.status_code == 200, f"Chat HTTP {response.status_code}"
            parsed = []
            for block in response.text.split("\n\n"):
                lines = block.splitlines()
                event = next((line[7:] for line in lines if line.startswith("event: ")), None)
                data = next((line[6:] for line in lines if line.startswith("data: ")), None)
                if event and data:
                    parsed.append((event, json.loads(data)))
            assert not any(event == "error" for event, _ in parsed), parsed
            assert any(event == "done" for event, _ in parsed), "No completion event"
            return parsed

        try:
            with TestClient(app) as client:
                response = client.post("/api/v1/auth/register", json={"email": "live-smoke@example.com",
                    "display_name": "合成測試帳號", "password": "synthetic-test-only-739"})
                assert response.status_code == 201, f"Register HTTP {response.status_code}"
                headers = {"X-CSRF-Token": response.json()["csrf_token"]}

                def indexing():
                    with SessionLocal() as db:
                        count = asyncio.run(embed_missing_chunks(db, NvidiaNimProvider(settings), settings.ai_embedding_model))
                    assert count == 1, f"Expected one indexed chunk, got {count}"
                    return {"indexed_chunks": count, "input_type": "passage"}

                indexed = check("real_embedding_index", indexing)
                turtle_id = None
                if settings.enable_turtle_module:
                    turtle = client.post("/api/v1/turtles", headers=headers, json={"name": "小測試龜",
                        "species": "合成測試物種", "turtle_type": "aquatic", "notes": "僅供軟體測試"})
                    assert turtle.status_code == 201, f"Profile HTTP {turtle.status_code}"
                    turtle_id = turtle.json()["id"]
                conversation = client.post("/api/v1/conversations", headers=headers, json={"turtle_id": turtle_id})
                assert conversation.status_code == 201
                conversation_id = conversation.json()["id"]

                def chat():
                    assert indexed, "Embedding indexing failed"
                    question = "知識庫的測試代碼是什麼？請根據來源回答並保留完整代碼。"
                    if turtle_id:
                        question += "也請依據目前烏龜資料說出我的烏龜名稱。"
                    parsed = events(client.post(f"/api/v1/conversations/{conversation_id}/messages/stream",
                        headers=headers, json={"content": question, "attachment_ids": []}))
                    answer = "".join(data["delta"] for event, data in parsed if event == "token")
                    assert "RAG-739" in answer, answer
                    if turtle_id:
                        assert "小測試龜" in answer, answer
                    citations = next(data for event, data in parsed if event == "citations")
                    assert citations["status"] == "found" and len(citations["items"]) == 1
                    saved = client.get(f"/api/v1/conversations/{conversation_id}").json()
                    assert len(saved["messages"]) == 2 and saved["messages"][1]["status"] == "complete"
                    assert saved["messages"][1]["citations"][0]["title"] == "合成測試知識文件"
                    assert saved["title"] and saved["title"] != "新對話"
                    assert "\n" not in saved["title"] and "```" not in saved["title"] and len(saved["title"]) <= 18
                    return {"answer": answer, "citation_count": len(citations["items"]), "saved_messages": 2,
                            "generated_title": saved["title"], "turtle_profile_in_answer": bool(turtle_id)}

                check("real_streaming_rag_and_persistence", chat)

                def vision():
                    image = Image.new("RGB", (640, 320), "white")
                    ImageDraw.Draw(image).rectangle((70, 70, 260, 240), fill="red")
                    buf = io.BytesIO()
                    image.save(buf, format="PNG")
                    upload = client.post("/api/v1/attachments", headers=headers,
                                         files={"file": ("synthetic-red-rectangle.png", buf.getvalue(), "image/png")})
                    assert upload.status_code == 201, f"Upload HTTP {upload.status_code}"
                    attachment_id = upload.json()["id"]
                    parsed = events(client.post(f"/api/v1/conversations/{conversation_id}/messages/stream",
                        headers=headers, json={"content": "只根據這張圖片說明矩形是什麼顏色。請用繁體中文簡短回答。",
                                               "attachment_ids": [attachment_id]}))
                    answer = "".join(data["delta"] for event, data in parsed if event == "token")
                    assert "紅" in answer or "red" in answer.casefold(), answer
                    saved = client.get(f"/api/v1/conversations/{conversation_id}").json()
                    assert len(saved["messages"]) == 4 and saved["messages"][-1]["status"] == "complete"
                    assert saved["messages"][-2]["attachments"][0]["id"] == attachment_id
                    with SessionLocal() as db:
                        usage = db.scalar(select(AIUsageLog).where(AIUsageLog.feature == "vision"))
                        assert usage and usage.model == settings.ai_vision_model and usage.status == "success"
                    return {"answer": answer, "uploaded_image_saved": True, "vision_model_recorded": True}

                check("real_image_upload_and_streaming_vision", vision)

                if settings.ai_fallback_model and settings.ai_fallback_model != settings.ai_model:
                    def fallback():
                        # An unavailable primary exercises the product's real failover path.
                        probe = NvidiaNimProvider(settings.model_copy(update={"ai_model": "unavailable/synthetic-smoke-model"}))
                        async def run():
                            return [event async for event in probe.stream_generate(
                                [{"role": "user", "content": "Reply exactly FALLBACK-731, without explanation."}], max_tokens=64)]
                        result = asyncio.run(run())
                        answer = "".join(event.content or "" for event in result if event.kind == "token")
                        models = [event.content for event in result if event.kind == "model"]
                        assert "FALLBACK-731" in answer, answer
                        assert models == ["unavailable/synthetic-smoke-model", settings.ai_fallback_model], models
                        return {"answer": answer, "selected_models": models}
                    check("real_streaming_fallback", fallback)
        except Exception as exc:
            report["tests"].append({"name": "test_setup", "passed": False, "error_type": type(exc).__name__,
                                    "message": str(exc).replace(settings.ai_api_key, "[REDACTED]")})
        finally:
            engine.dispose()

    report["passed"] = bool(report["tests"]) and all(test["passed"] for test in report["tests"])
    serialized = json.dumps(report, ensure_ascii=False, indent=2).replace(original.ai_api_key, "[REDACTED]")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
