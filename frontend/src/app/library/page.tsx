"use client";

import { useEffect, useState, useRef } from "react";
import Card from "@/components/ui/Card";
import { getApiBase, getVideoUrl, downloadVideo } from "@/lib/api";

interface VideoItem {
  session_id: string;
  variant_index: number;
  clip_index: number;
  video_url: string;
  product_name: string;
  created_at: string;
  duration: number;
  provider: string;
  model: string;
}

// Video Thumbnail with hover play
function VideoThumbnail({ video, onClick }: { video: VideoItem; onClick: () => void }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isHovered, setIsHovered] = useState(false);

  useEffect(() => {
    if (videoRef.current) {
      if (isHovered) {
        videoRef.current.play().catch(() => {});
      } else {
        videoRef.current.pause();
        videoRef.current.currentTime = 0;
      }
    }
  }, [isHovered]);

  return (
    <div
      className="aspect-[9/16] bg-dark-elevated relative cursor-pointer group"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={onClick}
    >
      <video
        ref={videoRef}
        src={getVideoUrl(video.video_url)}
        className="w-full h-full object-contain bg-black"
        muted
        playsInline
        loop
        preload="metadata"
      />

      {/* Play Icon Overlay */}
      {!isHovered && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/20">
          <div className="w-12 h-12 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center">
            <svg className="w-6 h-6 text-white ml-0.5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M8 5v14l11-7z" />
            </svg>
          </div>
        </div>
      )}

      {/* Info Badges */}
      <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between">
        <span className="bg-black/60 backdrop-blur-sm px-2 py-0.5 rounded text-xs font-medium">
          {video.duration.toFixed(1)}s
        </span>
        <span className="bg-accent-cyan/20 text-accent-cyan px-2 py-0.5 rounded text-xs font-medium">
          V{video.variant_index + 1}
        </span>
      </div>
    </div>
  );
}

// Full Video Player Modal
function VideoModal({ video, onClose }: { video: VideoItem; onClose: () => void }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(true);
  const [currentTime, setCurrentTime] = useState(0);
  const [isDownloading, setIsDownloading] = useState(false);

  useEffect(() => {
    // Auto-play on open
    videoRef.current?.play().catch(() => {});
  }, []);

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

  const handleSeek = (e: React.MouseEvent<HTMLDivElement>) => {
    if (videoRef.current) {
      const rect = e.currentTarget.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const percentage = x / rect.width;
      videoRef.current.currentTime = percentage * video.duration;
    }
  };

  const formatTime = (time: number) => {
    const mins = Math.floor(time / 60);
    const secs = Math.floor(time % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const handleDownload = async () => {
    setIsDownloading(true);
    const filename = `${video.product_name}_v${video.variant_index + 1}_clip${video.clip_index + 1}.mp4`;
    await downloadVideo(video.video_url, filename);
    setIsDownloading(false);
  };

  return (
    <div
      className="fixed inset-0 bg-black/95 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div className="w-full max-w-md" onClick={(e) => e.stopPropagation()}>
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 w-10 h-10 bg-white/10 rounded-full flex items-center justify-center hover:bg-white/20 transition-colors"
        >
          <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        {/* Video Player */}
        <div className="relative bg-black rounded-2xl overflow-hidden">
          <video
            ref={videoRef}
            src={getVideoUrl(video.video_url)}
            className="w-full aspect-[9/16] object-contain"
            playsInline
            onTimeUpdate={() => setCurrentTime(videoRef.current?.currentTime || 0)}
            onEnded={() => setIsPlaying(false)}
            onClick={togglePlay}
          />

          {/* Center Play Button (when paused) */}
          {!isPlaying && (
            <button
              onClick={togglePlay}
              className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-20 h-20 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center hover:bg-white/30 transition-colors"
            >
              <svg className="w-10 h-10 text-white ml-1" fill="currentColor" viewBox="0 0 24 24">
                <path d="M8 5v14l11-7z" />
              </svg>
            </button>
          )}

          {/* Bottom Controls */}
          <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-black/80 to-transparent">
            {/* Progress Bar */}
            <div
              className="h-1 bg-white/30 rounded-full mb-3 cursor-pointer"
              onClick={handleSeek}
            >
              <div
                className="h-full bg-accent-cyan rounded-full transition-all"
                style={{ width: `${(currentTime / video.duration) * 100}%` }}
              />
            </div>

            {/* Controls Row */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <button onClick={togglePlay} className="text-white hover:text-accent-cyan transition-colors">
                  {isPlaying ? (
                    <svg className="w-7 h-7" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
                    </svg>
                  ) : (
                    <svg className="w-7 h-7" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M8 5v14l11-7z" />
                    </svg>
                  )}
                </button>
                <span className="text-white/80 text-sm font-medium">
                  {formatTime(currentTime)} / {formatTime(video.duration)}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Video Info */}
        <div className="mt-4 text-center">
          <h3 className="font-semibold text-lg">{video.product_name}</h3>
          <p className="text-gray-400 text-sm mt-1">
            Variant {video.variant_index + 1} • Clip {video.clip_index + 1}
          </p>
          <p className="text-gray-500 text-xs mt-1">
            {video.provider} • {video.model}
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-3 mt-5">
          <button
            onClick={handleDownload}
            disabled={isDownloading}
            className="flex-1 py-3 bg-accent-cyan rounded-xl text-sm font-semibold flex items-center justify-center gap-2 hover:bg-accent-cyan/90 transition-colors disabled:opacity-50"
          >
            {isDownloading ? (
              <>
                <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Downloading...
              </>
            ) : (
              <>
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                Download
              </>
            )}
          </button>
          <button
            onClick={onClose}
            className="flex-1 py-3 bg-dark-elevated rounded-xl text-sm font-semibold hover:bg-dark-card transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

export default function LibraryPage() {
  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedVideo, setSelectedVideo] = useState<VideoItem | null>(null);

  useEffect(() => {
    const fetchVideos = async () => {
      try {
        const response = await fetch(`${getApiBase()}/library`);
        if (response.ok) {
          const data = await response.json();
          setVideos(data.videos || []);
        }
      } catch {
        // Backend not running - show empty state silently
      } finally {
        setIsLoading(false);
      }
    };

    fetchVideos();
  }, []);

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
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
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Video Library</h1>
        <p className="text-gray-400 mt-1">{videos.length} videos generated</p>
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-2 mb-6 overflow-x-auto pb-2">
        <button className="px-4 py-2 rounded-xl bg-accent-cyan/20 text-accent-cyan text-sm font-medium whitespace-nowrap">
          All Videos
        </button>
        <button className="px-4 py-2 rounded-xl text-gray-400 text-sm font-medium whitespace-nowrap">
          Recent
        </button>
        <button className="px-4 py-2 rounded-xl text-gray-400 text-sm font-medium whitespace-nowrap">
          By Product
        </button>
      </div>

      {/* Video Grid */}
      {videos.length === 0 ? (
        <div className="text-center py-12">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-dark-card flex items-center justify-center">
            <svg className="w-8 h-8 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
          </div>
          <p className="text-gray-400">No videos yet</p>
          <p className="text-gray-500 text-sm mt-1">Generated videos will appear here</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3">
          {videos.map((video) => (
            <Card
              key={`${video.session_id}-${video.variant_index}-${video.clip_index}`}
              className="p-0 overflow-hidden"
            >
              <VideoThumbnail
                video={video}
                onClick={() => setSelectedVideo(video)}
              />
              <div className="p-3">
                <p className="font-medium text-sm truncate">{video.product_name}</p>
                <p className="text-gray-500 text-xs mt-1">{formatDate(video.created_at)}</p>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Video Modal */}
      {selectedVideo && (
        <VideoModal
          video={selectedVideo}
          onClose={() => setSelectedVideo(null)}
        />
      )}
    </div>
  );
}
