import httpx
import asyncio
import base64
import time
import redis
from pathlib import Path
from typing import Optional, Literal
from dataclasses import dataclass
from enum import Enum

from config import settings
from services.pipeline_logger import PipelineLogger


def get_api_key(key_name: str, fallback: str) -> str:
    """Get API key from Redis settings or fall back to .env"""
    try:
        r = redis.from_url(settings.redis_url)
        key = r.hget("app_settings", key_name)
        if key:
            return key.decode("utf-8") if isinstance(key, bytes) else key
    except Exception:
        pass
    return fallback


class Provider(str, Enum):
    KIE_AI = "kie.ai"
    DEFAPI = "defapi.org"


class Model(str, Enum):
    # Kie.ai models
    VEO_31_FAST = "veo-3.1-fast"
    VEO_31_QUALITY = "veo-3.1-quality"
    SORA_2 = "sora-2"
    # defapi.org models
    DEFAPI_VEO_31 = "defapi-veo-3.1"
    DEFAPI_SORA_2 = "defapi-sora-2"


@dataclass
class GenerationResult:
    """Result of video generation"""
    success: bool
    video_url: Optional[str] = None
    video_path: Optional[str] = None
    error: Optional[str] = None
    provider: str = ""
    model: str = ""
    cost_estimate: float = 0.0


class VideoGenerator:
    """Multi-provider video generation service"""

    # Cost estimates per request (in USD)
    COST_MAP = {
        (Provider.KIE_AI, Model.VEO_31_FAST): 0.40,
        (Provider.KIE_AI, Model.VEO_31_QUALITY): 2.00,
        (Provider.KIE_AI, Model.SORA_2): 0.15,
        (Provider.DEFAPI, Model.DEFAPI_VEO_31): 0.50,  # $0.5 per request
        (Provider.DEFAPI, Model.DEFAPI_SORA_2): 0.10,  # $0.1 per request
    }

    def __init__(self):
        self.kie_api_key = get_api_key("kie_ai_key", settings.kie_ai_api_key)
        self.defapi_api_key = get_api_key("defapi_key", settings.defapi_org_api_key)
        self.storage_path = Path(settings.storage_path)
        self.logger = PipelineLogger()

    async def generate(
        self,
        prompt: str,
        provider: Provider,
        model: Model,
        product_image_path: Optional[str] = None,
        start_frame_path: Optional[str] = None,
        duration: float = 8.0,
        session_id: str = "",
        variant_index: int = 0
    ) -> GenerationResult:
        """
        Generate video using specified provider and model.

        Args:
            prompt: Veo prompt for generation
            provider: kie.ai or defapi.org
            model: Model to use
            product_image_path: Path to product reference image
            start_frame_path: Path to start frame image (for clip chaining)
            duration: Target duration in seconds
            session_id: For organizing output files
            variant_index: Which variant this is (0-N)

        Returns:
            GenerationResult with video URL/path or error
        """
        # Set logger session
        self.logger.set_session(session_id)

        self.logger.info("VIDEO_GEN", f"Starting generation: provider={provider.value}, model={model.value}", {
            "provider": provider.value,
            "model": model.value,
            "duration_requested": duration,
            "variant_index": variant_index,
            "has_product_image": bool(product_image_path and Path(product_image_path).exists()),
            "has_start_frame": bool(start_frame_path and Path(start_frame_path).exists()),
            "prompt_length": len(prompt),
            "prompt_preview": prompt[:200] if prompt else None
        })

        try:
            # Check if this is a clip 2+ with start frame -> use Kie.ai I2V for true first-frame
            if start_frame_path and Path(start_frame_path).exists():
                self.logger.info("VIDEO_GEN", "Using Kie.ai I2V for clip chaining (true first-frame)", {
                    "start_frame_path": start_frame_path,
                    "reason": "Clip 2+ with start_frame - switching to I2V for visual continuity"
                })
                return await self._generate_kie_ai_i2v(
                    prompt, start_frame_path, duration, session_id, variant_index
                )

            if provider == Provider.KIE_AI:
                return await self._generate_kie_ai(
                    prompt, model, product_image_path, start_frame_path, duration, session_id, variant_index
                )
            elif provider == Provider.DEFAPI:
                return await self._generate_defapi(
                    prompt, model, product_image_path, start_frame_path, duration, session_id, variant_index
                )
            else:
                self.logger.error("VIDEO_GEN", f"Unknown provider: {provider}")
                return GenerationResult(
                    success=False,
                    error=f"Unknown provider: {provider}"
                )
        except Exception as e:
            self.logger.error("VIDEO_GEN", "Generation failed with exception", error=e)
            return GenerationResult(
                success=False,
                error=str(e),
                provider=provider.value,
                model=model.value
            )

    async def _generate_kie_ai(
        self,
        prompt: str,
        model: Model,
        product_image_path: Optional[str],
        start_frame_path: Optional[str],
        duration: float,
        session_id: str,
        variant_index: int
    ) -> GenerationResult:
        """Generate video using Kie.ai API"""

        # Map model to Kie.ai model names
        model_map = {
            Model.VEO_31_FAST: "veo-3.1-generate-video/fast",
            Model.VEO_31_QUALITY: "veo-3.1-generate-video/quality",
            Model.SORA_2: "sora-2-generate-video",
        }

        kie_model = model_map.get(model)
        if not kie_model:
            return GenerationResult(success=False, error=f"Model {model} not supported by Kie.ai")

        # Prepare request
        payload = {
            "prompt": prompt,
            "duration": min(duration, 8),  # Kie.ai max 8s per generation
        }

        # Priority: start_frame > product_image (start_frame for clip chaining)
        if start_frame_path and Path(start_frame_path).exists():
            with open(start_frame_path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode()
            payload["image"] = f"data:image/jpeg;base64,{image_b64}"
        elif product_image_path and Path(product_image_path).exists():
            with open(product_image_path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode()
            payload["image"] = f"data:image/jpeg;base64,{image_b64}"

        headers = {
            "Authorization": f"Bearer {self.kie_api_key}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=300) as client:
            # Submit generation job
            response = await client.post(
                f"https://api.kie.ai/v1/{kie_model}",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            result = response.json()

            # Poll for completion
            task_id = result.get("task_id") or result.get("id")
            video_url = await self._poll_kie_ai(client, task_id, headers)

            if video_url:
                # Download and save video
                video_path = await self._download_video(
                    client, video_url, session_id, variant_index
                )

                cost = self.COST_MAP.get((Provider.KIE_AI, model), 0.0)

                return GenerationResult(
                    success=True,
                    video_url=video_url,
                    video_path=video_path,
                    provider=Provider.KIE_AI.value,
                    model=model.value,
                    cost_estimate=cost
                )

            return GenerationResult(
                success=False,
                error="Generation timed out",
                provider=Provider.KIE_AI.value,
                model=model.value
            )

    async def _poll_kie_ai(
        self,
        client: httpx.AsyncClient,
        task_id: str,
        headers: dict,
        max_attempts: int = 60
    ) -> Optional[str]:
        """Poll Kie.ai for generation completion"""
        for _ in range(max_attempts):
            response = await client.get(
                f"https://api.kie.ai/v1/tasks/{task_id}",
                headers=headers
            )
            result = response.json()

            status = result.get("status")
            if status == "completed":
                return result.get("video_url") or result.get("output", {}).get("video_url")
            elif status == "failed":
                return None

            await asyncio.sleep(5)

        return None

    async def _generate_kie_ai_i2v(
        self,
        prompt: str,
        start_frame_path: str,
        duration: float,
        session_id: str,
        variant_index: int
    ) -> GenerationResult:
        """Generate video using Kie.ai Sora 2 Image-to-Video API (true first-frame)"""

        self.logger.info("KIE_I2V", f"Starting I2V generation with first frame: {start_frame_path}", {
            "start_frame_path": start_frame_path,
            "duration": duration,
            "variant_index": variant_index,
        })

        # Read and encode start frame
        with open(start_frame_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode()
        mime_type = "image/png" if start_frame_path.endswith(".png") else "image/jpeg"

        payload = {
            "prompt": prompt,
            "image_urls": [f"data:{mime_type};base64,{image_b64}"],
            "n_frames": 10,  # 10 seconds
            "aspect_ratio": "portrait"
        }

        headers = {
            "Authorization": f"Bearer {self.kie_api_key}",
            "Content-Type": "application/json"
        }

        self.logger.info("KIE_I2V", "Sending I2V request to Kie.ai", {
            "endpoint": "https://api.kie.ai/v1/sora-2-image-to-video",
            "n_frames": payload["n_frames"],
            "aspect_ratio": payload["aspect_ratio"],
        })

        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(
                "https://api.kie.ai/v1/sora-2-image-to-video",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            result = response.json()

            self.logger.info("KIE_I2V", f"I2V request submitted", {"response": result})

            task_id = result.get("task_id") or result.get("id")
            video_url = await self._poll_kie_ai(client, task_id, headers)

            if video_url:
                video_path = await self._download_video(client, video_url, session_id, variant_index)
                self.logger.success("KIE_I2V", f"I2V video generated successfully", {
                    "video_path": video_path,
                    "video_url": video_url[:100] if video_url else None,
                })
                return GenerationResult(
                    success=True,
                    video_url=video_url,
                    video_path=video_path,
                    provider=Provider.KIE_AI.value,
                    model="sora-2-i2v",
                    cost_estimate=0.15
                )

            self.logger.error("KIE_I2V", "I2V generation timed out")
            return GenerationResult(
                success=False,
                error="Generation timed out",
                provider=Provider.KIE_AI.value,
                model="sora-2-i2v"
            )

    async def _generate_defapi(
        self,
        prompt: str,
        model: Model,
        product_image_path: Optional[str],
        start_frame_path: Optional[str],
        duration: float,
        session_id: str,
        variant_index: int
    ) -> GenerationResult:
        """Generate video using defapi.org API (Veo 3.1 or Sora 2)"""

        self.logger.info("DEFAPI", f"Preparing defapi request for model: {model.value}", {
            "model": model.value,
            "product_image_exists": bool(product_image_path and Path(product_image_path).exists()),
            "start_frame_exists": bool(start_frame_path and Path(start_frame_path).exists()),
            "start_frame_path": start_frame_path,
            "product_image_path": product_image_path,
        })

        # Determine endpoint and payload based on model
        if model == Model.DEFAPI_SORA_2:
            # Sora 2 endpoint: /api/sora2/gen
            endpoint = "https://api.defapi.org/api/sora2/gen"

            # defapi Sora 2: Payload format from working n8n setup
            # - model: "sora-2" (NOT "sora-2-hd")
            # - duration: 15 (Integer, NOT string)
            # - size: "720x1280" (NOT aspect_ratio)
            # - input_reference: single data URI (NOT images array)
            payload = {
                "model": "sora-2",
                "prompt": prompt,
                "duration": "15",  # String! API expects "10"|"15"|"25"
                "size": "720x1280",  # TikTok portrait: width x height
            }

            self.logger.info("DEFAPI_SORA2", "Building Sora 2 payload", {
                "endpoint": endpoint,
                "model_in_payload": payload["model"],
                "duration_in_payload": payload["duration"],
                "duration_type": type(payload["duration"]).__name__,
                "size": payload["size"],
            })

            # Sora 2 uses "input_reference" for reference image (single data URI, not array)
            # Priority: start_frame > product_image (start_frame for clip chaining)
            if start_frame_path and Path(start_frame_path).exists():
                self.logger.info("DEFAPI_SORA2", f"Using START FRAME for clip chaining: {start_frame_path}", {
                    "frame_path": start_frame_path,
                    "frame_exists": True,
                    "frame_size_bytes": Path(start_frame_path).stat().st_size,
                })
                with open(start_frame_path, "rb") as f:
                    image_b64 = base64.b64encode(f.read()).decode()
                # Detect MIME type from extension
                mime_type = "image/png" if start_frame_path.endswith(".png") else "image/jpeg"
                payload["input_reference"] = f"data:{mime_type};base64,{image_b64}"
                self.logger.success("DEFAPI_SORA2", "Added start_frame as input_reference", {
                    "mime_type": mime_type,
                    "base64_length": len(image_b64),
                })
            elif product_image_path and Path(product_image_path).exists():
                self.logger.info("DEFAPI_SORA2", f"Using PRODUCT IMAGE (no start frame): {product_image_path}", {
                    "image_path": product_image_path,
                    "image_exists": True,
                    "image_size_bytes": Path(product_image_path).stat().st_size,
                    "reason": "No start_frame available, falling back to product image"
                })
                with open(product_image_path, "rb") as f:
                    image_b64 = base64.b64encode(f.read()).decode()
                # Detect MIME type from extension
                mime_type = "image/png" if product_image_path.endswith(".png") else "image/jpeg"
                payload["input_reference"] = f"data:{mime_type};base64,{image_b64}"
                self.logger.success("DEFAPI_SORA2", "Added product_image as input_reference", {
                    "mime_type": mime_type,
                    "base64_length": len(image_b64),
                })
            else:
                self.logger.warning("DEFAPI_SORA2", "NO IMAGE provided - generating without reference!", {
                    "start_frame_path": start_frame_path,
                    "start_frame_exists": bool(start_frame_path and Path(start_frame_path).exists()) if start_frame_path else False,
                    "product_image_path": product_image_path,
                    "product_image_exists": bool(product_image_path and Path(product_image_path).exists()) if product_image_path else False,
                })

            cost = 0.10  # $0.1 per request
        else:
            # Veo 3.1 endpoint: /api/google/veo/generate
            endpoint = "https://api.defapi.org/api/google/veo/generate"
            payload = {
                "model": "google/veo3.1-fast",
                "prompt": prompt,
                "aspect_ratio": "9:16",  # TikTok format
            }

            self.logger.info("DEFAPI_VEO", "Building Veo 3.1 payload", {
                "endpoint": endpoint,
                "model_in_payload": payload["model"],
                "aspect_ratio": payload["aspect_ratio"],
            })

            # Veo uses "image" for reference image
            # Priority: start_frame > product_image (start_frame for clip chaining)
            if start_frame_path and Path(start_frame_path).exists():
                self.logger.info("DEFAPI_VEO", f"Using START FRAME: {start_frame_path}")
                with open(start_frame_path, "rb") as f:
                    image_b64 = base64.b64encode(f.read()).decode()
                payload["image"] = f"data:image/jpeg;base64,{image_b64}"
            elif product_image_path and Path(product_image_path).exists():
                self.logger.info("DEFAPI_VEO", f"Using PRODUCT IMAGE: {product_image_path}")
                with open(product_image_path, "rb") as f:
                    image_b64 = base64.b64encode(f.read()).decode()
                payload["image"] = f"data:image/jpeg;base64,{image_b64}"
            cost = 0.50  # $0.5 per request

        headers = {
            "Authorization": f"Bearer {self.defapi_api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        # Log the complete payload (without base64 images for brevity)
        payload_for_log = {k: v for k, v in payload.items() if k != "images" and k != "image"}
        payload_for_log["has_images"] = "images" in payload
        payload_for_log["has_image"] = "image" in payload

        self.logger.api_request("DEFAPI", endpoint, payload_for_log)

        start_time = time.time()

        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(endpoint, json=payload, headers=headers)

            duration_ms = (time.time() - start_time) * 1000

            self.logger.info("DEFAPI", f"Initial response received", {
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            })

            response.raise_for_status()
            result = response.json()

            self.logger.api_response("DEFAPI", response.status_code, result, duration_ms)

            # Response format: {"code": 0, "message": "ok", "data": {"task_id": "..."}}
            if result.get("code") != 0:
                self.logger.error("DEFAPI", f"API returned error code: {result.get('code')}", data={
                    "code": result.get("code"),
                    "message": result.get("message"),
                    "full_response": result,
                })
                return GenerationResult(
                    success=False,
                    error=result.get("message", "API error"),
                    provider=Provider.DEFAPI.value,
                    model=model.value
                )

            task_id = result.get("data", {}).get("task_id")
            if not task_id:
                self.logger.error("DEFAPI", "No task_id in response", data={"response": result})
                return GenerationResult(
                    success=False,
                    error="No task_id in response",
                    provider=Provider.DEFAPI.value,
                    model=model.value
                )

            self.logger.success("DEFAPI", f"Task created: {task_id}", {"task_id": task_id})

            video_url = await self._poll_defapi(client, task_id, headers, is_sora=model == Model.DEFAPI_SORA_2)

            if video_url:
                self.logger.success("DEFAPI", f"Video URL received: {video_url[:100]}...")

                video_path = await self._download_video(
                    client, video_url, session_id, variant_index
                )

                self.logger.success("DEFAPI", f"Video downloaded: {video_path}", {
                    "video_path": video_path,
                    "video_size_bytes": Path(video_path).stat().st_size if Path(video_path).exists() else 0,
                })

                return GenerationResult(
                    success=True,
                    video_url=video_url,
                    video_path=video_path,
                    provider=Provider.DEFAPI.value,
                    model=model.value,
                    cost_estimate=cost
                )

            self.logger.error("DEFAPI", "Generation timed out - no video URL received")
            return GenerationResult(
                success=False,
                error="Generation timed out",
                provider=Provider.DEFAPI.value,
                model=model.value
            )

    async def _poll_defapi(
        self,
        client: httpx.AsyncClient,
        task_id: str,
        headers: dict,
        max_attempts: int = 120,
        is_sora: bool = False
    ) -> Optional[str]:
        """Poll defapi.org for generation completion"""

        poll_endpoint = f"https://api.defapi.org/api/task/query?task_id={task_id}"
        self.logger.info("DEFAPI_POLL", f"Starting polling for task: {task_id}", {
            "task_id": task_id,
            "max_attempts": max_attempts,
            "poll_interval_sec": 5,
            "is_sora": is_sora,
        })

        for attempt in range(max_attempts):
            # Same endpoint for both Veo and Sora: /api/task/query?task_id=...
            response = await client.get(poll_endpoint, headers=headers)
            result = response.json()

            # Response format: {"code": 0, "data": {"task_id": "...", "status": "...", "result": {...}}}
            if result.get("code") != 0:
                self.logger.warning("DEFAPI_POLL", f"Attempt {attempt+1}: Non-zero code", {
                    "attempt": attempt + 1,
                    "code": result.get("code"),
                    "message": result.get("message"),
                })
                await asyncio.sleep(5)
                continue

            data = result.get("data", {})
            status = data.get("status")

            self.logger.debug("DEFAPI_POLL", f"Attempt {attempt+1}: status={status}", {
                "attempt": attempt + 1,
                "status": status,
                "has_result": "result" in data,
            })

            if status in ["completed", "success"]:
                video_result = data.get("result")
                self.logger.success("DEFAPI_POLL", f"Task completed! Extracting video URL...", {
                    "status": status,
                    "result_type": type(video_result).__name__,
                    "result_preview": str(video_result)[:200] if video_result else None,
                })

                if video_result:
                    # Sora 2 returns {"video": "url"}, Veo returns {"video_url": "url"}
                    if isinstance(video_result, str):
                        self.logger.info("DEFAPI_POLL", "Result is direct URL string")
                        return video_result
                    elif isinstance(video_result, dict):
                        video_url = (video_result.get("video") or
                                    video_result.get("video_url") or
                                    video_result.get("url"))
                        self.logger.info("DEFAPI_POLL", f"Extracted video URL from dict", {
                            "video_key": "video" if "video" in video_result else ("video_url" if "video_url" in video_result else "url"),
                            "all_keys": list(video_result.keys()),
                        })
                        return video_url
                self.logger.error("DEFAPI_POLL", "Completed but no result data!", {"data": data})
                return None
            elif status in ["failed", "error"]:
                self.logger.error("DEFAPI_POLL", f"Task FAILED with status: {status}", {
                    "status": status,
                    "full_data": data,
                })
                return None

            await asyncio.sleep(5)

        self.logger.error("DEFAPI_POLL", f"Polling timed out after {max_attempts} attempts", {
            "max_attempts": max_attempts,
            "total_wait_sec": max_attempts * 5,
        })
        return None

    async def _download_video(
        self,
        client: httpx.AsyncClient,
        video_url: str,
        session_id: str,
        variant_index: int
    ) -> str:
        """Download generated video to storage"""
        output_dir = self.storage_path / session_id
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / f"variant_{variant_index:03d}.mp4"

        self.logger.info("DOWNLOAD", f"Downloading video...", {
            "video_url": video_url[:100],
            "output_path": str(output_path),
        })

        start_time = time.time()
        response = await client.get(video_url)
        response.raise_for_status()

        download_time_ms = (time.time() - start_time) * 1000

        with open(output_path, "wb") as f:
            f.write(response.content)

        file_size = output_path.stat().st_size

        self.logger.success("DOWNLOAD", f"Video saved: {output_path}", {
            "output_path": str(output_path),
            "file_size_bytes": file_size,
            "file_size_mb": round(file_size / (1024 * 1024), 2),
            "download_time_ms": download_time_ms,
        })

        return str(output_path)


# Singleton instance
video_generator = VideoGenerator()
