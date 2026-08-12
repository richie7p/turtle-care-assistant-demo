from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PublicConfigResponse(BaseModel):
    app_name: str
    app_short_name: str
    app_icon: str
    app_tagline: str
    app_description: str
    assistant_name: str
    knowledge_label: str
    profile_label: str
    welcome_title: str
    welcome_description: str
    disclaimer: str
    enable_turtle_module: bool
    ai_provider: str
    ai_configured: bool


class RegisterRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("display_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("名稱不可為空白")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserResponse(ORMModel):
    id: str
    email: EmailStr
    display_name: str
    role: str
    created_at: datetime


class AuthResponse(BaseModel):
    user: UserResponse
    csrf_token: str


class TurtleBase(ORMModel):
    name: str = Field(min_length=1, max_length=80)
    species: str = Field(min_length=1, max_length=120)
    turtle_type: Literal["aquatic", "terrestrial"]
    age: str | None = Field(default=None, max_length=80)
    sex: Literal["male", "female", "unknown"] = "unknown"
    shell_length_cm: float | None = Field(default=None, ge=0, le=300)
    weight_g: float | None = Field(default=None, ge=0, le=500000)
    habitat: str | None = Field(default=None, max_length=2000)
    placement: Literal["indoor", "outdoor"] | None = None
    enclosure_size: str | None = Field(default=None, max_length=120)
    has_uvb: bool | None = None
    has_heater: bool | None = None
    diet: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=3000)


class TurtleCreate(TurtleBase):
    pass


class TurtleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    species: str | None = Field(default=None, min_length=1, max_length=120)
    turtle_type: Literal["aquatic", "terrestrial"] | None = None
    age: str | None = Field(default=None, max_length=80)
    sex: Literal["male", "female", "unknown"] | None = None
    shell_length_cm: float | None = Field(default=None, ge=0, le=300)
    weight_g: float | None = Field(default=None, ge=0, le=500000)
    habitat: str | None = Field(default=None, max_length=2000)
    placement: Literal["indoor", "outdoor"] | None = None
    enclosure_size: str | None = Field(default=None, max_length=120)
    has_uvb: bool | None = None
    has_heater: bool | None = None
    diet: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=3000)


class AttachmentResponse(ORMModel):
    id: str
    original_name: str
    media_type: str
    size_bytes: int
    purpose: str
    created_at: datetime
    url: str | None = None


class TurtleResponse(TurtleBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    photo: AttachmentResponse | None = None


class ConversationCreate(BaseModel):
    turtle_id: str | None = None
    title: str | None = Field(default=None, max_length=100)


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    turtle_id: str | None = None


class ConversationResponse(ORMModel):
    id: str
    user_id: str
    turtle_id: str | None
    title: str
    summary: str | None
    created_at: datetime
    updated_at: datetime
    turtle_name: str | None = None


class CitationResponse(BaseModel):
    document_id: str
    chunk_id: str
    title: str
    source_name: str
    source_url: str
    section: str
    rank: int
    score: float


class MessageResponse(ORMModel):
    id: str
    user_id: str
    conversation_id: str
    role: str
    content: str
    status: str
    created_at: datetime
    attachments: list[AttachmentResponse] = Field(default_factory=list)
    citations: list[CitationResponse] = Field(default_factory=list)


class ConversationDetail(ConversationResponse):
    messages: list[MessageResponse]


class ChatRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    attachment_ids: list[str] = Field(default_factory=list, max_length=4)


class KnowledgeDocumentResponse(ORMModel):
    id: str
    slug: str
    title: str
    description: str
    source_url: str
    source_name: str
    reviewed_at: str
    tags: list[str]
    chunk_count: int = 0


class UserSettingsResponse(ORMModel):
    theme: str
    response_style: str
    default_turtle_id: str | None


class UserSettingsUpdate(BaseModel):
    theme: Literal["light", "dark", "system"] | None = None
    response_style: Literal["concise", "balanced", "detailed"] | None = None
    default_turtle_id: str | None = None


class AdminStatsResponse(BaseModel):
    users: int
    active_users: int
    admins: int
    turtles: int
    conversations: int
    message_count: int
    conversations_today: int
    ai_requests_today: int
    ai_errors_today: int
    ai_success_rate_today: float | None
    input_tokens_today: int
    output_tokens_today: int
    estimated_cost_today: float | None
    cost_configured: bool
    feature_usage: dict[str, int]
    model: str
    vision_model: str
    embedding_model: str
    configured: bool
    last_success_at: datetime | None
    last_latency_ms: int | None
    knowledge_documents: int
    knowledge_chunks: int
    embedded_chunks: int


class AdminUserItem(BaseModel):
    id: str
    email: EmailStr
    display_name: str
    role: Literal["user", "admin"]
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None
    turtle_count: int
    conversation_count: int
    message_count: int
    ai_request_count: int


class AdminUserListResponse(BaseModel):
    items: list[AdminUserItem]
    total: int
    page: int
    page_size: int


class AdminUserUpdate(BaseModel):
    role: Literal["user", "admin"] | None = None
    is_active: bool | None = None


class AdminUsageItem(BaseModel):
    id: str
    request_id: str
    user_id: str | None
    user_email: EmailStr | None
    feature: str
    provider: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    usage_estimated: bool
    estimated_cost: float | None
    latency_ms: int | None
    status: str
    error_code: str | None
    created_at: datetime


class AdminUsageListResponse(BaseModel):
    items: list[AdminUsageItem]
    total: int
    page: int
    page_size: int


class AdminKnowledgeItem(BaseModel):
    id: str
    slug: str
    title: str
    is_active: bool
    reviewed_at: str
    chunk_count: int
    embedded_chunks: int
    updated_at: datetime


class AdminKnowledgeStatusResponse(BaseModel):
    items: list[AdminKnowledgeItem]
    documents: int
    active_documents: int
    chunks: int
    embedded_chunks: int
    embedding_model: str


class AdminKnowledgeSyncResponse(BaseModel):
    updated_documents: int
    embedded_chunks: int
    message: str


class AdminAuditItem(BaseModel):
    id: str
    actor_user_id: str | None
    actor_email: EmailStr | None
    action: str
    target_type: str
    target_id: str | None
    details: dict
    created_at: datetime


class AdminAuditListResponse(BaseModel):
    items: list[AdminAuditItem]
    total: int


class AdminProviderHealthResponse(BaseModel):
    reachable: bool
    status: str
    message: str
    latency_ms: int | None
    chat_model_available: bool
    vision_model_available: bool
    embedding_model_available: bool
    checked_at: datetime


class AdminSystemInfoResponse(BaseModel):
    app_env: str
    database_backend: str
    session_days: int
    ai_requests_per_minute: int
    ai_per_user_concurrency: int
    ai_global_concurrency: int
    max_input_chars: int
    max_image_bytes: int
    max_images_per_message: int
    context_recent_messages: int
    summary_trigger_messages: int


class APIMessage(BaseModel):
    message: str
