import asyncio
import json
import redis
import traceback
from typing import Optional
from pathlib import Path
from celery import Celery

from config import settings
from services.video_downloader import video_downloader
from services.scene_detector import scene_detector
from services.gemini_analyzer import gemini_analyzer, TargetModel
from services.video_generator import video_generator, Provider, Model
from services.storage_manager import StorageManager
from services.image_processor import image_processor
from services.clip_segmenter import clip_segmenter
from services.pipeline_logger import PipelineLogger

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
    # Initialize logger for this session
    logger = PipelineLogger(session_id)

    logger.pipeline_step("PIPELINE_START", "started", {
        "session_id": session_id,
        "tiktok_url": tiktok_url,
        "product_name": product_name,
        "product_image_path": product_image_path,
        "product_image_exists": bool(product_image_path and Path(product_image_path).exists()),
        "num_variants": num_variants,
        "provider": provider,
        "model": model,
        "strategy": strategy,
    })

    storage = StorageManager()

    try:
        # === Step 1: Download TikTok Video ===
        logger.pipeline_step("DOWNLOAD", "started", {"url": tiktok_url})
        update_job_status(
            session_id,
            status="downloading",
            progress=5.0,
            current_step="Downloading TikTok video..."
        )

        download_result = video_downloader.download(tiktok_url, session_id)
        video_path = download_result["video_path"]

        logger.pipeline_step("DOWNLOAD", "completed", {
            "video_path": video_path,
            "duration": download_result["duration"],
            "video_exists": Path(video_path).exists(),
            "video_size_bytes": Path(video_path).stat().st_size if Path(video_path).exists() else 0,
        })

        update_job_status(
            session_id,
            status="downloading",
            progress=15.0,
            current_step="Video downloaded successfully",
            original_duration=download_result["duration"]
        )

        # === Step 2: Scene Detection ===
        logger.pipeline_step("SCENE_DETECTION", "started", {"video_path": video_path})
        update_job_status(
            session_id,
            status="analyzing",
            progress=20.0,
            current_step="Detecting scenes..."
        )

        scenes = scene_detector.detect_scenes(video_path, session_id)

        logger.pipeline_step("SCENE_DETECTION", "completed", {
            "scene_count": len(scenes),
            "scenes": [{"start": s.start_time, "end": s.end_time} for s in scenes] if scenes else [],
        })

        update_job_status(
            session_id,
            status="analyzing",
            progress=30.0,
            current_step=f"Detected {len(scenes)} scenes",
            scene_count=len(scenes)
        )

        # === Step 3: Calculate Clip Segments ===
        # Determine target model for prompt optimization
        if "sora" in model.lower():
            target_model = TargetModel.SORA_2
            prompt_type = "Sora 2"
        else:
            target_model = TargetModel.VEO_3
            prompt_type = "Veo 3.1"

        logger.info("CLIP_SEGMENTER", f"Using target model: {target_model.value}, prompt_type: {prompt_type}", {
            "target_model": target_model.value,
            "prompt_type": prompt_type,
            "model_input": model,
        })

        update_job_status(
            session_id,
            status="analyzing",
            progress=32.0,
            current_step="Calculating optimal clip segments..."
        )

        # Calculate clip segments based on video duration and model limits
        video_duration = download_result["duration"]
        clip_segments = clip_segmenter.calculate_segments(video_duration, model)

        logger.info("CLIP_SEGMENTER", f"Calculated {len(clip_segments)} clip segments", {
            "video_duration": video_duration,
            "num_clips": len(clip_segments),
            "clips": [
                {
                    "index": seg.clip_index,
                    "start": seg.start_time,
                    "end": seg.end_time,
                    "duration": seg.duration,
                    "target_duration": seg.target_duration,
                    "pacing": seg.pacing,
                }
                for seg in clip_segments
            ],
        })

        # Convert scene boundaries for clip alignment
        scene_boundaries = [s.end_time for s in scenes[:-1]] if len(scenes) > 1 else []

        update_job_status(
            session_id,
            status="analyzing",
            progress=35.0,
            current_step=f"Video {video_duration:.1f}s -> {len(clip_segments)} clips"
        )

        # === Step 4: Gemini Analysis for Clips ===
        logger.pipeline_step("GEMINI_ANALYSIS", "started", {
            "product_name": product_name,
            "num_clips": len(clip_segments),
            "target_model": target_model.value,
        })

        update_job_status(
            session_id,
            status="analyzing",
            progress=40.0,
            current_step=f"Analyzing video for {product_name} ({prompt_type} prompts)..."
        )

        # Convert clip_segments to dict format for Gemini
        clip_segments_dict = [
            {
                "clip_index": seg.clip_index,
                "start_time": seg.start_time,
                "end_time": seg.end_time,
                "duration": seg.duration,
                "target_duration": seg.target_duration,
                "pacing": seg.pacing,
                "pacing_note": seg.pacing_note
            }
            for seg in clip_segments
        ]

        # Use clip-based analysis
        analysis = gemini_analyzer.analyze_video_for_clips(
            video_path,
            product_name,
            clip_segments_dict,
            target_model=target_model
        )

        logger.pipeline_step("GEMINI_ANALYSIS", "completed", {
            "num_prompts": len(analysis.clip_prompts or []),
            "prompts_preview": [
                {
                    "clip_index": p.get("clip_index") if isinstance(p, dict) else getattr(p, "clip_index", 0),
                    "prompt_preview": (p.get("prompt") if isinstance(p, dict) else getattr(p, "prompt", ""))[:150],
                }
                for p in (analysis.clip_prompts or [])
            ],
        })

        update_job_status(
            session_id,
            status="analyzing",
            progress=55.0,
            current_step=f"Generated {len(analysis.clip_prompts or [])} {prompt_type} prompts"
        )

        # Get prompts from clip_prompts
        prompts = analysis.clip_prompts or []

        if not prompts:
            logger.error("GEMINI_ANALYSIS", "No prompts generated!", data={
                "analysis_result": str(analysis)[:500],
            })

        update_job_status(
            session_id,
            status="analyzing",
            progress=60.0,
            current_step=f"Ready to generate {len(prompts)} clips per variant"
        )

        # === Step 5: Generate Videos (N Variants) ===
        logger.pipeline_step("VIDEO_GENERATION", "started", {
            "num_variants": num_variants,
            "prompts_per_variant": len(prompts),
            "total_generations": num_variants * len(prompts),
            "provider": provider,
            "model": model,
        })

        provider_enum = Provider(provider)
        model_enum = Model(model)

        total_generations = num_variants * len(prompts)
        completed_generations = 0
        all_variants = []

        for variant_idx in range(num_variants):
            logger.info("VARIANT", f"Starting variant {variant_idx + 1}/{num_variants}", {
                "variant_index": variant_idx,
            })

            variant_clips = []
            last_frame_path = None  # For chaining clips

            for clip_prompt in prompts:
                # Handle both dict and object formats
                if isinstance(clip_prompt, dict):
                    clip_index = clip_prompt.get("clip_index", 0)
                    prompt_text = clip_prompt.get("prompt", "")
                    target_duration = clip_prompt.get("target_duration", 15.0)
                    clip_duration = clip_prompt.get("duration", target_duration)
                else:
                    clip_index = getattr(clip_prompt, "clip_index", 0)
                    prompt_text = getattr(clip_prompt, "prompt", "")
                    target_duration = getattr(clip_prompt, "target_duration", 15.0)
                    clip_duration = getattr(clip_prompt, "duration", target_duration)

                # Determine start frame for this clip
                # Clip 0: use product_image, Clip 1+: use last frame from previous clip
                start_frame = None
                if clip_index > 0 and last_frame_path:
                    start_frame = last_frame_path

                logger.info("CLIP_GENERATION", f"Generating clip {clip_index + 1}/{len(prompts)}", {
                    "variant_index": variant_idx,
                    "clip_index": clip_index,
                    "target_duration": target_duration,
                    "has_start_frame": start_frame is not None,
                    "start_frame_path": start_frame,
                    "start_frame_exists": bool(start_frame and Path(start_frame).exists()),
                    "using_product_image": clip_index == 0 and product_image_path is not None,
                    "product_image_path": product_image_path if clip_index == 0 else None,
                    "prompt_preview": prompt_text[:200],
                })

                update_job_status(
                    session_id,
                    status="generating",
                    progress=60.0 + (completed_generations / total_generations * 30.0),
                    current_step=f"Generating variant {variant_idx + 1}/{num_variants}, "
                                 f"clip {clip_index + 1}/{len(prompts)} ({target_duration:.0f}s)"
                                 f"{' [chained]' if start_frame else ''}...",
                    variants_completed=variant_idx,
                    variants_total=num_variants
                )

                # Run async generation with correct duration for model
                result = asyncio.run(video_generator.generate(
                    prompt=prompt_text,
                    provider=provider_enum,
                    model=model_enum,
                    product_image_path=product_image_path,
                    start_frame_path=start_frame,  # Chain from previous clip
                    duration=target_duration,
                    session_id=session_id,
                    variant_index=variant_idx * len(prompts) + clip_index
                ))

                if result.success and result.video_path:
                    logger.success("CLIP_GENERATION", f"Clip generated successfully: {result.video_path}", {
                        "variant_index": variant_idx,
                        "clip_index": clip_index,
                        "video_path": result.video_path,
                        "video_exists": Path(result.video_path).exists(),
                        "video_size_bytes": Path(result.video_path).stat().st_size if Path(result.video_path).exists() else 0,
                        "cost": result.cost_estimate,
                    })

                    # Extract last frame for next clip chaining
                    try:
                        logger.info("FRAME_CHAIN", f"Extracting last frame for clip chaining", {
                            "source_video": result.video_path,
                        })
                        last_frame_path = image_processor.extract_last_frame(result.video_path, session_id=session_id)
                        logger.success("FRAME_CHAIN", f"Last frame extracted: {last_frame_path}", {
                            "frame_path": last_frame_path,
                            "frame_exists": Path(last_frame_path).exists() if last_frame_path else False,
                            "frame_size_bytes": Path(last_frame_path).stat().st_size if last_frame_path and Path(last_frame_path).exists() else 0,
                        })
                    except Exception as e:
                        logger.error("FRAME_CHAIN", f"Failed to extract last frame", error=e)
                        last_frame_path = None

                    # Upload to storage with descriptive name: clip_1_of_3.mp4
                    total_clips = len(prompts)
                    filename = f"v{variant_idx + 1}_clip_{clip_index + 1}_of_{total_clips}.mp4"
                    stored = storage.upload_video(session_id, result.video_path, filename)

                    logger.success("STORAGE", f"Video uploaded: {filename}", {
                        "filename": filename,
                        "url": stored.url,
                    })

                    variant_clips.append({
                        "clip_index": clip_index,
                        "scene_index": clip_index,
                        "duration": clip_duration,
                        "target_duration": target_duration,
                        "prompt": prompt_text,
                        "video_url": stored.url,
                        "status": "completed",
                        "cost": result.cost_estimate
                    })
                else:
                    logger.error("CLIP_GENERATION", f"Clip generation FAILED", data={
                        "variant_index": variant_idx,
                        "clip_index": clip_index,
                        "error": result.error,
                    })

                    # Reset chaining if clip failed
                    last_frame_path = None
                    variant_clips.append({
                        "clip_index": clip_index,
                        "scene_index": clip_index,
                        "duration": clip_duration,
                        "target_duration": target_duration,
                        "prompt": prompt_text,
                        "video_url": None,
                        "status": "failed",
                        "error": result.error,
                        "cost": 0.0
                    })

                completed_generations += 1

            variant_status = "completed" if all(c["status"] == "completed" for c in variant_clips) else "partial"
            variant_cost = sum(c.get("cost", 0) for c in variant_clips)

            logger.info("VARIANT", f"Variant {variant_idx + 1} complete: {variant_status}", {
                "variant_index": variant_idx,
                "status": variant_status,
                "clips_completed": sum(1 for c in variant_clips if c["status"] == "completed"),
                "clips_failed": sum(1 for c in variant_clips if c["status"] == "failed"),
                "total_cost": variant_cost,
            })

            all_variants.append({
                "variant_index": variant_idx,
                "clips": variant_clips,
                "status": variant_status,
                "total_cost": variant_cost
            })

        # === Step 6: Finalize ===
        total_cost = sum(v["total_cost"] for v in all_variants)
        total_completed = sum(1 for v in all_variants if v["status"] == "completed")

        logger.pipeline_step("PIPELINE_COMPLETE", "completed", {
            "total_variants": num_variants,
            "completed_variants": total_completed,
            "total_cost": total_cost,
            "all_variants_summary": [
                {
                    "index": v["variant_index"],
                    "status": v["status"],
                    "cost": v["total_cost"],
                    "clips_count": len(v["clips"]),
                }
                for v in all_variants
            ],
        })

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
        logger.critical("PIPELINE_ERROR", f"Pipeline FAILED with exception", error=e, data={
            "session_id": session_id,
            "traceback": traceback.format_exc(),
        })

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
