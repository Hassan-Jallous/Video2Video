"use client";

import { useState, useEffect } from "react";
import Card from "@/components/ui/Card";
import ProgressBar from "@/components/ui/ProgressBar";
import StatRow from "@/components/ui/StatRow";
import Link from "next/link";
import { getApiBase } from "@/lib/api";

interface Session {
  session_id: string;
  product_name: string;
  status: string;
  num_variants: number;
  created_at: string;
  progress?: number;
  current_step?: string;
  variants_completed?: number;
  variants_total?: number;
}

interface Stats {
  totalVideos: number;
  completed: number;
  totalCost: number;
}

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<"overview" | "sessions">("overview");
  const [sessions, setSessions] = useState<Session[]>([]);
  const [stats, setStats] = useState<Stats>({ totalVideos: 0, completed: 0, totalCost: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      // Fetch sessions
      const sessionsRes = await fetch(`${getApiBase()}/sessions`);
      if (sessionsRes.ok) {
        const data = await sessionsRes.json();
        setSessions(data.sessions || []);

        // Calculate stats from sessions
        const completed = data.sessions.filter((s: Session) => s.status === "completed").length;
        setStats({
          totalVideos: data.sessions.length,
          completed: completed,
          totalCost: 0, // Could calculate from session data if stored
        });
      }
    } catch (error) {
      console.error("Failed to fetch data:", error);
    } finally {
      setLoading(false);
    }
  };

  // Find active (in-progress) session
  const activeSession = sessions.find(s =>
    ["pending", "downloading", "analyzing", "generating"].includes(s.status)
  );

  return (
    <div className="px-4 pt-12">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <Link href="/" className="text-2xl font-bold text-accent-cyan hover:opacity-80 transition-opacity">
          CloneVideo
        </Link>
        <div className="w-10 h-10 rounded-full bg-gradient-button flex items-center justify-center">
          <span className="text-lg">👋</span>
        </div>
      </div>

      {/* Tab Switcher */}
      <div className="flex gap-2 mb-6">
        <button
          onClick={() => setActiveTab("overview")}
          className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
            activeTab === "overview"
              ? "bg-accent-cyan/20 text-accent-cyan"
              : "text-gray-400"
          }`}
        >
          Overview
        </button>
        <button
          onClick={() => setActiveTab("sessions")}
          className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
            activeTab === "sessions"
              ? "bg-accent-cyan/20 text-accent-cyan"
              : "text-gray-400"
          }`}
        >
          Sessions
        </button>
      </div>

      {/* Overview Tab Content */}
      {activeTab === "overview" && (
        <>
          {/* Active Generation Card */}
          {activeSession && (
            <Link href={`/session/${activeSession.session_id}`}>
              <Card gradient className="mb-6">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className="font-semibold text-white">Active Generation</h3>
                    <p className="text-white/70 text-sm mt-1">{activeSession.product_name}</p>
                  </div>
                  <div className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center">
                    <span className="text-xs text-white">{activeSession.status}</span>
                  </div>
                </div>

                <div className="mb-2">
                  <p className="text-white/60 text-xs mb-2">{activeSession.current_step || "Processing..."}</p>
                  <ProgressBar
                    progress={activeSession.progress || 0}
                    showPercentage={true}
                  />
                </div>

                <p className="text-white/70 text-sm mt-3">
                  {activeSession.variants_completed || 0}/{activeSession.variants_total || activeSession.num_variants} variants
                </p>
              </Card>
            </Link>
          )}

          {/* Stats Card */}
          <Card>
            <StatRow
              icon={
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              }
              label="Total Sessions"
              value={stats.totalVideos}
              href="/library"
              color="cyan"
            />
            <StatRow
              icon={
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              }
              label="Completed"
              value={stats.completed}
              color="green"
            />
            <StatRow
              icon={
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              }
              label="Total Cost"
              value={`$${stats.totalCost.toFixed(2)}`}
              color="orange"
            />
          </Card>
        </>
      )}

      {/* Sessions Tab Content */}
      {activeTab === "sessions" && (
        <div className="flex flex-col gap-4">
          {loading ? (
            <Card className="text-center py-8 text-gray-400">Loading...</Card>
          ) : sessions.length === 0 ? (
            <Card className="text-center py-8 text-gray-400">No sessions yet. Create your first video!</Card>
          ) : (
            sessions.map((session) => (
              <Link key={session.session_id} href={`/session/${session.session_id}`} className="block">
                <Card className="flex items-center gap-4">
                  <div className="w-16 h-16 rounded-2xl bg-dark-elevated flex items-center justify-center">
                    <span className="text-2xl">📦</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium truncate">{session.product_name}</h3>
                    <p className="text-gray-400 text-sm">{session.num_variants} variants • {session.status}</p>
                  </div>
                  {session.status === "completed" && <span className="text-accent-green text-sm">✓</span>}
                  {session.status === "failed" && <span className="text-red-500 text-sm">✗</span>}
                </Card>
              </Link>
            ))
          )}
        </div>
      )}

      {/* Recent Sessions - Only show on Overview */}
      {activeTab === "overview" && sessions.length > 0 && (
        <div className="mt-6">
          <h2 className="text-lg font-semibold mb-4">Recent Sessions</h2>
          <div className="flex flex-col gap-4">
            {sessions.slice(0, 3).map((session) => (
              <Link key={session.session_id} href={`/session/${session.session_id}`} className="block">
                <Card className="flex items-center gap-4">
                  <div className="w-16 h-16 rounded-2xl bg-dark-elevated flex items-center justify-center">
                    <span className="text-2xl">📦</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium truncate">{session.product_name}</h3>
                    <p className="text-gray-400 text-sm">{session.num_variants} variants • {session.status}</p>
                  </div>
                  {session.status === "completed" && <span className="text-accent-green text-sm">✓</span>}
                  {session.status === "failed" && <span className="text-red-500 text-sm">✗</span>}
                </Card>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
