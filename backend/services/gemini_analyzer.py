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
import redis

from config import settings
from services.scene_detector import Scene
from services.transcript_extractor import transcript_extractor, TranscriptResult


def get_gemini_api_key() -> str:
    """Get Gemini API key from Redis settings or fall back to .env"""
    try:
        r = redis.from_url(settings.redis_url)
        key = r.hget("app_settings", "gemini_key")
        if key:
            return key.decode("utf-8") if isinstance(key, bytes) else key
    except Exception:
        pass
    return settings.google_gemini_api_key


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


class ClipPrompt(BaseModel):
    """Generated prompt for a single clip (time-based segment)"""
    clip_index: int = Field(description="Zero-based index of the clip")
    start_time: float = Field(description="Start time in seconds")
    end_time: float = Field(description="End time in seconds")
    duration: float = Field(description="Clip duration in seconds")
    target_duration: float = Field(description="Target duration for AI generation")

    # The generated prompt optimized for target model
    prompt: str = Field(description="The optimized prompt for video generation")

    # Transcript portion for this clip
    transcript_text: str = Field(description="The exact dialogue/transcript for this clip")

    # Visual details
    person_description: str = Field(description="Detailed person appearance if present")
    background_description: str = Field(description="Detailed background/environment")
    camera_description: str = Field(description="Camera shot and angle")
    lighting_description: str = Field(description="Lighting setup")
    action_description: str = Field(description="What happens in this clip")


class VideoPromptResult(BaseModel):
    """Complete video analysis with model-optimized prompts"""
    product_name: str = Field(description="The product being showcased")
    target_model: str = Field(description="Target model: sora-2 or veo-3.1")
    total_duration: float = Field(description="Total video duration in seconds")
    scene_count: int = Field(description="Number of scenes")

    # Scene-by-scene prompts (legacy - for compatibility)
    scene_prompts: List[ScenePrompt] = Field(description="Optimized prompt for each scene")

    # Clip-based prompts (NEW - for intelligent segmentation)
    clip_prompts: Optional[List[ClipPrompt]] = Field(default=None, description="Optimized prompts per time-based clip")

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

## PRIMARY GOAL: EXACT VISUAL CLONING
Your task is to create prompts that will generate a video that looks VISUALLY IDENTICAL to the original.
The AI video generator CANNOT see the original video - it only receives your text description.
Therefore, you MUST describe EVERY visual detail with extreme precision.

## MANDATORY VISUAL DETAILS TO EXTRACT AND INCLUDE:

### 1. PERSON DESCRIPTION (CRITICAL - if person appears):
- Gender: male/female
- Approximate age: young adult, middle-aged, etc.
- Ethnicity/appearance: skin tone, facial features
- Facial hair: beard style, mustache, clean-shaven
- Hair: color, length, style
- Clothing: EXACT colors, patterns, logos, patches, accessories
- Example: "A young Middle Eastern man with a dark full beard, short black hair, wearing a dark grey t-shirt with a small Germany flag patch on the chest"

### 2. CAMERA & FRAMING:
- Shot type: selfie-style, tripod medium shot, close-up, etc.
- Person's position in frame: centered, slightly off-center
- Distance from camera: close, medium, far
- Camera angle: eye-level, slightly below, above

### 3. BACKGROUND & ENVIRONMENT:
- Room type: bedroom, office, studio, kitchen, living room
- Wall color and texture
- Visible furniture or objects
- Doors, windows, decorations
- Example: "minimal modern room with off-white walls, visible black door handle on left, simple ceiling lamp"

### 4. LIGHTING:
- Light direction: from left, right, front, behind
- Light quality: soft natural daylight, harsh overhead, warm lamp
- Shadows: where they fall

### 5. ON-SCREEN TEXT/GRAPHICS (if present):
- Exact text content
- Position: top, bottom, center
- Style: font color, background

### 6. ACTIONS & BODY LANGUAGE:
- Exact gestures: hand movements, pointing, holding
- Facial expression: talking, smiling, serious
- Body position: standing, sitting, leaning

## SORA 2 PROMPTING RULES (from OpenAI's official guide):

### Structure for each scene prompt:
```
[Detailed person description with clothing] stands/sits in [exact background description].
[Camera shot type and angle], [lighting description].
[Person] [exact action/gesture] while [speaking/looking at camera].
The scene shows [product name] [how product appears if visible].

Cinematography:
Camera shot: [framing and angle]
Camera movement: [dolly, tracking, pan, static, handheld]
Lens: [focal length and characteristics]
Mood: [overall tone]

Actions:
- [Action 1: specific beat/gesture with timing]
- [Action 2: distinct movement]

[Dialogue if applicable - EXACT words from transcript]
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

## PRIMARY GOAL: EXACT VISUAL CLONING
Your task is to create prompts that will generate a video that looks VISUALLY IDENTICAL to the original.
The AI video generator CANNOT see the original video - it only receives your text description.
Therefore, you MUST describe EVERY visual detail with extreme precision.

## MANDATORY VISUAL DETAILS TO EXTRACT AND INCLUDE:

### 1. PERSON DESCRIPTION (CRITICAL - if person appears):
- Gender: male/female
- Approximate age: young adult, middle-aged, etc.
- Ethnicity/appearance: skin tone, facial features
- Facial hair: beard style, mustache, clean-shaven
- Hair: color, length, style
- Clothing: EXACT colors, patterns, logos, patches, accessories

### 2. BACKGROUND & ENVIRONMENT:
- Room type and wall colors
- Visible objects (doors, furniture, decorations)

### 3. CAMERA & LIGHTING:
- Shot type and angle
- Light direction and quality

### 4. ON-SCREEN TEXT/GRAPHICS (if present):
- Exact text content and position

## VEO 3.1 PROMPTING RULES (from Google's official guide):

### 5-Part Formula for each scene:
[Cinematography] + [Subject with EXACT appearance] + [Action] + [Context with EXACT background] + [Style & Ambiance]

### Example structure:
```
[Camera shot and movement], [subject with EXACT gender, age, clothing description], [action being performed],
[environment with wall colors and visible objects], [style, lighting, and mood].
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
        genai.configure(api_key=get_gemini_api_key())

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
        target_model: TargetModel = TargetModel.VEO_3,
        transcript: Optional[TranscriptResult] = None
    ) -> VideoPromptResult:
        """
        Analyze video and generate optimized prompts for the target model.

        Args:
            video_path: Path to video file
            product_name: Exact product name (mentioned multiple times for emphasis)
            scenes: List of detected scenes with timestamps
            target_model: Which model to optimize prompts for (sora-2 or veo-3.1)
            transcript: Pre-extracted transcript with timestamps (optional but recommended)

        Returns:
            VideoPromptResult with scene-by-scene optimized prompts
        """
        # Extract transcript if not provided
        if transcript is None:
            print("Extracting transcript from video...")
            transcript = transcript_extractor.extract_transcript(video_path)
            print(f"Transcript extracted: {len(transcript.segments)} segments, language: {transcript.language}")

        # Upload video to Gemini File API
        video_file = genai.upload_file(video_path)

        # Wait for processing
        import time
        while video_file.state.name == "PROCESSING":
            time.sleep(2)
            video_file = genai.get_file(video_file.name)

        if video_file.state.name == "FAILED":
            raise ValueError(f"Video processing failed: {video_file.state.name}")

        # Build prompt based on target model (now with transcript)
        if target_model == TargetModel.SORA_2:
            system_prompt = SORA_2_SYSTEM_PROMPT
            prompt = self._build_sora_prompt(product_name, scenes, transcript)
        else:
            system_prompt = VEO_3_SYSTEM_PROMPT
            prompt = self._build_veo_prompt(product_name, scenes, transcript)

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
            # Handle nested response structure and normalize fields
            result_dict = self._unwrap_response(result_dict, product_name, scenes, target_model)
            return VideoPromptResult(**result_dict)

        except Exception as e:
            print(f"Primary model failed, trying fallback: {e}")
            response = self.fallback_model.generate_content(
                contents=[video_file, system_prompt + "\n\n" + prompt + "\n\nRespond with valid JSON only."]
            )
            result_dict = json.loads(response.text)
            # Handle nested response structure and normalize fields
            result_dict = self._unwrap_response(result_dict, product_name, scenes, target_model)
            return VideoPromptResult(**result_dict)

    def analyze_video_for_clips(
        self,
        video_path: str,
        product_name: str,
        clip_segments: List[dict],  # List of ClipSegment as dicts
        target_model: TargetModel = TargetModel.SORA_2,
        transcript: Optional[TranscriptResult] = None
    ) -> VideoPromptResult:
        """
        Analyze video and generate optimized prompts for each CLIP segment.

        This method generates prompts based on time-based clips (not scene detection).
        Each clip gets a prompt with the transcript portion for that time range.

        Args:
            video_path: Path to video file
            product_name: Exact product name
            clip_segments: List of ClipSegment dicts with start_time, end_time, duration, pacing_note
            target_model: Which model to optimize prompts for
            transcript: Pre-extracted transcript with timestamps

        Returns:
            VideoPromptResult with clip_prompts list
        """
        # Extract transcript if not provided
        if transcript is None:
            print("Extracting transcript from video...")
            transcript = transcript_extractor.extract_transcript(video_path)
            print(f"Transcript extracted: {len(transcript.segments)} segments, language: {transcript.language}")

        # Upload video to Gemini File API
        video_file = genai.upload_file(video_path)

        # Wait for processing
        import time
        while video_file.state.name == "PROCESSING":
            time.sleep(2)
            video_file = genai.get_file(video_file.name)

        if video_file.state.name == "FAILED":
            raise ValueError(f"Video processing failed: {video_file.state.name}")

        # Build clip-based prompt
        prompt = self._build_clip_prompt(product_name, clip_segments, transcript, target_model)

        if target_model == TargetModel.SORA_2:
            system_prompt = SORA_2_SYSTEM_PROMPT
        else:
            system_prompt = VEO_3_SYSTEM_PROMPT

        try:
            response = self.model.generate_content(
                contents=[
                    {"role": "user", "parts": [video_file]},
                    {"role": "user", "parts": [system_prompt + "\n\n" + prompt]}
                ],
                generation_config={
                    "temperature": 0.4,
                    "response_mime_type": "application/json",
                }
            )

            result_dict = json.loads(response.text)
            result_dict = self._process_clip_response(result_dict, product_name, clip_segments, target_model, transcript)
            return VideoPromptResult(**result_dict)

        except Exception as e:
            print(f"Primary model failed for clips, trying fallback: {e}")
            response = self.fallback_model.generate_content(
                contents=[video_file, system_prompt + "\n\n" + prompt + "\n\nRespond with valid JSON only."]
            )
            result_dict = json.loads(response.text)
            result_dict = self._process_clip_response(result_dict, product_name, clip_segments, target_model, transcript)
            return VideoPromptResult(**result_dict)

    def _build_clip_prompt(
        self,
        product_name: str,
        clip_segments: List[dict],
        transcript: Optional[TranscriptResult],
        target_model: TargetModel
    ) -> str:
        """Build prompt for clip-based analysis."""

        # Build clip info with transcript portions
        clip_info_parts = []
        for clip in clip_segments:
            clip_start = clip.get("start_time", 0)
            clip_end = clip.get("end_time", 0)
            clip_duration = clip.get("duration", clip_end - clip_start)
            target_dur = clip.get("target_duration", clip_duration)
            pacing_note = clip.get("pacing_note", "")

            clip_line = f"  CLIP {clip.get('clip_index', 0) + 1}: {self._format_time(clip_start)} - {self._format_time(clip_end)} ({clip_duration:.1f}s → generate {target_dur:.1f}s)"

            # Get transcript for this clip
            if transcript and transcript.segments:
                clip_transcript = transcript_extractor.get_transcript_for_timerange(
                    transcript, clip_start, clip_end
                )
                if clip_transcript:
                    clip_line += f"\n    TRANSCRIPT: \"{clip_transcript}\""

            if pacing_note:
                clip_line += f"\n    {pacing_note}"

            clip_info_parts.append(clip_line)

        clip_info = "\n".join(clip_info_parts)
        total_duration = clip_segments[-1].get("end_time", 0) if clip_segments else 0

        # Full transcript
        transcript_section = ""
        if transcript and transcript.has_speech:
            transcript_section = f"""
## FULL TRANSCRIPT
Language: {transcript.language}
"{transcript.full_text}"

**IMPORTANT: Distribute this transcript across the clips. Each clip should contain the portion of speech that occurs during that time range.**
"""

        return f"""## TASK: GENERATE PROMPTS FOR {len(clip_segments)} CLIPS

Analyze this product video for "{product_name}" and generate ONE PROMPT PER CLIP.

## CLIP SEGMENTS (time-based, NOT scene-based):
{clip_info}
{transcript_section}
## CRITICAL REQUIREMENTS:

1. **ONE PROMPT PER CLIP** - You must generate exactly {len(clip_segments)} prompts, one for each clip segment above.

2. **VISUAL CLONING** - Each prompt must describe the EXACT visual appearance:
   - Person: gender, age, beard, hair, EXACT clothing with colors/logos
   - Background: room type, wall colors, visible objects (doors, furniture)
   - Camera: shot type, angle, position in frame
   - Lighting: direction, quality (soft/harsh, natural/artificial)

3. **TRANSCRIPT DISTRIBUTION** - Distribute the full transcript across clips:
   - Clip 1: First portion of dialogue
   - Clip 2: Next portion of dialogue
   - etc.
   - DO NOT repeat dialogue across clips!
   - Each clip should have unique dialogue matching its time range

4. **VISUAL CONSISTENCY** - All clips must have IDENTICAL:
   - Person appearance (same clothing, same person)
   - Background (same room, same objects)
   - Lighting setup
   - Camera style
   Only the ACTION and DIALOGUE should differ between clips.

## OUTPUT FORMAT

Return JSON with this structure:
{{
  "product_name": "{product_name}",
  "target_model": "{target_model.value}",
  "total_duration": {total_duration:.1f},
  "clip_prompts": [
    {{
      "clip_index": 0,
      "start_time": ...,
      "end_time": ...,
      "duration": ...,
      "target_duration": ...,
      "prompt": "Full detailed prompt for clip 1...",
      "transcript_text": "Exact dialogue for clip 1...",
      "person_description": "...",
      "background_description": "...",
      "camera_description": "...",
      "lighting_description": "...",
      "action_description": "..."
    }},
    // ... one entry per clip
  ],
  "scene_prompts": [],
  "visual_style": "...",
  "color_palette": "...",
  "film_reference": "..."
}}"""

    def _process_clip_response(
        self,
        result_dict: dict,
        product_name: str,
        clip_segments: List[dict],
        target_model: TargetModel,
        transcript: Optional[TranscriptResult]
    ) -> dict:
        """Process and normalize clip-based response from Gemini."""

        # Unwrap if nested
        if len(result_dict) == 1:
            key = list(result_dict.keys())[0]
            if isinstance(result_dict[key], dict) and key[0].isupper():
                result_dict = result_dict[key]

        # Ensure required fields
        result_dict.setdefault("product_name", product_name)
        result_dict.setdefault("target_model", target_model.value)
        result_dict.setdefault("total_duration", clip_segments[-1].get("end_time", 0) if clip_segments else 0)
        result_dict.setdefault("scene_count", len(clip_segments))
        result_dict.setdefault("scene_prompts", [])  # Empty for clip-based
        result_dict.setdefault("visual_style", "cinematic commercial style")
        result_dict.setdefault("color_palette", "warm, natural tones")
        result_dict.setdefault("film_reference", "modern digital commercial")
        result_dict.setdefault("full_video_prompt", None)

        # Ensure clip_prompts exists with fallback
        if "clip_prompts" not in result_dict or not result_dict["clip_prompts"]:
            # Create fallback prompts
            result_dict["clip_prompts"] = []
            for clip in clip_segments:
                clip_start = clip.get("start_time", 0)
                clip_end = clip.get("end_time", 0)

                # Get transcript for this clip
                clip_transcript = ""
                if transcript and transcript.segments:
                    clip_transcript = transcript_extractor.get_transcript_for_timerange(
                        transcript, clip_start, clip_end
                    ) or ""

                result_dict["clip_prompts"].append({
                    "clip_index": clip.get("clip_index", 0),
                    "start_time": clip_start,
                    "end_time": clip_end,
                    "duration": clip.get("duration", clip_end - clip_start),
                    "target_duration": clip.get("target_duration", clip.get("duration", 15)),
                    "prompt": f"A commercial scene showcasing {product_name} with professional lighting and composition.",
                    "transcript_text": clip_transcript,
                    "person_description": "person in casual attire",
                    "background_description": "modern minimal room",
                    "camera_description": "medium shot",
                    "lighting_description": "soft natural light",
                    "action_description": "presenting product"
                })

        # Normalize clip_prompts
        normalized_clips = []
        for i, clip in enumerate(result_dict["clip_prompts"]):
            orig_clip = clip_segments[i] if i < len(clip_segments) else {}
            normalized = {
                "clip_index": clip.get("clip_index", i),
                "start_time": clip.get("start_time", orig_clip.get("start_time", 0)),
                "end_time": clip.get("end_time", orig_clip.get("end_time", 0)),
                "duration": clip.get("duration", orig_clip.get("duration", 0)),
                "target_duration": clip.get("target_duration", orig_clip.get("target_duration", 15)),
                "prompt": clip.get("prompt", ""),
                "transcript_text": clip.get("transcript_text", ""),
                "person_description": clip.get("person_description", ""),
                "background_description": clip.get("background_description", ""),
                "camera_description": clip.get("camera_description", ""),
                "lighting_description": clip.get("lighting_description", ""),
                "action_description": clip.get("action_description", "")
            }
            normalized_clips.append(normalized)

        result_dict["clip_prompts"] = normalized_clips

        return result_dict

    def _build_sora_prompt(self, product_name: str, scenes: List[Scene], transcript: Optional[TranscriptResult] = None) -> str:
        """Build analysis prompt optimized for Sora 2 output."""

        scene_info_parts = []
        for s in scenes:
            scene_line = f"  Scene {s.index + 1}: {self._format_time(s.start_time)} - {self._format_time(s.end_time)} ({s.duration:.1f}s)"
            # Add transcript for this scene if available
            if transcript and transcript.segments:
                scene_transcript = transcript_extractor.get_transcript_for_timerange(
                    transcript, s.start_time, s.end_time
                )
                if scene_transcript:
                    scene_line += f"\n    SPOKEN TEXT: \"{scene_transcript}\""
            scene_info_parts.append(scene_line)

        scene_info = "\n".join(scene_info_parts)
        total_duration = scenes[-1].end_time if scenes else 0

        # Build transcript section
        transcript_section = ""
        if transcript and transcript.has_speech:
            transcript_section = f"""
## EXACT TRANSCRIPT (USE THIS - DO NOT MAKE UP TEXT!)
Language: {transcript.language}
Full transcript: "{transcript.full_text}"

**CRITICAL: The dialogue/voiceover above is EXACT. Use these EXACT words in the prompts!**
"""

        return f"""## TASK: VISUAL CLONING
Analyze this product video for "{product_name}" and generate SORA 2 OPTIMIZED prompts that will create a video VISUALLY IDENTICAL to the original.

**CRITICAL**: Sora 2 CANNOT see the original video. It only receives your text description.
Your prompts must describe EVERY visual detail so precisely that the generated video matches the original.

## VIDEO INFO
- Product: {product_name}
- Duration: {total_duration:.1f} seconds
- Scenes detected:
{scene_info}
{transcript_section}
## YOUR OUTPUT - MANDATORY DETAILS FOR EACH SCENE:

### 1. PERSON ANALYSIS (if person appears):
- Gender (male/female)
- Age range
- Facial features (beard, glasses, hair color/style)
- EXACT clothing with colors and any visible logos/patches
- Example: "young man with dark full beard, short black hair, dark grey t-shirt with Germany flag patch"

### 2. BACKGROUND ANALYSIS:
- Room type and wall colors
- Visible objects (doors, furniture, decorations)
- Example: "modern minimal room, off-white walls, black door handle visible on left"

### 3. CAMERA ANALYSIS:
- Shot type (medium, close-up, selfie-style)
- Person's position in frame
- Camera angle

### 4. LIGHTING ANALYSIS:
- Light source direction
- Quality (soft/harsh, natural/artificial)

### 5. ACTION ANALYSIS:
- What the person is doing
- Hand gestures
- Facial expression

### 6. ON-SCREEN TEXT (if any):
- Exact text content
- Position and style

## PROMPT FORMAT FOR EACH SCENE:
```
A [age] [gender] with [facial features], wearing [exact clothing description], [stands/sits] in [exact room description with wall color and visible objects].
[Shot type] at [camera angle], [lighting description].
[He/She] [exact action] while [speaking to camera / gesturing].
[On-screen text if present: "exact text"]

Cinematography:
Camera shot: [specific framing]
Camera movement: [static/movement type]
Lens: [focal length]
Mood: [tone]

Actions:
- [Specific gesture 1]
- [Specific gesture 2]

[EXACT dialogue from transcript if speaking]
```

## CRITICAL REMINDERS:
- **PERSON DETAILS ARE MANDATORY**: Never say "a person" - always specify gender, appearance, clothing
- **BACKGROUND DETAILS ARE MANDATORY**: Never say "a room" - describe wall color, visible objects
- **Be SPECIFIC**: Every detail matters for visual matching
- **DIALOGUE MUST BE EXACT**: Use the transcript word-for-word

## OUTPUT FORMAT
Return a VideoPromptResult JSON with target_model="sora-2" and detailed prompts for each scene."""

    def _build_veo_prompt(self, product_name: str, scenes: List[Scene], transcript: Optional[TranscriptResult] = None) -> str:
        """Build analysis prompt optimized for Veo 3.1 output."""

        scene_info_parts = []
        for s in scenes:
            scene_line = f"  Scene {s.index + 1}: {self._format_time(s.start_time)} - {self._format_time(s.end_time)} ({s.duration:.1f}s)"
            # Add transcript for this scene if available
            if transcript and transcript.segments:
                scene_transcript = transcript_extractor.get_transcript_for_timerange(
                    transcript, s.start_time, s.end_time
                )
                if scene_transcript:
                    scene_line += f"\n    SPOKEN TEXT: \"{scene_transcript}\""
            scene_info_parts.append(scene_line)

        scene_info = "\n".join(scene_info_parts)
        total_duration = scenes[-1].end_time if scenes else 0

        # Build transcript section
        transcript_section = ""
        if transcript and transcript.has_speech:
            transcript_section = f"""
## EXACT TRANSCRIPT (USE THIS - DO NOT MAKE UP TEXT!)
Language: {transcript.language}
Full transcript: "{transcript.full_text}"

**CRITICAL: The dialogue/voiceover above is EXACT. Use these EXACT words in the prompts!**
"""

        return f"""## TASK
Analyze this product video for "{product_name}" and generate VEO 3.1 OPTIMIZED prompts for each scene.

## VIDEO INFO
- Product: {product_name}
- Duration: {total_duration:.1f} seconds
- Scenes detected:
{scene_info}
{transcript_section}
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
[Audio: A person says, "EXACT transcript text here." (no subtitles)]
```

## VEO 3.1 SPECIFIC FORMATTING:
- Dialogue: A person says, "exact words here." (no subtitles) - USE EXACT TRANSCRIPT!
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
- **DIALOGUE MUST BE EXACT**: Use the transcript text word-for-word, do NOT paraphrase!

## OUTPUT FORMAT
Return a VideoPromptResult JSON with target_model="veo-3.1" and optimized prompts for each scene.
Include full_video_prompt with timestamp-based prompt for seamless generation."""

    def _unwrap_response(self, result_dict: dict, product_name: str, scenes: List[Scene], target_model: TargetModel = TargetModel.VEO_3) -> dict:
        """
        Handle nested response structure and normalize field names from Gemini API.
        Sometimes the API wraps the result or uses different field names.
        """
        # Check if wrapped in class name
        if len(result_dict) == 1:
            key = list(result_dict.keys())[0]
            if isinstance(result_dict[key], dict) and key[0].isupper():
                result_dict = result_dict[key]

        # Add missing top-level fields with defaults
        if "product_name" not in result_dict:
            result_dict["product_name"] = product_name
        if "target_model" not in result_dict:
            result_dict["target_model"] = target_model.value  # Use actual target model
        if "total_duration" not in result_dict:
            result_dict["total_duration"] = scenes[-1].end_time if scenes else 0.0
        if "visual_style" not in result_dict:
            result_dict["visual_style"] = "cinematic commercial style"
        if "color_palette" not in result_dict:
            result_dict["color_palette"] = "warm, natural tones"
        if "film_reference" not in result_dict:
            result_dict["film_reference"] = "modern digital commercial"

        # CRITICAL: Ensure scene_prompts exists with default fallback
        if "scene_prompts" not in result_dict or not result_dict["scene_prompts"]:
            # Create default scene prompts from detected scenes
            result_dict["scene_prompts"] = []
            for i, scene in enumerate(scenes):
                default_prompt = {
                    "scene_index": i,
                    "start_time": scene.start_time,
                    "end_time": scene.end_time,
                    "duration": scene.duration,
                    "prompt": f"A commercial scene showcasing {product_name} with professional lighting and composition.",
                    "camera_shot": "medium shot",
                    "camera_movement": "static",
                    "subject_action": "product display",
                    "lighting": "soft natural light",
                    "mood": "professional",
                    "has_audio": False,
                    "audio_description": None
                }
                result_dict["scene_prompts"].append(default_prompt)

        # Normalize scene_prompts
        normalized_scenes = []
        for i, scene in enumerate(result_dict["scene_prompts"]):
            normalized = self._normalize_scene(scene, i, scenes)
            normalized_scenes.append(normalized)
        result_dict["scene_prompts"] = normalized_scenes

        # Update scene_count after normalization
        result_dict["scene_count"] = len(result_dict["scene_prompts"])

        # CRITICAL: Ensure full_video_prompt exists (can be None but must be present)
        if "full_video_prompt" not in result_dict:
            result_dict["full_video_prompt"] = None

        return result_dict

    def _normalize_scene(self, scene: dict, index: int, scenes: List[Scene]) -> dict:
        """Normalize a single scene prompt to match expected schema."""
        # Get original scene info if available
        orig_scene = scenes[index] if index < len(scenes) else None

        # Map alternative field names
        normalized = {
            "scene_index": scene.get("scene_index", scene.get("scene_number", index + 1)) - 1 if "scene_number" in scene else scene.get("scene_index", index),
            "start_time": self._parse_time(scene.get("start_time", orig_scene.start_time if orig_scene else 0.0)),
            "end_time": self._parse_time(scene.get("end_time", orig_scene.end_time if orig_scene else 0.0)),
            "duration": scene.get("duration", orig_scene.duration if orig_scene else 0.0),
            "prompt": scene.get("prompt", scene.get("video_prompt", scene.get("scene_prompt", ""))),
            "camera_shot": scene.get("camera_shot", scene.get("shot_type", "medium shot")),
            "camera_movement": scene.get("camera_movement", scene.get("movement", "static")),
            "subject_action": scene.get("subject_action", scene.get("action", "product display")),
            "lighting": scene.get("lighting", scene.get("light", "soft natural light")),
            "mood": scene.get("mood", scene.get("atmosphere", "professional")),
            "has_audio": scene.get("has_audio", bool(scene.get("audio_description") or scene.get("dialogue"))),
            "audio_description": scene.get("audio_description", scene.get("dialogue", None)),
        }

        # Calculate duration if missing
        if normalized["duration"] == 0.0 and normalized["end_time"] > normalized["start_time"]:
            normalized["duration"] = normalized["end_time"] - normalized["start_time"]

        return normalized

    def _parse_time(self, time_value) -> float:
        """Parse time value from various formats to float seconds."""
        if isinstance(time_value, (int, float)):
            return float(time_value)
        if isinstance(time_value, str):
            # Handle MM:SS or HH:MM:SS format
            parts = time_value.split(":")
            if len(parts) == 2:
                return float(parts[0]) * 60 + float(parts[1])
            elif len(parts) == 3:
                return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
            # Try direct float conversion
            try:
                return float(time_value)
            except ValueError:
                return 0.0
        return 0.0

    def _format_time(self, seconds: float) -> str:
        """Format seconds as MM:SS"""
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins:02d}:{secs:02d}"


# Singleton instance
gemini_analyzer = GeminiAnalyzer()
