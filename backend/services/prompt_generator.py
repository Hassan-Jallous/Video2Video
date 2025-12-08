from typing import List
from dataclasses import dataclass

from services.gemini_analyzer import VideoAnalysis, SceneAnalysis


@dataclass
class VeoPrompt:
    """Generated prompt for Veo video generation"""
    scene_index: int
    duration: float
    prompt: str
    negative_prompt: str


class PromptGenerator:
    """Generate Veo-optimized prompts from video analysis"""

    def __init__(self):
        # Negative prompt to avoid common issues
        self.default_negative = (
            "blurry, low quality, distorted, watermark, text overlay, "
            "wrong product, different product, morphing, glitching"
        )

    def generate_prompts(
        self,
        analysis: VideoAnalysis,
        product_name: str
    ) -> List[VeoPrompt]:
        """
        Generate Veo prompts for each scene.

        Args:
            analysis: Complete video analysis from Gemini
            product_name: Exact product name to emphasize

        Returns:
            List of VeoPrompt objects, one per scene
        """
        prompts = []

        for scene in analysis.scenes:
            prompt = self._build_scene_prompt(scene, product_name, analysis.overall_style)
            prompts.append(VeoPrompt(
                scene_index=scene.scene_index,
                duration=scene.end_time - scene.start_time,
                prompt=prompt,
                negative_prompt=self.default_negative
            ))

        return prompts

    def _build_scene_prompt(
        self,
        scene: SceneAnalysis,
        product_name: str,
        overall_style: str
    ) -> str:
        """
        Build a single scene prompt following Veo best practices.

        Structure: [Camera] + [Product] + [Action] + [Environment] + [Style]
        Product name appears 2-3 times for emphasis.
        """
        parts = []

        # 1. Camera movement and framing
        if scene.camera_movement:
            parts.append(scene.camera_movement)

        # 2. Product positioning (first mention)
        if scene.product_position:
            parts.append(f"{product_name} {scene.product_position}")
        else:
            parts.append(f"{product_name} in frame")

        # 3. Person/hand interaction with product (second mention)
        if scene.person_interaction:
            interaction = scene.person_interaction
            if product_name.lower() not in interaction.lower():
                interaction = f"{interaction} with {product_name}"
            parts.append(interaction)

        # 4. Product action/demonstration (third mention if needed)
        if scene.product_action:
            action = scene.product_action
            if product_name.lower() not in action.lower():
                action = f"{product_name} {action}"
            parts.append(action)

        # 5. Environment
        if scene.environment:
            parts.append(scene.environment)

        # 6. Lighting
        if scene.lighting:
            parts.append(scene.lighting)

        # 7. Style
        style = scene.style_notes or overall_style
        if style:
            parts.append(style)

        # 8. Audio cue (if relevant)
        if scene.audio_description and "music" in scene.audio_description.lower():
            parts.append(scene.audio_description)

        # Combine parts
        prompt = ", ".join(filter(None, parts))

        # Ensure product name appears at least twice
        product_count = prompt.lower().count(product_name.lower())
        if product_count < 2:
            prompt = f"{product_name} product video. {prompt}"

        return prompt

    def generate_seamless_prompt(
        self,
        analysis: VideoAnalysis,
        product_name: str
    ) -> VeoPrompt:
        """
        Generate a single prompt for seamless (full video) generation.

        Used when strategy is 'seamless' instead of 'segments'.
        """
        # Combine key elements from all scenes
        camera_movements = set()
        environments = set()
        actions = []

        for scene in analysis.scenes:
            if scene.camera_movement:
                camera_movements.add(scene.camera_movement)
            if scene.environment:
                environments.add(scene.environment)
            if scene.product_action:
                actions.append(scene.product_action)

        # Build comprehensive prompt
        parts = [
            f"Product showcase video featuring {product_name}",
            ", ".join(camera_movements) if camera_movements else "dynamic camera work",
        ]

        if actions:
            parts.append(f"{product_name} being demonstrated: {', '.join(actions[:3])}")

        if environments:
            parts.append(f"Setting: {', '.join(environments)}")

        if analysis.overall_style:
            parts.append(analysis.overall_style)

        parts.append(f"Professional {product_name} advertisement")

        prompt = ". ".join(parts)

        return VeoPrompt(
            scene_index=-1,  # -1 indicates full video
            duration=analysis.total_duration,
            prompt=prompt,
            negative_prompt=self.default_negative
        )


# Singleton instance
prompt_generator = PromptGenerator()
