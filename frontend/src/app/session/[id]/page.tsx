"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter, useParams } from "next/navigation";
import Card from "@/components/ui/Card";
import ProgressBar from "@/components/ui/ProgressBar";
import Button from "@/components/ui/Button";
import { getApiBase, getVideoUrl, downloadVideo } from "@/lib/api";

interface SessionStatus {
  session_id: string;
  status: string;
  progress: number;
  current_step: string;
  variants_completed: number;
  variants_total: number;
  error_message?: string;
}

interface Clip {
  clip_index: number;
  video_url: string | null;
  status: string;
  duration: number;
}

interface Variant {
  variant_index: number;
  clips: Clip[];
  status: string;
}

interface Session {
  session_id: string;
  product_name: string;
  tiktok_url: string;
  status: string;
  provider: string;
  model: string;
  variants: Variant[];
  total_cost: number;
}

// Custom Video Player Component
function VideoPlayer({ src, duration, onDownload }: { src: string; duration: number; onDownload: () => void }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [showControls, setShowControls] = useState(true);

  const togglePlay = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  };

  const handleSeek = (e: React.MouseEvent<HTMLDivElement>) => {
    if (videoRef.current) {
      const rect = e.currentTarget.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const percentage = x / rect.width;
      videoRef.current.currentTime = percentage * duration;
    }
  };

  const formatTime = (time: number) => {
    const mins = Math.floor(time / 60);
    const secs = Math.floor(time % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div
      className="relative bg-black rounded-2xl overflow-hidden group"
      onMouseEnter={() => setShowControls(true)}
      onMouseLeave={() => !isPlaying && setShowControls(true)}
    >
      {/* Video */}
      <video
        ref={videoRef}
        src={src}
        className="w-full aspect-[9/16] object-contain bg-black"
        playsInline
        onTimeUpdate={handleTimeUpdate}
        onEnded={() => setIsPlaying(false)}
        onClick={togglePlay}
      />

      {/* Custom Controls Overlay */}
      <div className={`absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent transition-opacity ${showControls || !isPlaying ? 'opacity-100' : 'opacity-0'}`}>
        {/* Center Play Button */}
        {!isPlaying && (
          <button
            onClick={togglePlay}
            className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-16 h-16 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center hover:bg-white/30 transition-colors"
          >
            <svg className="w-8 h-8 text-white ml-1" fill="currentColor" viewBox="0 0 24 24">
              <path d="M8 5v14l11-7z" />
            </svg>
          </button>
        )}

        {/* Bottom Controls */}
        <div className="absolute bottom-0 left-0 right-0 p-3">
          {/* Progress Bar */}
          <div
            className="h-1 bg-white/30 rounded-full mb-3 cursor-pointer"
            onClick={handleSeek}
          >
            <div
              className="h-full bg-accent-cyan rounded-full transition-all"
              style={{ width: `${(currentTime / duration) * 100}%` }}
            />
          </div>

          {/* Controls Row */}
          <div className="flex items-center justify-between">
            {/* Left: Play/Pause + Time */}
            <div className="flex items-center gap-3 flex-1">
              <button onClick={togglePlay} className="text-white hover:text-accent-cyan transition-colors">
                {isPlaying ? (
                  <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
                  </svg>
                ) : (
                  <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M8 5v14l11-7z" />
                  </svg>
                )}
              </button>
              <span className="text-white/80 text-sm font-medium">
                {formatTime(currentTime)} / {formatTime(duration)}
              </span>
            </div>

            {/* Download Button */}
            <button
              onClick={(e) => { e.stopPropagation(); onDownload(); }}
              className="text-white hover:text-accent-cyan transition-colors"
              title="Download"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function SessionPage() {
  const router = useRouter();
  const params = useParams();
  const sessionId = params.id as string;

  const [session, setSession] = useState<Session | null>(null);
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isDownloading, setIsDownloading] = useState(false);

  // Poll for status updates
  useEffect(() => {
    let mounted = true;

    const fetchStatus = async () => {
      try {
        const sessionRes = await fetch(`${getApiBase()}/sessions/${sessionId}`);
        if (!mounted) return;
        if (sessionRes.ok) {
          setSession(await sessionRes.json());
        }

        const statusRes = await fetch(`${getApiBase()}/sessions/${sessionId}/status`);
        if (!mounted) return;
        if (statusRes.ok) {
          setStatus(await statusRes.json());
        }
      } catch {
        // Backend not running - ignore silently
      } finally {
        if (mounted) setIsLoading(false);
      }
    };

    fetchStatus();

    // Poll every 3 seconds if not completed
    const interval = setInterval(() => {
      if (status?.status !== "completed" && status?.status !== "failed") {
        fetchStatus();
      }
    }, 3000);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, [sessionId, status?.status]);

  const getStatusColor = (s: string) => {
    switch (s) {
      case "completed":
        return "text-accent-green";
      case "failed":
        return "text-red-400";
      case "generating":
        return "text-accent-cyan";
      default:
        return "text-yellow-400";
    }
  };

  const getStatusIcon = (s: string) => {
    switch (s) {
      case "completed":
        return "✓";
      case "failed":
        return "✕";
      case "generating":
        return "⚡";
      default:
        return "⏳";
    }
  };

  const handleDownloadAll = async () => {
    setIsDownloading(true);
    for (const variant of session?.variants || []) {
      for (const clip of variant.clips) {
        if (clip.video_url) {
          const filename = `${session?.product_name || 'video'}_v${variant.variant_index + 1}_clip${clip.clip_index + 1}.mp4`;
          await downloadVideo(clip.video_url, filename);
          // Small delay between downloads
          await new Promise(resolve => setTimeout(resolve, 500));
        }
      }
    }
    setIsDownloading(false);
  };

  const handleDownloadClip = async (clip: Clip, variantIndex: number) => {
    if (clip.video_url) {
      const filename = `${session?.product_name || 'video'}_v${variantIndex + 1}_clip${clip.clip_index + 1}.mp4`;
      await downloadVideo(clip.video_url, filename);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="px-4 pt-6 pb-8">
      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        <button
          onClick={() => router.push("/")}
          className="w-10 h-10 rounded-full bg-dark-card flex items-center justify-center"
        >
          <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <div className="flex-1">
          <h1 className="text-xl font-bold truncate">{session?.product_name || "Session"}</h1>
          <p className="text-gray-400 text-sm">{session?.provider} • {session?.model}</p>
        </div>
      </div>

      {/* Progress Card */}
      <Card gradient className="mb-6">
        <div className="flex items-center gap-3 mb-4">
          <span className={`text-2xl ${getStatusColor(status?.status || "pending")}`}>
            {getStatusIcon(status?.status || "pending")}
          </span>
          <div>
            <h3 className="font-semibold text-white capitalize">{status?.status || "Pending"}</h3>
            <p className="text-white/70 text-sm">{status?.current_step || "Waiting to start..."}</p>
          </div>
        </div>

        <ProgressBar progress={status?.progress || 0} showPercentage />

        {status?.variants_total && status.variants_total > 0 && (
          <p className="text-white/60 text-sm mt-3">
            Variant {status.variants_completed}/{status.variants_total}
          </p>
        )}

        {status?.error_message && (
          <p className="text-red-400 text-sm mt-3">{status.error_message}</p>
        )}
      </Card>

      {/* Cost */}
      <Card className="mb-6">
        <div className="flex items-center justify-between">
          <span className="text-gray-400">Total Cost</span>
          <span className="text-xl font-bold text-accent-cyan">
            ${(session?.total_cost || 0).toFixed(2)}
          </span>
        </div>
      </Card>

      {/* Generated Videos */}
      {session?.variants && session.variants.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-4">Generated Videos</h2>
          <div className="space-y-6">
            {session.variants.map((variant) => (
              <Card key={variant.variant_index} className="p-4">
                <h3 className="font-medium mb-4 text-accent-cyan">Variant {variant.variant_index + 1}</h3>
                <div className="space-y-4">
                  {variant.clips.map((clip) => (
                    <div key={clip.clip_index}>
                      {clip.video_url ? (
                        <VideoPlayer
                          src={getVideoUrl(clip.video_url)}
                          duration={clip.duration}
                          onDownload={() => handleDownloadClip(clip, variant.variant_index)}
                        />
                      ) : (
                        <div className="aspect-[9/16] bg-dark-elevated rounded-2xl flex items-center justify-center">
                          {clip.status === "completed" ? (
                            <span className="text-accent-green text-2xl">✓</span>
                          ) : clip.status === "failed" ? (
                            <span className="text-red-400 text-2xl">✕</span>
                          ) : (
                            <div className="animate-pulse w-8 h-8 rounded-full bg-dark-border" />
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      {status?.status === "completed" && (
        <div className="mt-6 space-y-3">
          <Button
            fullWidth
            variant="primary"
            onClick={handleDownloadAll}
            disabled={isDownloading}
          >
            {isDownloading ? (
              <span className="flex items-center justify-center gap-2 w-full">
                <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Downloading...
              </span>
            ) : (
              <span className="flex items-center justify-center gap-2 w-full">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                Download All
              </span>
            )}
          </Button>
          <Button fullWidth variant="secondary" onClick={() => router.push("/library")}>
            Go to Library
          </Button>
        </div>
      )}

      {status?.status === "failed" && (
        <div className="mt-6">
          <Button fullWidth variant="secondary" onClick={() => router.push("/new")}>
            Try Again
          </Button>
        </div>
      )}
    </div>
  );
}
