"use client";

import { useEffect, useState } from "react";
import Card from "@/components/ui/Card";

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

export default function LibraryPage() {
  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedVideo, setSelectedVideo] = useState<VideoItem | null>(null);

  useEffect(() => {
    const fetchVideos = async () => {
      try {
        const response = await fetch("http://localhost:8000/api/v1/library");
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
              onClick={() => setSelectedVideo(video)}
            >
              <div className="aspect-[9/16] bg-dark-elevated relative">
                <video
                  src={video.video_url}
                  className="w-full h-full object-cover"
                  preload="metadata"
                />
                <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between">
                  <span className="bg-black/60 px-2 py-0.5 rounded text-xs">
                    {video.duration.toFixed(1)}s
                  </span>
                  <span className="bg-accent-cyan/20 text-accent-cyan px-2 py-0.5 rounded text-xs">
                    V{video.variant_index + 1}
                  </span>
                </div>
              </div>
              <div className="p-3">
                <p className="font-medium text-sm truncate">{video.product_name}</p>
                <p className="text-gray-500 text-xs mt-1">{formatDate(video.created_at)}</p>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Video Preview Modal */}
      {selectedVideo && (
        <div
          className="fixed inset-0 bg-black/90 z-50 flex items-center justify-center p-4"
          onClick={() => setSelectedVideo(null)}
        >
          <div className="w-full max-w-sm" onClick={(e) => e.stopPropagation()}>
            <video
              src={selectedVideo.video_url}
              className="w-full rounded-2xl"
              controls
              autoPlay
              playsInline
            />
            <div className="mt-4 text-center">
              <h3 className="font-semibold">{selectedVideo.product_name}</h3>
              <p className="text-gray-400 text-sm mt-1">
                Variant {selectedVideo.variant_index + 1} • Clip {selectedVideo.clip_index + 1}
              </p>
              <div className="flex gap-3 mt-4 justify-center">
                <button className="px-4 py-2 bg-accent-cyan rounded-xl text-sm font-medium">
                  Download
                </button>
                <button
                  className="px-4 py-2 bg-dark-elevated rounded-xl text-sm font-medium"
                  onClick={() => setSelectedVideo(null)}
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
