"use client";

import BottomNav from "./BottomNav";

interface MobileLayoutProps {
  children: React.ReactNode;
}

export default function MobileLayout({ children }: MobileLayoutProps) {
  return (
    <div className="min-h-screen bg-dark-bg">
      {/* Main content with bottom padding for nav */}
      <main className="pb-28">
        {children}
      </main>

      {/* Bottom Navigation */}
      <BottomNav />
    </div>
  );
}
