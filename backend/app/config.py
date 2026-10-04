from functools import lru_cache
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "烏龜飼養小助手"
    app_short_name: str = "烏龜飼養"
    app_icon: str = "龜"
    app_tagline: str = "懂你的龜，也懂你的飼養日常"
    app_description: str = "結合龜龜 Profile、自訂飼養知識庫與 NVIDIA NIM 的完整實力示範。"
    assistant_name: str = "烏龜飼養小助手"
    knowledge_label: str = "飼養知識"
    profile_label: str = "我的龜龜"
    welcome_title: str = "嗨！我是你的烏龜飼養小助手"
    welcome_description: str = "選擇一隻龜龜後提問，我會結合牠的資料與可信飼養知識回答。"
    app_disclaimer: str = "AI 可能會出錯；重大健康問題請諮詢合格爬蟲類獸醫。"
    enable_turtle_module: bool = True
    knowledge_dir: str = "./knowledge"
    system_prompt_file: str = "./prompts/assistant.md"
    system_prompt: str | None = None
    app_env: str = "development"
    app_origin: str = "http://localhost:5173"
    session_secret: str = "development-only-change-this-secret-now"
    session_days: int = 7
    database_url: str = "sqlite:///./data/turtle_assistant.db"
    upload_dir: str = "./uploads"

    ai_provider: str = "nvidia-nim"
    ai_api_key: str = ""
    ai_base_url: str = "https://integrate.api.nvidia.com/v1"
    ai_model: str = "nvidia/nemotron-3.5-lightning-30b-a3b"
    ai_fallback_model: str | None = "nvidia/nemotron-3-super-120b-a12b"
    ai_vision_model: str = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
    ai_embedding_model: str = "nvidia/llama-nemotron-embed-vl-1b-v2"
    ai_timeout_seconds: int = 45
    ai_max_output_tokens: int = 1200
    ai_input_cost_per_million: float | None = None
    ai_output_cost_per_million: float | None = None

    ai_requests_per_minute: int = 10
    ai_per_user_concurrency: int = 1
    ai_global_concurrency: int = 4
    max_input_chars: int = 8000
    max_image_bytes: int = 5 * 1024 * 1024
    max_images_per_message: int = 4
    context_recent_messages: int = 12
    context_max_chars: int = 40000
    summary_trigger_messages: int = 20
    rag_top_k: int = 4
    rag_min_score: float = 0.35

    session_cookie_name: str = "turtle_session"
    csrf_cookie_name: str = "turtle_csrf"

    @field_validator("database_url")
    @classmethod
    def resolve_sqlite_url(cls, value: str) -> str:
        prefix = "sqlite:///./"
        if value.startswith(prefix):
            path = BACKEND_DIR / value.removeprefix(prefix)
            return f"sqlite:///{path.as_posix()}"
        return value

    @field_validator(
        "ai_input_cost_per_million",
        "ai_output_cost_per_million",
        "ai_fallback_model",
        "system_prompt",
        mode="before",
    )
    @classmethod
    def blank_cost_is_unset(cls, value):
        return None if value == "" else value

    @field_validator("upload_dir")
    @classmethod
    def resolve_upload_dir(cls, value: str) -> str:
        path = Path(value)
        if not path.is_absolute():
            path = BACKEND_DIR / path
        return str(path.resolve())

    @model_validator(mode="after")
    def validate_production_security(self):
        if not self.is_production:
            return self
        secret = self.session_secret.strip()
        placeholder_markers = ("development-only", "replace", "請替換", "請換成")
        if len(secret) < 32 or any(marker in secret.casefold() for marker in placeholder_markers):
            raise ValueError("Production requires a unique SESSION_SECRET of at least 32 characters.")
        if not self.app_origin.startswith("https://") or "example.org" in self.app_origin:
            raise ValueError("Production APP_ORIGIN must be the real public HTTPS origin.")
        return self

    @property
    def knowledge_path(self) -> Path:
        path = Path(self.knowledge_dir)
        return path if path.is_absolute() else (PROJECT_DIR / path).resolve()

    @property
    def system_prompt_path(self) -> Path:
        path = Path(self.system_prompt_file)
        return path if path.is_absolute() else (PROJECT_DIR / path).resolve()

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def allowed_origins(self) -> list[str]:
        if self.is_production:
            return [self.app_origin.rstrip("/")]
        origins = {
            self.app_origin.rstrip("/"),
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        }
        return sorted(origins)


@lru_cache
def get_settings() -> Settings:
    return Settings()
