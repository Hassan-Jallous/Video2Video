from typing import List, Optional
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl


# === Enums ===

class Provider(str, Enum):
    KIE_AI = "kie.ai"
    DEFAPI = "defapi.org"


class Model(str, Enum):
    VEO_31_FAST = "veo-3.1-fast"
    VEO_31_QUALITY = "veo-3.1-quality"
    SORA_2 = "sora-2"
    SORA_2_PRO = "sora-2-pro"
    DEFAPI_VEO_31 = "defapi-veo-3.1"


class Strategy(str, Enum):
    SEGMENTS = "segments"
    SEAMLESS = "seamless"


class JobStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


# === Request Models ===

class CreateSessionRequest(BaseModel):
    """Request to create a new video clone session"""
    tiktok_url: str = Field(..., description="TikTok video URL to clone")
    product_name: str = Field(..., description="Exact product name (will be used in prompts)")
    num_variants: int = Field(default=1, ge=1, le=10, description="Number of video variants to generate")
    provider: Provider = Field(default=Provider.KIE_AI, description="Video generation provider")
    model: Model = Field(default=Model.VEO_31_FAST, description="AI model for generation")
    strategy: Strategy = Field(default=Strategy.SEGMENTS, description="Generation strategy")


class StartGenerationRequest(BaseModel):
    """Request to start video generation for a session"""
    session_id: str


# === Response Models ===

class ClipInfo(BaseModel):
    """Information about a single generated clip"""
    clip_index: int
    scene_index: int
    duration: float
    prompt: str
    video_url: Optional[str] = None
    status: JobStatus = JobStatus.PENDING


class VariantInfo(BaseModel):
    """Information about a video variant"""
    variant_index: int
    clips: List[ClipInfo] = []
    status: JobStatus = JobStatus.PENDING
    total_cost: float = 0.0


class SessionResponse(BaseModel):
    """Response with session details"""
    session_id: str
    tiktok_url: str
    product_name: str
    num_variants: int
    provider: Provider
    model: Model
    strategy: Strategy
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    original_video_url: Optional[str] = None
    product_image_url: Optional[str] = None
    scene_count: int = 0
    variants: List[VariantInfo] = []
    total_cost: float = 0.0
    error_message: Optional[str] = None


class SessionListResponse(BaseModel):
    """Response with list of sessions"""
    sessions: List[SessionResponse]
    total: int


class VideoLibraryItem(BaseModel):
    """Single video in the library"""
    session_id: str
    variant_index: int
    clip_index: int
    video_url: str
    product_name: str
    created_at: datetime
    duration: float
    provider: Provider
    model: Model


class VideoLibraryResponse(BaseModel):
    """Response with video library contents"""
    videos: List[VideoLibraryItem]
    total: int


class UploadImageResponse(BaseModel):
    """Response after uploading product image"""
    session_id: str
    image_url: str
    message: str


class JobStatusResponse(BaseModel):
    """Response with job status"""
    session_id: str
    status: JobStatus
    progress: float = Field(ge=0.0, le=100.0, description="Progress percentage")
    current_step: str = ""
    variants_completed: int = 0
    variants_total: int = 0
    error_message: Optional[str] = None


class CostEstimateResponse(BaseModel):
    """Response with cost estimate"""
    provider: Provider
    model: Model
    num_variants: int
    estimated_scenes: int
    cost_per_8s: float
    total_estimated_cost: float
    currency: str = "USD"


class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str
    detail: Optional[str] = None
    session_id: Optional[str] = None


# === Settings Models ===

class KeyType(str, Enum):
    GEMINI = "gemini"
    KIE_AI = "kie_ai"
    DEFAPI = "defapi"


class APIKeysRequest(BaseModel):
    """Request to save API keys"""
    gemini_key: Optional[str] = None
    kie_ai_key: Optional[str] = None
    defapi_key: Optional[str] = None


class ValidateKeyRequest(BaseModel):
    """Request to validate a single API key"""
    key_type: KeyType
    key_value: str


class ValidateKeyResponse(BaseModel):
    """Response from key validation"""
    key_type: KeyType
    is_valid: bool
    message: str


class PromptTemplatesRequest(BaseModel):
    """Request to save prompt templates"""
    sora_2_prompt: Optional[str] = None
    veo_3_prompt: Optional[str] = None


class SettingsResponse(BaseModel):
    """Response with all settings"""
    # API Keys (masked)
    gemini_key_set: bool = False
    kie_ai_key_set: bool = False
    defapi_key_set: bool = False
    # Prompt templates
    sora_2_prompt: str = ""
    veo_3_prompt: str = ""
