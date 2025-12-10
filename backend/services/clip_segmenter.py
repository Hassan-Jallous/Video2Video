"""
Clip Segmenter - Optimale Clip-Segmentierung basierend auf Model-Limits

Berechnet wie ein Video in Clips aufgeteilt werden soll, um:
1. Alle Model-Limits einzuhalten (z.B. defapi Sora 2 max 15s)
2. Kosten zu optimieren (keine unnötigen Clips)
3. Natürliche Szenen-Grenzen zu respektieren (wenn möglich)
"""
from dataclasses import dataclass
from typing import List, Literal, Optional


@dataclass
class ClipSegment:
    """Ein Clip-Segment mit Timing und Pacing-Info"""
    clip_index: int
    start_time: float
    end_time: float
    duration: float
    target_duration: float  # Ziel-Dauer für AI-Generation
    pacing: Literal["normal", "slightly_faster", "slightly_slower"]
    pacing_note: str  # Hinweis für Gemini-Prompt


class ClipSegmenter:
    """Berechnet optimale Clip-Segmentierung basierend auf Model-Limits"""

    # Model-spezifische Limits
    MODEL_LIMITS = {
        # defapi.org models
        "defapi-sora-2": {"max_duration": 15.0, "min_duration": 5.0, "default_duration": 10.0},
        "defapi-veo-3.1": {"max_duration": 8.0, "min_duration": 3.0, "default_duration": 8.0},
        # kie.ai models
        "veo-3.1-fast": {"max_duration": 8.0, "min_duration": 3.0, "default_duration": 8.0},
        "veo-3.1-quality": {"max_duration": 8.0, "min_duration": 3.0, "default_duration": 8.0},
        "sora-2": {"max_duration": 8.0, "min_duration": 3.0, "default_duration": 8.0},
    }

    # Puffer am Anfang/Ende für AI-Übergang (Person braucht Zeit zu starten)
    BUFFER_SECONDS = 0.5

    # Max Sekunden die durch schnelleres Pacing kompensiert werden können
    PACING_THRESHOLD = 3.0

    def get_model_limits(self, model: str) -> dict:
        """Hole Model-Limits, fallback zu 8s wenn unbekannt"""
        return self.MODEL_LIMITS.get(model, {"max_duration": 8.0, "min_duration": 3.0, "default_duration": 8.0})

    def calculate_segments(
        self,
        video_duration: float,
        model: str,
        scene_boundaries: Optional[List[float]] = None
    ) -> List[ClipSegment]:
        """
        Berechne optimale Clip-Segmentierung.

        Args:
            video_duration: Gesamtlänge des Videos in Sekunden
            model: Model-Name (z.B. "defapi-sora-2")
            scene_boundaries: Optional - Liste von Szenen-Grenzen in Sekunden

        Returns:
            Liste von ClipSegment mit Timing und Pacing-Info
        """
        limits = self.get_model_limits(model)
        max_dur = limits["max_duration"]

        # Berechne minimale Anzahl an Clips
        min_clips = max(1, int(video_duration / max_dur))
        remainder = video_duration - (min_clips * max_dur)

        # Entscheide: N Clips mit schnellerem Pacing oder N+1 Clips?
        if remainder <= 0:
            # Video passt genau in N Clips
            num_clips = min_clips
            pacing = "normal"
            pacing_note = ""
        elif remainder <= self.PACING_THRESHOLD:
            # Kleine Überschreitung → kompensiere durch schnelleres Pacing
            num_clips = min_clips
            pacing = "slightly_faster"
            compression_ratio = video_duration / (num_clips * max_dur)
            pacing_note = f"PACING: Speak {int((compression_ratio - 1) * 100)}% faster to fit {video_duration:.1f}s content into {num_clips * max_dur:.1f}s. Keep natural rhythm but slightly quicker pace."
        else:
            # Große Überschreitung → brauchen einen zusätzlichen Clip
            num_clips = min_clips + 1
            pacing = "normal"
            pacing_note = ""

        # Berechne Clip-Längen
        # Versuche gleichmäßige Aufteilung
        clip_duration = video_duration / num_clips

        # Wenn wir Szenen-Grenzen haben, versuche Clips an Szenen auszurichten
        if scene_boundaries and len(scene_boundaries) > 0:
            segments = self._align_to_scenes(
                video_duration, num_clips, max_dur, scene_boundaries, pacing, pacing_note
            )
        else:
            # Gleichmäßige Aufteilung
            segments = self._uniform_segments(
                video_duration, num_clips, max_dur, pacing, pacing_note
            )

        return segments

    def _uniform_segments(
        self,
        video_duration: float,
        num_clips: int,
        max_dur: float,
        pacing: str,
        pacing_note: str
    ) -> List[ClipSegment]:
        """Erstelle gleichmäßig verteilte Clips"""
        clip_duration = video_duration / num_clips
        segments = []

        for i in range(num_clips):
            start = i * clip_duration
            end = (i + 1) * clip_duration

            segments.append(ClipSegment(
                clip_index=i,
                start_time=start,
                end_time=end,
                duration=end - start,
                target_duration=min(clip_duration, max_dur),
                pacing=pacing,
                pacing_note=pacing_note if i == 0 else ""  # Pacing-Note nur beim ersten Clip
            ))

        return segments

    def _align_to_scenes(
        self,
        video_duration: float,
        num_clips: int,
        max_dur: float,
        scene_boundaries: List[float],
        pacing: str,
        pacing_note: str
    ) -> List[ClipSegment]:
        """
        Versuche Clips an Szenen-Grenzen auszurichten.
        Falls nicht möglich, fallback zu gleichmäßiger Aufteilung.
        """
        # Füge Start und Ende hinzu
        boundaries = [0.0] + sorted(scene_boundaries) + [video_duration]

        # Wenn weniger Szenen als Clips, nutze gleichmäßige Aufteilung
        if len(boundaries) - 1 < num_clips:
            return self._uniform_segments(video_duration, num_clips, max_dur, pacing, pacing_note)

        # Versuche optimale Grenzen zu finden
        # Einfache Strategie: Teile Szenen möglichst gleichmäßig auf Clips auf
        target_clip_duration = video_duration / num_clips
        segments = []
        current_start = 0.0
        clips_created = 0

        for i, boundary in enumerate(boundaries[1:], 1):
            elapsed = boundary - current_start

            # Wenn wir genug Material für einen Clip haben ODER es der letzte Clip ist
            if elapsed >= target_clip_duration * 0.8 or clips_created == num_clips - 1:
                # Erstelle Clip bis zu dieser Grenze
                end = boundary if clips_created < num_clips - 1 else video_duration

                segments.append(ClipSegment(
                    clip_index=clips_created,
                    start_time=current_start,
                    end_time=end,
                    duration=end - current_start,
                    target_duration=min(end - current_start, max_dur),
                    pacing=pacing,
                    pacing_note=pacing_note if clips_created == 0 else ""
                ))

                current_start = end
                clips_created += 1

                if clips_created >= num_clips:
                    break

        # Falls wir nicht genug Clips erstellt haben, fülle auf
        while len(segments) < num_clips:
            # Teile den letzten Clip
            last = segments[-1]
            mid = (last.start_time + last.end_time) / 2

            segments[-1] = ClipSegment(
                clip_index=last.clip_index,
                start_time=last.start_time,
                end_time=mid,
                duration=mid - last.start_time,
                target_duration=min(mid - last.start_time, max_dur),
                pacing=pacing,
                pacing_note=last.pacing_note
            )

            segments.append(ClipSegment(
                clip_index=len(segments),
                start_time=mid,
                end_time=last.end_time,
                duration=last.end_time - mid,
                target_duration=min(last.end_time - mid, max_dur),
                pacing=pacing,
                pacing_note=""
            ))

        return segments

    def get_duration_prefix(self, model: str, target_duration: float) -> str:
        """
        Generiere Duration-Prefix für API-Request.
        Für defapi Sora 2: "(15s,hd)" oder "(10s,hd)"
        """
        if model == "defapi-sora-2":
            # defapi Sora 2 unterstützt 10s (default) oder 15s mit Prefix
            if target_duration > 10:
                return "(15s,hd) "
            else:
                return "(10s,hd) "
        return ""


# Singleton instance
clip_segmenter = ClipSegmenter()
