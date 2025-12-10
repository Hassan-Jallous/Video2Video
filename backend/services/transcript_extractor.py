"""
Transcript Extractor - Audio Analysis with Timestamps

Uses Gemini's audio understanding to extract accurate transcripts
with timestamps from video files. This provides much more accurate
text than general video analysis.
"""
import json
import time
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field

import google.generativeai as genai
import redis

from config import settings
from services.pipeline_logger import PipelineLogger


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


class TranscriptSegment(BaseModel):
    """A single segment of transcribed speech"""
    start_time: float = Field(description="Start time in seconds")
    end_time: float = Field(description="End time in seconds")
    text: str = Field(description="The spoken text in this segment")
    speaker: Optional[str] = Field(default=None, description="Speaker identifier if multiple speakers")
    confidence: float = Field(default=1.0, description="Confidence score 0-1")


class TranscriptResult(BaseModel):
    """Complete transcript with timestamps"""
    language: str = Field(description="Detected language of the audio")
    total_duration: float = Field(description="Total audio duration in seconds")
    segments: List[TranscriptSegment] = Field(description="Transcript segments with timestamps")
    full_text: str = Field(description="Complete transcript as continuous text")
    has_speech: bool = Field(description="Whether the video contains speech")
    has_music: bool = Field(description="Whether the video contains music")
    background_sounds: Optional[str] = Field(default=None, description="Description of background sounds")


class TranscriptExtractor:
    """
    Extracts accurate transcripts with timestamps from video files.

    Uses Gemini's audio understanding capabilities for high-accuracy
    transcription with precise timing information.
    """

    def __init__(self):
        genai.configure(api_key=get_gemini_api_key())
        self.logger = PipelineLogger()

        # Use Gemini 2.0 Flash for fast audio processing
        self.model = genai.GenerativeModel(
            "gemini-2.0-flash-exp",
            generation_config={
                "temperature": 0.1,  # Low temperature for accurate transcription
                "response_mime_type": "application/json",
            }
        )

    def extract_transcript(self, video_path: str, session_id: Optional[str] = None) -> TranscriptResult:
        """
        Extract transcript with timestamps from a video file.

        Args:
            video_path: Path to the video file
            session_id: Optional session ID for logging

        Returns:
            TranscriptResult with timestamped segments
        """
        if session_id:
            self.logger.set_session(session_id)

        self.logger.info("TRANSCRIPT", f"Starting transcript extraction: {video_path}", {
            "video_path": video_path,
            "video_exists": Path(video_path).exists(),
        })

        # Check video file
        video_path_obj = Path(video_path)
        if not video_path_obj.exists():
            self.logger.error("TRANSCRIPT", f"Video file not found: {video_path}")
            return self._empty_transcript()

        video_size = video_path_obj.stat().st_size
        self.logger.info("TRANSCRIPT", f"Video file: {video_size} bytes", {
            "video_size_bytes": video_size,
            "video_size_mb": round(video_size / (1024 * 1024), 2),
        })

        # Upload video to Gemini
        self.logger.info("TRANSCRIPT", "Uploading video to Gemini API...")
        upload_start = time.time()

        try:
            video_file = genai.upload_file(video_path)
            upload_time = time.time() - upload_start

            self.logger.success("TRANSCRIPT", f"Video uploaded in {upload_time:.1f}s", {
                "upload_time_sec": upload_time,
                "file_name": video_file.name,
                "file_state": video_file.state.name,
            })
        except Exception as e:
            self.logger.error("TRANSCRIPT", "Failed to upload video to Gemini", error=e)
            return self._empty_transcript()

        # Wait for processing
        self.logger.info("TRANSCRIPT", f"Waiting for Gemini to process video (state: {video_file.state.name})...")
        wait_start = time.time()
        poll_count = 0

        while video_file.state.name == "PROCESSING":
            poll_count += 1
            time.sleep(2)
            video_file = genai.get_file(video_file.name)
            self.logger.debug("TRANSCRIPT", f"Poll #{poll_count}: state={video_file.state.name}")

        wait_time = time.time() - wait_start
        self.logger.info("TRANSCRIPT", f"Processing complete: {video_file.state.name} ({wait_time:.1f}s)", {
            "final_state": video_file.state.name,
            "wait_time_sec": wait_time,
            "poll_count": poll_count,
        })

        if video_file.state.name == "FAILED":
            self.logger.error("TRANSCRIPT", f"Gemini processing FAILED", data={
                "state": video_file.state.name,
            })
            return self._empty_transcript()

        # Build transcript extraction prompt
        prompt = self._build_transcript_prompt()
        self.logger.info("TRANSCRIPT", f"Sending transcription request to Gemini...", {
            "prompt_length": len(prompt),
        })

        try:
            # Note: Don't use response_schema with Pydantic schemas - causes "$defs" error
            generate_start = time.time()
            response = self.model.generate_content(
                contents=[
                    {"role": "user", "parts": [video_file]},
                    {"role": "user", "parts": [prompt]}
                ],
                generation_config={
                    "temperature": 0.1,
                    "response_mime_type": "application/json",
                }
            )
            generate_time = time.time() - generate_start

            self.logger.success("TRANSCRIPT", f"Gemini response received in {generate_time:.1f}s", {
                "generate_time_sec": generate_time,
                "response_length": len(response.text) if response.text else 0,
            })

            # Parse JSON response
            self.logger.info("TRANSCRIPT", "Parsing JSON response...")

            try:
                result_dict = json.loads(response.text)
                self.logger.info("TRANSCRIPT", "JSON parsed successfully", {
                    "keys": list(result_dict.keys()),
                })
            except json.JSONDecodeError as e:
                self.logger.error("TRANSCRIPT", "Failed to parse JSON response", error=e, data={
                    "response_preview": response.text[:500] if response.text else None,
                })
                return self._empty_transcript()

            # Normalize result
            result_dict = self._normalize_result(result_dict)

            self.logger.success("TRANSCRIPT", "Transcript extraction complete!", {
                "language": result_dict.get("language"),
                "total_duration": result_dict.get("total_duration"),
                "segment_count": len(result_dict.get("segments", [])),
                "has_speech": result_dict.get("has_speech"),
                "has_music": result_dict.get("has_music"),
                "full_text_preview": result_dict.get("full_text", "")[:200],
            })

            return TranscriptResult(**result_dict)

        except Exception as e:
            self.logger.error("TRANSCRIPT", "Transcript extraction FAILED", error=e)
            return self._empty_transcript()

    def _empty_transcript(self) -> TranscriptResult:
        """Return empty transcript on failure"""
        self.logger.warning("TRANSCRIPT", "Returning empty transcript due to error")
        return TranscriptResult(
            language="unknown",
            total_duration=0.0,
            segments=[],
            full_text="",
            has_speech=False,
            has_music=False,
            background_sounds=None
        )

    def _build_transcript_prompt(self) -> str:
        """Build the prompt for transcript extraction."""
        return """## TASK: ACCURATE AUDIO TRANSCRIPTION WITH TIMESTAMPS

You are a professional transcriptionist. Your job is to extract the EXACT spoken words from this video with precise timestamps.

## CRITICAL RULES:

1. **ACCURACY IS PARAMOUNT**
   - Transcribe EXACTLY what is said, word for word
   - Do NOT paraphrase or summarize
   - Do NOT add words that weren't spoken
   - Do NOT skip any spoken content
   - Include filler words (um, uh, like) if present

2. **TIMESTAMPS MUST BE PRECISE**
   - Provide start_time and end_time for each segment
   - Timestamps in SECONDS (e.g., 2.5 for 2.5 seconds)
   - Break into segments at natural pauses or sentence boundaries
   - Each segment should be 1-10 seconds typically

3. **LANGUAGE DETECTION**
   - Identify the primary language spoken
   - If multiple languages, note this in the segments

4. **AUDIO ANALYSIS**
   - Note if there is speech (has_speech: true/false)
   - Note if there is music (has_music: true/false)
   - Describe any significant background sounds

## OUTPUT FORMAT

Return a TranscriptResult JSON with:
- language: The detected language (e.g., "German", "English")
- total_duration: Video length in seconds
- segments: Array of TranscriptSegment objects with exact timestamps
- full_text: Complete transcript as one continuous string
- has_speech: Whether video contains speech
- has_music: Whether video contains music
- background_sounds: Description of background sounds if notable

## EXAMPLE OUTPUT:

```json
{
  "language": "German",
  "total_duration": 15.5,
  "segments": [
    {
      "start_time": 0.0,
      "end_time": 3.2,
      "text": "Wird Kollagen im Kaffee zerstort?",
      "speaker": null,
      "confidence": 0.95
    },
    {
      "start_time": 3.5,
      "end_time": 8.1,
      "text": "Diese Frage hore ich sehr oft, und die Antwort ist nein.",
      "speaker": null,
      "confidence": 0.92
    }
  ],
  "full_text": "Wird Kollagen im Kaffee zerstort? Diese Frage hore ich sehr oft, und die Antwort ist nein.",
  "has_speech": true,
  "has_music": false,
  "background_sounds": "Soft ambient room tone"
}
```

Now transcribe the video audio with maximum accuracy."""

    def _normalize_result(self, result_dict: dict) -> dict:
        """Normalize the response structure."""
        self.logger.info("TRANSCRIPT", "Normalizing result structure...", {
            "input_keys": list(result_dict.keys()),
        })

        # Handle wrapped responses
        if len(result_dict) == 1:
            key = list(result_dict.keys())[0]
            if isinstance(result_dict[key], dict) and key[0].isupper():
                self.logger.info("TRANSCRIPT", f"Unwrapping nested response from key: {key}")
                result_dict = result_dict[key]

        # Ensure required fields exist
        if "language" not in result_dict:
            self.logger.warning("TRANSCRIPT", "Missing 'language' field, defaulting to 'unknown'")
            result_dict["language"] = "unknown"
        if "total_duration" not in result_dict:
            self.logger.warning("TRANSCRIPT", "Missing 'total_duration' field, defaulting to 0.0")
            result_dict["total_duration"] = 0.0
        if "segments" not in result_dict:
            self.logger.warning("TRANSCRIPT", "Missing 'segments' field, defaulting to []")
            result_dict["segments"] = []
        if "full_text" not in result_dict:
            # Build full_text from segments
            result_dict["full_text"] = " ".join(
                seg.get("text", "") for seg in result_dict.get("segments", [])
            )
            self.logger.info("TRANSCRIPT", "Built 'full_text' from segments")
        if "has_speech" not in result_dict:
            result_dict["has_speech"] = len(result_dict.get("segments", [])) > 0
        if "has_music" not in result_dict:
            result_dict["has_music"] = False

        # Normalize segments
        normalized_segments = []
        for i, seg in enumerate(result_dict.get("segments", [])):
            normalized_seg = {
                "start_time": float(seg.get("start_time", 0)),
                "end_time": float(seg.get("end_time", 0)),
                "text": seg.get("text", ""),
                "speaker": seg.get("speaker"),
                "confidence": float(seg.get("confidence", 1.0))
            }
            normalized_segments.append(normalized_seg)

        result_dict["segments"] = normalized_segments

        self.logger.success("TRANSCRIPT", "Normalization complete", {
            "segment_count": len(normalized_segments),
            "full_text_length": len(result_dict.get("full_text", "")),
        })

        return result_dict

    def get_transcript_for_timerange(
        self,
        transcript: TranscriptResult,
        start_time: float,
        end_time: float
    ) -> str:
        """
        Get transcript text for a specific time range.

        Args:
            transcript: The full transcript
            start_time: Start time in seconds
            end_time: End time in seconds

        Returns:
            Transcript text that falls within the time range
        """
        relevant_segments = []
        for seg in transcript.segments:
            # Include segment if it overlaps with the time range
            if seg.end_time > start_time and seg.start_time < end_time:
                relevant_segments.append(seg.text)

        result = " ".join(relevant_segments)

        self.logger.debug("TRANSCRIPT", f"Time range [{start_time:.1f}-{end_time:.1f}]: {len(relevant_segments)} segments", {
            "start_time": start_time,
            "end_time": end_time,
            "segment_count": len(relevant_segments),
            "text_preview": result[:100] if result else "(empty)",
        })

        return result


# Singleton instance
transcript_extractor = TranscriptExtractor()
