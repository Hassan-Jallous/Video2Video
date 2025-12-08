import json
import uuid
from datetime import datetime
from typing import Optional

import redis
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends

from config import settings
from models.schemas import (
    CreateSessionRequest,
    SessionResponse,
    SessionListResponse,
    JobStatusResponse,
    UploadImageResponse,
    VideoLibraryResponse,
    VideoLibraryItem,
    CostEstimateResponse,
    ErrorResponse,
    JobStatus,
    Provider,
    Model,
    Strategy,
    APIKeysRequest,
    ValidateKeyRequest,
    ValidateKeyResponse,
    PromptTemplatesRequest,
    SettingsResponse,
    KeyType,
)
from services.storage_manager import StorageManager
from services.image_processor import image_processor
from tasks.video_processor import process_video_pipeline, get_session_data, update_job_status

router = APIRouter()

# Redis client
redis_client = redis.from_url(settings.redis_url)

# Cost map for estimates
COST_PER_8S = {
    (Provider.KIE_AI, Model.VEO_31_FAST): 0.40,
    (Provider.KIE_AI, Model.VEO_31_QUALITY): 2.00,
    (Provider.KIE_AI, Model.SORA_2): 0.15,
    (Provider.KIE_AI, Model.SORA_2_PRO): 0.50,
    (Provider.DEFAPI, Model.DEFAPI_VEO_31): 0.10,
}


def get_storage() -> StorageManager:
    """Dependency to get storage manager"""
    return StorageManager()


# === Session Management ===

@router.post("/sessions", response_model=SessionResponse)
async def create_session(request: CreateSessionRequest):
    """Create a new video clone session"""
    session_id = str(uuid.uuid4())

    # Store session in Redis
    session_data = {
        "session_id": session_id,
        "tiktok_url": request.tiktok_url,
        "product_name": request.product_name,
        "num_variants": request.num_variants,
        "provider": request.provider.value,
        "model": request.model.value,
        "strategy": request.strategy.value,
        "status": JobStatus.PENDING.value,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "scene_count": 0,
        "total_cost": 0.0,
    }

    redis_client.hset(f"session:{session_id}", mapping={
        k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
        for k, v in session_data.items()
    })

    # Add to sessions list
    redis_client.sadd("sessions", session_id)

    return SessionResponse(
        session_id=session_id,
        tiktok_url=request.tiktok_url,
        product_name=request.product_name,
        num_variants=request.num_variants,
        provider=request.provider,
        model=request.model,
        strategy=request.strategy,
        status=JobStatus.PENDING,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Get session details"""
    if not redis_client.exists(f"session:{session_id}"):
        raise HTTPException(status_code=404, detail="Session not found")

    data = get_session_data(session_id)

    return SessionResponse(
        session_id=session_id,
        tiktok_url=data.get("tiktok_url", ""),
        product_name=data.get("product_name", ""),
        num_variants=int(data.get("num_variants", 1)),
        provider=Provider(data.get("provider", "kie.ai")),
        model=Model(data.get("model", "veo-3.1-fast")),
        strategy=Strategy(data.get("strategy", "segments")),
        status=JobStatus(data.get("status", "pending")),
        created_at=datetime.fromisoformat(data.get("created_at", datetime.utcnow().isoformat())),
        updated_at=datetime.fromisoformat(data.get("updated_at", datetime.utcnow().isoformat())),
        original_video_url=data.get("original_video_url"),
        product_image_url=data.get("product_image_url"),
        scene_count=int(data.get("scene_count", 0)),
        variants=data.get("variants", []),
        total_cost=float(data.get("total_cost", 0.0)),
        error_message=data.get("error"),
    )


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(limit: int = 20, offset: int = 0):
    """List all sessions"""
    session_ids = list(redis_client.smembers("sessions"))
    session_ids = [s.decode() if isinstance(s, bytes) else s for s in session_ids]

    sessions = []
    for sid in session_ids[offset:offset + limit]:
        try:
            session = await get_session(sid)
            sessions.append(session)
        except HTTPException:
            continue

    # Sort by created_at descending
    sessions.sort(key=lambda x: x.created_at, reverse=True)

    return SessionListResponse(sessions=sessions, total=len(session_ids))


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, storage: StorageManager = Depends(get_storage)):
    """Delete a session and its videos"""
    if not redis_client.exists(f"session:{session_id}"):
        raise HTTPException(status_code=404, detail="Session not found")

    # Delete from storage
    storage.delete_session(session_id)

    # Delete from Redis
    redis_client.delete(f"session:{session_id}")
    redis_client.srem("sessions", session_id)

    return {"message": "Session deleted", "session_id": session_id}


# === Image Upload ===

@router.post("/sessions/{session_id}/image", response_model=UploadImageResponse)
async def upload_product_image(
    session_id: str,
    file: UploadFile = File(...),
    storage: StorageManager = Depends(get_storage)
):
    """Upload product reference image for a session"""
    if not redis_client.exists(f"session:{session_id}"):
        raise HTTPException(status_code=404, detail="Session not found")

    # Read and save image
    image_data = await file.read()
    image_path = image_processor.save_product_image(
        image_data,
        session_id,
        file.filename or "product.jpg"
    )

    # Store path in session
    redis_client.hset(f"session:{session_id}", "product_image_path", image_path)
    redis_client.hset(f"session:{session_id}", "product_image_url", image_path)

    return UploadImageResponse(
        session_id=session_id,
        image_url=image_path,
        message="Product image uploaded successfully"
    )


# === Video Generation ===

@router.post("/sessions/{session_id}/generate", response_model=JobStatusResponse)
async def start_generation(session_id: str):
    """Start video generation for a session"""
    if not redis_client.exists(f"session:{session_id}"):
        raise HTTPException(status_code=404, detail="Session not found")

    data = get_session_data(session_id)

    # Check if already processing
    if data.get("status") in ["downloading", "analyzing", "generating"]:
        raise HTTPException(status_code=400, detail="Session already processing")

    # Get product image path
    product_image_path = data.get("product_image_path")

    # Start Celery task
    process_video_pipeline.delay(
        session_id=session_id,
        tiktok_url=data["tiktok_url"],
        product_name=data["product_name"],
        product_image_path=product_image_path,
        num_variants=int(data["num_variants"]),
        provider=data["provider"],
        model=data["model"],
        strategy=data["strategy"]
    )

    update_job_status(session_id, status="pending", progress=0.0, current_step="Job queued")

    return JobStatusResponse(
        session_id=session_id,
        status=JobStatus.PENDING,
        progress=0.0,
        current_step="Job queued",
        variants_completed=0,
        variants_total=int(data["num_variants"])
    )


@router.get("/sessions/{session_id}/status", response_model=JobStatusResponse)
async def get_job_status(session_id: str):
    """Get current job status"""
    if not redis_client.exists(f"session:{session_id}"):
        raise HTTPException(status_code=404, detail="Session not found")

    data = get_session_data(session_id)

    return JobStatusResponse(
        session_id=session_id,
        status=JobStatus(data.get("status", "pending")),
        progress=float(data.get("progress", 0.0)),
        current_step=data.get("current_step", ""),
        variants_completed=int(data.get("variants_completed", 0)),
        variants_total=int(data.get("variants_total", 0)),
        error_message=data.get("error")
    )


# === Video Library ===

@router.get("/library", response_model=VideoLibraryResponse)
async def get_video_library(
    limit: int = 50,
    offset: int = 0,
    storage: StorageManager = Depends(get_storage)
):
    """Get all generated videos from the library"""
    session_ids = list(redis_client.smembers("sessions"))
    session_ids = [s.decode() if isinstance(s, bytes) else s for s in session_ids]

    all_videos = []

    for sid in session_ids:
        try:
            data = get_session_data(sid)
            if data.get("status") != "completed":
                continue

            variants = data.get("variants", [])
            if isinstance(variants, str):
                variants = json.loads(variants)

            for variant in variants:
                for clip in variant.get("clips", []):
                    if clip.get("video_url"):
                        all_videos.append(VideoLibraryItem(
                            session_id=sid,
                            variant_index=variant["variant_index"],
                            clip_index=clip["clip_index"],
                            video_url=clip["video_url"],
                            product_name=data.get("product_name", ""),
                            created_at=datetime.fromisoformat(data.get("created_at", datetime.utcnow().isoformat())),
                            duration=clip.get("duration", 0.0),
                            provider=Provider(data.get("provider", "kie.ai")),
                            model=Model(data.get("model", "veo-3.1-fast"))
                        ))
        except Exception:
            continue

    # Sort by created_at descending
    all_videos.sort(key=lambda x: x.created_at, reverse=True)

    return VideoLibraryResponse(
        videos=all_videos[offset:offset + limit],
        total=len(all_videos)
    )


# === Cost Estimation ===

@router.get("/estimate", response_model=CostEstimateResponse)
async def estimate_cost(
    provider: Provider,
    model: Model,
    num_variants: int = 1,
    estimated_scenes: int = 4
):
    """Estimate cost for video generation"""
    cost_key = (provider, model)
    cost_per_8s = COST_PER_8S.get(cost_key, 0.50)

    # Assume average 8s per scene
    total_cost = cost_per_8s * estimated_scenes * num_variants

    return CostEstimateResponse(
        provider=provider,
        model=model,
        num_variants=num_variants,
        estimated_scenes=estimated_scenes,
        cost_per_8s=cost_per_8s,
        total_estimated_cost=total_cost
    )


# === Health & Status ===

@router.get("/status")
async def get_api_status():
    """API status endpoint"""
    return {
        "status": "operational",
        "version": "1.0.0",
        "storage_mode": settings.storage_mode,
        "default_provider": settings.default_provider,
        "default_model": settings.default_model
    }


# === Settings ===

# Default prompts from gemini_analyzer
DEFAULT_SORA_2_PROMPT = """You are an expert cinematographer creating production briefs for Sora 2 video generation.

## SORA 2 PROMPTING RULES (from OpenAI's official guide):

### Structure for each scene prompt:
```
[Prose scene description - subject, product, scenery, lighting]

Cinematography:
Camera shot: [framing and angle]
Camera movement: [dolly, tracking, pan, static, handheld]
Lens: [focal length and characteristics]
Mood: [overall tone]

Actions:
- [Action 1: specific beat/gesture with timing]
- [Action 2: distinct movement]

[Dialogue if applicable - keep to 1-2 short sentences for 4-8 second clips]
```

### CRITICAL SORA 2 BEST PRACTICES:

1. **Specificity over vagueness:**
   - WEAK: "beautiful product shot"
   - STRONG: "the serum bottle catches soft window light, amber liquid glowing warm against the white marble surface"

2. **Camera language Sora understands:**
   - Shot types: wide establishing, medium, medium close-up, close-up, extreme close-up, over-shoulder
   - Movements: slow dolly-in, handheld ENG, tracking with subject, slow pan left/right, tilt up/down
   - Lenses: 35mm, 50mm, 85mm (specify for aesthetic feel), anamorphic, shallow DOF

3. **Lighting must be specific:**
   - WEAK: "brightly lit"
   - STRONG: "soft diffused window light from camera left, warm fill from practical lamp, cool rim separating subject from background"

4. **Actions in beats/counts:**
   - "takes three steps toward camera, pauses, raises product to eye level"
   - "hand enters frame from right, picks up bottle, rotates it slowly 90 degrees"

5. **Film stock references work well:**
   - "35mm Kodak warmth with subtle grain"
   - "clean digital with anamorphic bokeh"
   - "1970s documentary handheld aesthetic"

6. **Color anchors (3-5 colors):**
   - "amber, cream, soft white, touches of gold"

7. **One camera move + one subject action per shot** - don't overcomplicate

8. **Keep dialogue tight:** 6-12 words max for 8-second clips

9. **CRITICAL - Product name in EVERY prompt:**
   - The exact product name MUST appear 2-3 times in each scene prompt
   - Example: "The [PRODUCT NAME] bottle catches soft window light... hand picks up [PRODUCT NAME]..."
   - NEVER use generic terms like "the product" or "the item" - always use the exact product name
"""

DEFAULT_VEO_3_PROMPT = """You are an expert video producer creating prompts for Google Veo 3.1 video generation.

## VEO 3.1 PROMPTING RULES (from Google's official guide):

### 5-Part Formula for each scene:
[Cinematography] + [Subject] + [Action] + [Context] + [Style & Ambiance]

### Example structure:
```
[Camera shot and movement], [subject with product description], [action being performed],
[environment and setting details], [style and lighting description].
[Audio/dialogue if applicable]
```

### CRITICAL VEO 3.1 BEST PRACTICES:

1. **Camera terminology Veo understands:**
   - Movements: dolly shot, tracking shot, crane shot, aerial view, slow pan, POV shot
   - Composition: wide shot, close-up, extreme close-up, low angle, high angle, two-shot
   - Lens: shallow depth of field, wide-angle lens, soft focus, macro lens, deep focus

2. **Always specify lighting:**
   - "soft morning light", "harsh fluorescent overhead", "dramatic spotlight"
   - "warm golden hour lighting", "cool blue tones", "practical lamp glow"

3. **Dialogue format (important!):**
   - Use: A woman says, "We have to leave now."
   - NOT: "We have to leave now" (quotes alone don't work as well)
   - Add "(no subtitles)" if you don't want text on screen

4. **Sound effects format:**
   - "SFX: the soft click of the bottle cap"
   - "SFX: ambient room tone with distant traffic"
   - "Ambient noise: the quiet hum of a studio"

5. **Style keywords that work:**
   - "cinematic film look", "shot on 35mm film", "anamorphic widescreen"
   - "product photography aesthetic", "commercial beauty style"
   - Specific eras: "2020s digital clean", "1990s documentary style"

6. **Color/mood specification:**
   - "warm color palette with amber and cream tones"
   - "clean, minimal aesthetic with soft whites"
   - "moody, cinematic with cool shadows"

7. **Timestamp prompting for sequences:**
   [00:00-00:02] First action...
   [00:02-00:04] Second action...

8. **Keep it visual:** Describe what the camera SEES, not abstract concepts

9. **CRITICAL - Product name in EVERY prompt:**
   - The exact product name MUST appear 2-3 times in each scene prompt
   - Example: "[PRODUCT NAME] positioned center frame... hands demonstrating [PRODUCT NAME]..."
   - NEVER use generic terms like "the product" or "the item" - always use the exact product name
"""


@router.get("/settings", response_model=SettingsResponse)
async def get_settings():
    """Get all app settings"""
    data = redis_client.hgetall("app_settings")
    data = {k.decode(): v.decode() for k, v in data.items()} if data else {}

    return SettingsResponse(
        gemini_key_set=bool(data.get("gemini_key")),
        kie_ai_key_set=bool(data.get("kie_ai_key")),
        defapi_key_set=bool(data.get("defapi_key")),
        sora_2_prompt=data.get("sora_2_prompt", DEFAULT_SORA_2_PROMPT),
        veo_3_prompt=data.get("veo_3_prompt", DEFAULT_VEO_3_PROMPT),
    )


@router.post("/settings/keys")
async def save_api_keys(request: APIKeysRequest):
    """Save API keys"""
    updates = {}
    if request.gemini_key is not None:
        updates["gemini_key"] = request.gemini_key
    if request.kie_ai_key is not None:
        updates["kie_ai_key"] = request.kie_ai_key
    if request.defapi_key is not None:
        updates["defapi_key"] = request.defapi_key

    if updates:
        redis_client.hset("app_settings", mapping=updates)

    return {"message": "API keys saved", "keys_updated": list(updates.keys())}


@router.post("/settings/validate-key", response_model=ValidateKeyResponse)
async def validate_api_key(request: ValidateKeyRequest):
    """Validate a single API key"""
    import httpx

    key_type = request.key_type
    key_value = request.key_value

    if not key_value or len(key_value) < 10:
        return ValidateKeyResponse(
            key_type=key_type,
            is_valid=False,
            message="Key is too short"
        )

    try:
        if key_type == KeyType.GEMINI:
            # Test Gemini API
            import google.generativeai as genai
            genai.configure(api_key=key_value)
            list(genai.list_models())
            return ValidateKeyResponse(
                key_type=key_type,
                is_valid=True,
                message="Gemini API key is valid"
            )

        elif key_type == KeyType.KIE_AI:
            # Test Kie.ai API
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.kie.ai/api/user/balance",
                    headers={"Authorization": f"Bearer {key_value}"},
                    timeout=10.0
                )
                if response.status_code == 200:
                    return ValidateKeyResponse(
                        key_type=key_type,
                        is_valid=True,
                        message="Kie.ai API key is valid"
                    )
                else:
                    return ValidateKeyResponse(
                        key_type=key_type,
                        is_valid=False,
                        message=f"Kie.ai API returned status {response.status_code}"
                    )

        elif key_type == KeyType.DEFAPI:
            # Test defapi.org API
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.defapi.org/api/v1/user/balance",
                    headers={"Authorization": f"Bearer {key_value}"},
                    timeout=10.0
                )
                if response.status_code == 200:
                    return ValidateKeyResponse(
                        key_type=key_type,
                        is_valid=True,
                        message="defapi.org API key is valid"
                    )
                else:
                    return ValidateKeyResponse(
                        key_type=key_type,
                        is_valid=False,
                        message=f"defapi.org API returned status {response.status_code}"
                    )

    except Exception as e:
        return ValidateKeyResponse(
            key_type=key_type,
            is_valid=False,
            message=f"Validation failed: {str(e)}"
        )

    return ValidateKeyResponse(
        key_type=key_type,
        is_valid=False,
        message="Unknown key type"
    )


@router.post("/settings/prompts")
async def save_prompt_templates(request: PromptTemplatesRequest):
    """Save prompt templates"""
    updates = {}
    if request.sora_2_prompt is not None:
        updates["sora_2_prompt"] = request.sora_2_prompt
    if request.veo_3_prompt is not None:
        updates["veo_3_prompt"] = request.veo_3_prompt

    if updates:
        redis_client.hset("app_settings", mapping=updates)

    return {"message": "Prompts saved", "prompts_updated": list(updates.keys())}


@router.post("/settings/prompts/reset")
async def reset_prompt_templates():
    """Reset prompt templates to defaults"""
    redis_client.hset("app_settings", mapping={
        "sora_2_prompt": DEFAULT_SORA_2_PROMPT,
        "veo_3_prompt": DEFAULT_VEO_3_PROMPT,
    })
    return {"message": "Prompts reset to defaults"}
