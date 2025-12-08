import asyncio
import json
import redis
from typing import Optional
from celery import Celery

from config import settings
from services.video_downloader import video_downloader
from services.scene_detector import scene_detector
from services.gemini_analyzer import gemini_analyzer, TargetModel
from services.video_generator import video_generator, Provider, Model
from services.storage_manager import StorageManager
from services.image_processor import image_processor

# Initialize Celery
celery_app = Celery(
    "video_processor",
    broker=settings.celery_broker_url,
    backend=settings.redis_url
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)

# Redis client for status updates
redis_client = redis.from_url(settings.redis_url)


def update_job_status(
    session_id: str,
    status: str,
    progress: float = 0.0,
    current_step: str = "",
    error: Optional[str] = None,
    **extra_data
):
    """Update job status in Redis"""
    data = {
        "status": status,
        "progress": progress,
        "current_step": current_step,
        "error": error,
        **extra_data
    }
    redis_client.hset(f"session:{session_id}", mapping={
        k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
        for k, v in data.items() if v is not None
    })


def get_session_data(session_id: str) -> dict:
    """Get session data from Redis"""
    data = redis_client.hgetall(f"session:{session_id}")
    return {
        k.decode(): json.loads(v) if v.decode().startswith(('[', '{')) else v.decode()
        for k, v in data.items()
    }


@celery_app.task(bind=True, max_retries=3)
def process_video_pipeline(
    self,
    session_id: str,
    tiktok_url: str,
    product_name: str,
    product_image_path: Optional[str],
    num_variants: int,
    provider: str,
    model: str,
    strategy: str
):
    """
    Main video processing pipeline.

    Steps:
    1. Download TikTok video
    2. Detect scenes
    3. Analyze with Gemini (product-focused)
    4. Generate prompts
    5. Generate videos (N variants)
    6. Upload to storage
    """
    storage = StorageManager()

    try:
        # === Step 1: Download TikTok Video ===
        update_job_status(
            session_id,
            status="downloading",
            progress=5.0,
            current_step="Downloading TikTok video..."
        )

        download_result = video_downloader.download(tiktok_url, session_id)
        video_path = download_result["video_path"]

        update_job_status(
            session_id,
            status="downloading",
            progress=15.0,
            current_step="Video downloaded successfully",
            original_duration=download_result["duration"]
        )

        # === Step 2: Scene Detection ===
        update_job_status(
            session_id,
            status="analyzing",
            progress=20.0,
            current_step="Detecting scenes..."
        )

        scenes = scene_detector.detect_scenes(video_path, session_id)

        update_job_status(
            session_id,
            status="analyzing",
            progress=30.0,
            current_step=f"Detected {len(scenes)} scenes",
            scene_count=len(scenes)
        )

        # === Step 3: Gemini Analysis (Product-Focused) ===
        # Determine target model for prompt optimization
        # Sora models -> SORA_2 prompts, Veo models -> VEO_3 prompts
        if "sora" in model.lower():
            target_model = TargetModel.SORA_2
            prompt_type = "Sora 2"
        else:
            target_model = TargetModel.VEO_3
            prompt_type = "Veo 3.1"

        update_job_status(
            session_id,
            status="analyzing",
            progress=35.0,
            current_step=f"Analyzing video for {product_name} ({prompt_type} prompts)..."
        )

        analysis = gemini_analyzer.analyze_video(
            video_path,
            product_name,
            scenes,
            target_model=target_model
        )

        update_job_status(
            session_id,
            status="analyzing",
            progress=50.0,
            current_step="Video analysis complete"
        )

        # === Step 4: Extract Prompts from Analysis ===
        # Gemini analyzer now returns VideoPromptResult with optimized prompts
        update_job_status(
            session_id,
            status="analyzing",
            progress=55.0,
            current_step=f"Extracting {prompt_type} optimized prompts..."
        )

        # Use scene_prompts for segments strategy, full_video_prompt for seamless
        if strategy == "seamless" and analysis.full_video_prompt:
            # Create a single prompt object for full video
            from dataclasses import dataclass
            @dataclass
            class FullVideoPrompt:
                scene_index: int = -1
                duration: float = analysis.total_duration
                prompt: str = analysis.full_video_prompt
            prompts = [FullVideoPrompt()]
        else:
            # Use individual scene prompts
            prompts = analysis.scene_prompts

        update_job_status(
            session_id,
            status="analyzing",
            progress=60.0,
            current_step=f"Generated {len(prompts)} {prompt_type} prompts"
        )

        # === Step 5: Generate Videos (N Variants) ===
        provider_enum = Provider(provider)
        model_enum = Model(model)

        total_generations = num_variants * len(prompts)
        completed_generations = 0
        all_variants = []

        for variant_idx in range(num_variants):
            variant_clips = []

            for prompt_obj in prompts:
                update_job_status(
                    session_id,
                    status="generating",
                    progress=60.0 + (completed_generations / total_generations * 30.0),
                    current_step=f"Generating variant {variant_idx + 1}/{num_variants}, "
                                 f"clip {len(variant_clips) + 1}/{len(prompts)}...",
                    variants_completed=variant_idx,
                    variants_total=num_variants
                )

                # Run async generation
                result = asyncio.run(video_generator.generate(
                    prompt=prompt_obj.prompt,
                    provider=provider_enum,
                    model=model_enum,
                    product_image_path=product_image_path,
                    duration=min(prompt_obj.duration, 8.0),
                    session_id=session_id,
                    variant_index=variant_idx * len(prompts) + prompt_obj.scene_index
                ))

                if result.success and result.video_path:
                    # Upload to storage
                    filename = f"variant_{variant_idx:02d}_clip_{prompt_obj.scene_index:02d}.mp4"
                    stored = storage.upload_video(session_id, result.video_path, filename)

                    variant_clips.append({
                        "clip_index": prompt_obj.scene_index,
                        "scene_index": prompt_obj.scene_index,
                        "duration": prompt_obj.duration,
                        "prompt": prompt_obj.prompt,
                        "video_url": stored.url,
                        "status": "completed",
                        "cost": result.cost_estimate
                    })
                else:
                    variant_clips.append({
                        "clip_index": prompt_obj.scene_index,
                        "scene_index": prompt_obj.scene_index,
                        "duration": prompt_obj.duration,
                        "prompt": prompt_obj.prompt,
                        "video_url": None,
                        "status": "failed",
                        "error": result.error,
                        "cost": 0.0
                    })

                completed_generations += 1

            all_variants.append({
                "variant_index": variant_idx,
                "clips": variant_clips,
                "status": "completed" if all(c["status"] == "completed" for c in variant_clips) else "partial",
                "total_cost": sum(c.get("cost", 0) for c in variant_clips)
            })

        # === Step 6: Finalize ===
        total_cost = sum(v["total_cost"] for v in all_variants)

        update_job_status(
            session_id,
            status="completed",
            progress=100.0,
            current_step="All variants generated successfully",
            variants=all_variants,
            total_cost=total_cost,
            variants_completed=num_variants,
            variants_total=num_variants
        )

        # Cleanup temp files
        video_downloader.cleanup(session_id)

        return {
            "session_id": session_id,
            "status": "completed",
            "variants": all_variants,
            "total_cost": total_cost
        }

    except Exception as e:
        update_job_status(
            session_id,
            status="failed",
            progress=0.0,
            current_step="Pipeline failed",
            error=str(e)
        )
        raise self.retry(exc=e, countdown=60)


@celery_app.task
def cleanup_old_sessions(max_age_hours: int = 24):
    """Cleanup sessions older than max_age_hours"""
    # TODO: Implement session cleanup logic
    pass
