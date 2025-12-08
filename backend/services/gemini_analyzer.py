"""
Gemini Video Analyzer - Multi-Model Prompt Generation

Analyzes videos with Gemini and generates optimized prompts for:
- Sora 2 (OpenAI) - Cinematographer-style production briefs
- Veo 3.1 (Google) - 5-part formula with timestamp prompting

Based on official documentation:
- Sora 2: https://github.com/openai/openai-cookbook/blob/main/examples/sora/sora2_prompting_guide.ipynb
- Veo 3.1: https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1
- Gemini: https://ai.google.dev/gemini-api/docs/video-understanding
"""
import json
from pathlib import Path
from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from enum import Enum

import google.generativeai as genai

from config import settings
from services.scene_detector import Scene


# ============================================================================
# Enums for Target Models
# ============================================================================

class TargetModel(str, Enum):
    SORA_2 = "sora-2"
    VEO_3 = "veo-3.1"


# ============================================================================
# Pydantic Models for Structured Output
# ============================================================================

class ScenePrompt(BaseModel):
    """Generated prompt for a single scene"""
    scene_index: int = Field(description="Zero-based index of the scene")
    start_time: float = Field(description="Start time in seconds")
    end_time: float = Field(description="End time in seconds")
    duration: float = Field(description="Scene duration in seconds")

    # The generated prompt optimized for target model
    prompt: str = Field(description="The optimized prompt for video generation")

    # Scene analysis (for reference)
    camera_shot: str = Field(description="Shot type: wide, medium, close-up, etc.")
    camera_movement: str = Field(description="Camera movement: static, pan, dolly, tracking, etc.")
    subject_action: str = Field(description="What the subject/product is doing")
    lighting: str = Field(description="Lighting description")
    mood: str = Field(description="Overall mood/atmosphere")

    # Audio (if applicable)
    has_audio: bool = Field(description="Whether scene has significant audio")
    audio_description: Optional[str] = Field(description="Audio/dialogue description if present")


class VideoPromptResult(BaseModel):
    """Complete video analysis with model-optimized prompts"""
    product_name: str = Field(description="The product being showcased")
    target_model: str = Field(description="Target model: sora-2 or veo-3.1")
    total_duration: float = Field(description="Total video duration in seconds")
    scene_count: int = Field(description="Number of scenes")

    # Scene-by-scene prompts
    scene_prompts: List[ScenePrompt] = Field(description="Optimized prompt for each scene")

    # Overall style guide
    visual_style: str = Field(description="Overall visual style description")
    color_palette: str = Field(description="Dominant colors: e.g., 'warm amber, cream, soft white'")
    film_reference: str = Field(description="Film stock/era reference: e.g., '35mm Kodak, 2020s digital'")

    # For seamless strategy - full video prompt
    full_video_prompt: Optional[str] = Field(description="Single prompt for entire video if using seamless strategy")


# ============================================================================
# Prompt Templates for Target Models
# ============================================================================

SORA_2_SYSTEM_PROMPT = """You are an expert cinematographer creating production briefs for Sora 2 video generation.

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

VEO_3_SYSTEM_PROMPT = """You are an expert video producer creating prompts for Google Veo 3.1 video generation.

## VEO 3.1 PROMPTING RULES (from Google's official guide):

### 5-Part Formula for each scene:
[Cinematography] + [Subject] + [Action] + [Context] + [Style & Ambiance]

### Example structure:
```
[Camera shot and movement], [subject with product description], [action being performed],
[environment and setting details], [style, lighting, and mood].
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


# ============================================================================
# Main Analyzer Class
# ============================================================================

class GeminiAnalyzer:
    """
    Analyzes videos and generates model-optimized prompts.

    Supports:
    - Sora 2: OpenAI's cinematographer-style production briefs
    - Veo 3.1: Google's 5-part formula with timestamp support
    """

    def __init__(self):
        genai.configure(api_key=settings.google_gemini_api_key)

        # Primary model for video analysis
        self.model = genai.GenerativeModel(
            "gemini-2.5-pro-preview-06-05",
            generation_config={
                "temperature": 0.4,  # Slightly creative but consistent
                "response_mime_type": "application/json",
            }
        )

        # Fallback model
        self.fallback_model = genai.GenerativeModel(
            "gemini-2.0-flash-exp",
            generation_config={
                "temperature": 0.4,
                "response_mime_type": "application/json",
            }
        )

    def analyze_video(
        self,
        video_path: str,
        product_name: str,
        scenes: List[Scene],
        target_model: TargetModel = TargetModel.VEO_3
    ) -> VideoPromptResult:
        """
        Analyze video and generate optimized prompts for the target model.

        Args:
            video_path: Path to video file
            product_name: Exact product name (mentioned multiple times for emphasis)
            scenes: List of detected scenes with timestamps
            target_model: Which model to optimize prompts for (sora-2 or veo-3.1)

        Returns:
            VideoPromptResult with scene-by-scene optimized prompts
        """
        # Upload video to Gemini File API
        video_file = genai.upload_file(video_path)

        # Wait for processing
        import time
        while video_file.state.name == "PROCESSING":
            time.sleep(2)
            video_file = genai.get_file(video_file.name)

        if video_file.state.name == "FAILED":
            raise ValueError(f"Video processing failed: {video_file.state.name}")

        # Build prompt based on target model
        if target_model == TargetModel.SORA_2:
            system_prompt = SORA_2_SYSTEM_PROMPT
            prompt = self._build_sora_prompt(product_name, scenes)
        else:
            system_prompt = VEO_3_SYSTEM_PROMPT
            prompt = self._build_veo_prompt(product_name, scenes)

        # Get JSON schema
        json_schema = VideoPromptResult.model_json_schema()

        try:
            # Generate with structured output
            response = self.model.generate_content(
                contents=[
                    {"role": "user", "parts": [video_file]},
                    {"role": "user", "parts": [system_prompt + "\n\n" + prompt]}
                ],
                generation_config={
                    "temperature": 0.4,
                    "response_mime_type": "application/json",
                    "response_schema": json_schema,
                }
            )

            result_dict = json.loads(response.text)
            return VideoPromptResult(**result_dict)

        except Exception as e:
            print(f"Primary model failed, trying fallback: {e}")
            response = self.fallback_model.generate_content(
                contents=[video_file, system_prompt + "\n\n" + prompt + "\n\nRespond with valid JSON only."]
            )
            result_dict = json.loads(response.text)
            return VideoPromptResult(**result_dict)

    def _build_sora_prompt(self, product_name: str, scenes: List[Scene]) -> str:
        """Build analysis prompt optimized for Sora 2 output."""

        scene_info = "\n".join([
            f"  Scene {s.index + 1}: {self._format_time(s.start_time)} - {self._format_time(s.end_time)} ({s.duration:.1f}s)"
            for s in scenes
        ])

        total_duration = scenes[-1].end_time if scenes else 0

        return f"""## TASK
Analyze this product video for "{product_name}" and generate SORA 2 OPTIMIZED prompts for each scene.

## VIDEO INFO
- Product: {product_name}
- Duration: {total_duration:.1f} seconds
- Scenes detected:
{scene_info}

## YOUR OUTPUT

For EACH scene, generate a production-brief style prompt following Sora 2 best practices:

1. **Analyze the scene visually:**
   - What camera shot/angle is used?
   - What camera movement?
   - How is {product_name} positioned?
   - What's the lighting setup?
   - What action is happening?

2. **Generate SORA 2 prompt using this format:**
```
[Detailed prose description of the scene with {product_name}]

Cinematography:
Camera shot: [specific framing]
Camera movement: [specific movement or static]
Lens: [focal length, DOF]
Mood: [tone]

Actions:
- [Beat 1]
- [Beat 2]
```

3. **Include audio description if speech/music is present**

## CRITICAL REMINDERS FOR SORA 2:
- Be SPECIFIC: "amber serum bottle catches warm window light" not "product is lit nicely"
- Use FILM TERMINOLOGY: 85mm shallow DOF, slow dolly-in, handheld tracking
- Actions in BEATS: "hand enters frame, lifts bottle, rotates 45 degrees"
- COLOR ANCHORS: Specify 3-5 dominant colors
- ONE camera move + ONE subject action per scene

## OUTPUT FORMAT
Return a VideoPromptResult JSON with target_model="sora-2" and optimized prompts for each scene."""

    def _build_veo_prompt(self, product_name: str, scenes: List[Scene]) -> str:
        """Build analysis prompt optimized for Veo 3.1 output."""

        scene_info = "\n".join([
            f"  Scene {s.index + 1}: {self._format_time(s.start_time)} - {self._format_time(s.end_time)} ({s.duration:.1f}s)"
            for s in scenes
        ])

        total_duration = scenes[-1].end_time if scenes else 0

        return f"""## TASK
Analyze this product video for "{product_name}" and generate VEO 3.1 OPTIMIZED prompts for each scene.

## VIDEO INFO
- Product: {product_name}
- Duration: {total_duration:.1f} seconds
- Scenes detected:
{scene_info}

## YOUR OUTPUT

For EACH scene, generate a prompt using Veo 3.1's 5-part formula:
[Cinematography] + [Subject] + [Action] + [Context] + [Style & Ambiance]

1. **Analyze the scene:**
   - Camera shot type and movement
   - How {product_name} appears in frame
   - What action/movement is shown
   - Environment and setting
   - Lighting and color mood

2. **Generate VEO 3.1 prompt using this structure:**
```
[Shot type and camera movement], [subject showing {product_name}], [action being performed],
[environment details], [style and lighting description].
[Audio: SFX or dialogue if applicable]
```

## VEO 3.1 SPECIFIC FORMATTING:
- Dialogue: A person says, "exact words here." (no subtitles)
- Sound effects: SFX: description of sound
- Ambient: Ambient noise: background description

## TIMESTAMP PROMPT (for full_video_prompt):
Also create a timestamp-based prompt combining all scenes:
```
[00:00-00:02] First scene description...
[00:02-00:04] Second scene description...
```

## CRITICAL REMINDERS FOR VEO 3.1:
- Use VEO camera vocabulary: dolly shot, tracking shot, crane shot, shallow DOF
- Specify lighting explicitly: soft window light, dramatic spotlight, warm fill
- Include color/mood: "warm color palette", "clean minimal aesthetic"
- Keep descriptions VISUAL - what the camera sees

## OUTPUT FORMAT
Return a VideoPromptResult JSON with target_model="veo-3.1" and optimized prompts for each scene.
Include full_video_prompt with timestamp-based prompt for seamless generation."""

    def _format_time(self, seconds: float) -> str:
        """Format seconds as MM:SS"""
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins:02d}:{secs:02d}"


# Singleton instance
gemini_analyzer = GeminiAnalyzer()
