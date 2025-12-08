"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import Card from "@/components/ui/Card";
import ProgressBar from "@/components/ui/ProgressBar";
import Button from "@/components/ui/Button";

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

export default function SessionPage() {
  const router = useRouter();
  const params = useParams();
  const sessionId = params.id as string;

  const [session, setSession] = useState<Session | null>(null);
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Poll for status updates
  useEffect(() => {
    let mounted = true;

    const fetchStatus = async () => {
      try {
        const sessionRes = await fetch(`http://localhost:8000/api/v1/sessions/${sessionId}`);
        if (!mounted) return;
        if (sessionRes.ok) {
          setSession(await sessionRes.json());
        }

        const statusRes = await fetch(`http://localhost:8000/api/v1/sessions/${sessionId}/status`);
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
          <div className="space-y-4">
            {session.variants.map((variant) => (
              <Card key={variant.variant_index}>
                <h3 className="font-medium mb-3">Variant {variant.variant_index + 1}</h3>
                <div className="grid grid-cols-2 gap-2">
                  {variant.clips.map((clip) => (
                    <div
                      key={clip.clip_index}
                      className="aspect-video bg-dark-elevated rounded-xl overflow-hidden relative"
                    >
                      {clip.video_url ? (
                        <video
                          src={clip.video_url}
                          className="w-full h-full object-cover"
                          controls
                          playsInline
                        />
                      ) : (
                        <div className="flex items-center justify-center h-full">
                          {clip.status === "completed" ? (
                            <span className="text-accent-green">✓</span>
                          ) : clip.status === "failed" ? (
                            <span className="text-red-400">✕</span>
                          ) : (
                            <div className="animate-pulse w-6 h-6 rounded-full bg-dark-border" />
                          )}
                        </div>
                      )}
                      <div className="absolute bottom-1 right-1 bg-black/60 px-2 py-0.5 rounded text-xs">
                        {clip.duration.toFixed(1)}s
                      </div>
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
          <Button fullWidth variant="primary">
            Download All
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
