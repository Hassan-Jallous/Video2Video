import httpx
import asyncio
import base64
from pathlib import Path
from typing import Optional, Literal
from dataclasses import dataclass
from enum import Enum

from config import settings


class Provider(str, Enum):
    KIE_AI = "kie.ai"
    DEFAPI = "defapi.org"


class Model(str, Enum):
    # Kie.ai models
    VEO_31_FAST = "veo-3.1-fast"
    VEO_31_QUALITY = "veo-3.1-quality"
    SORA_2 = "sora-2"
    SORA_2_PRO = "sora-2-pro"
    # defapi.org models
    DEFAPI_VEO_31 = "defapi-veo-3.1"


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

    # Cost estimates per 8 seconds (in USD)
    COST_MAP = {
        (Provider.KIE_AI, Model.VEO_31_FAST): 0.40,
        (Provider.KIE_AI, Model.VEO_31_QUALITY): 2.00,
        (Provider.KIE_AI, Model.SORA_2): 0.15,
        (Provider.KIE_AI, Model.SORA_2_PRO): 0.50,
        (Provider.DEFAPI, Model.DEFAPI_VEO_31): 0.10,
    }

    def __init__(self):
        self.kie_api_key = settings.kie_ai_api_key
        self.defapi_api_key = settings.defapi_org_api_key
        self.storage_path = Path(settings.storage_path)

    async def generate(
        self,
        prompt: str,
        provider: Provider,
        model: Model,
        product_image_path: Optional[str] = None,
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
            duration: Target duration in seconds
            session_id: For organizing output files
            variant_index: Which variant this is (0-N)

        Returns:
            GenerationResult with video URL/path or error
        """
        try:
            if provider == Provider.KIE_AI:
                return await self._generate_kie_ai(
                    prompt, model, product_image_path, duration, session_id, variant_index
                )
            elif provider == Provider.DEFAPI:
                return await self._generate_defapi(
                    prompt, model, product_image_path, duration, session_id, variant_index
                )
            else:
                return GenerationResult(
                    success=False,
                    error=f"Unknown provider: {provider}"
                )
        except Exception as e:
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
            Model.SORA_2_PRO: "sora-2-pro-generate-video",
        }

        kie_model = model_map.get(model)
        if not kie_model:
            return GenerationResult(success=False, error=f"Model {model} not supported by Kie.ai")

        # Prepare request
        payload = {
            "prompt": prompt,
            "duration": min(duration, 8),  # Kie.ai max 8s per generation
        }

        # Add reference image if provided
        if product_image_path and Path(product_image_path).exists():
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

    async def _generate_defapi(
        self,
        prompt: str,
        model: Model,
        product_image_path: Optional[str],
        duration: float,
        session_id: str,
        variant_index: int
    ) -> GenerationResult:
        """Generate video using defapi.org API"""

        payload = {
            "prompt": prompt,
            "model": "veo-3.1",
            "duration": int(min(duration, 8)),
        }

        # Add reference image if provided
        if product_image_path and Path(product_image_path).exists():
            with open(product_image_path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode()
            payload["reference_image"] = image_b64

        headers = {
            "Authorization": f"Bearer {self.defapi_api_key}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(
                "https://api.defapi.org/v1/video/generate",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            result = response.json()

            # Poll for completion
            task_id = result.get("task_id") or result.get("id")
            video_url = await self._poll_defapi(client, task_id, headers)

            if video_url:
                video_path = await self._download_video(
                    client, video_url, session_id, variant_index
                )

                return GenerationResult(
                    success=True,
                    video_url=video_url,
                    video_path=video_path,
                    provider=Provider.DEFAPI.value,
                    model=model.value,
                    cost_estimate=0.10
                )

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
        max_attempts: int = 60
    ) -> Optional[str]:
        """Poll defapi.org for generation completion"""
        for _ in range(max_attempts):
            response = await client.get(
                f"https://api.defapi.org/v1/video/status/{task_id}",
                headers=headers
            )
            result = response.json()

            status = result.get("status")
            if status in ["completed", "success"]:
                return result.get("video_url") or result.get("output_url")
            elif status in ["failed", "error"]:
                return None

            await asyncio.sleep(5)

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

        response = await client.get(video_url)
        response.raise_for_status()

        with open(output_path, "wb") as f:
            f.write(response.content)

        return str(output_path)


# Singleton instance
video_generator = VideoGenerator()
