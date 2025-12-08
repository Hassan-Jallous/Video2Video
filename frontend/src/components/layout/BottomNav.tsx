"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  {
    href: "/library",
    label: "Library",
    icon: (active: boolean) => (
      <svg className="w-6 h-6" fill={active ? "currentColor" : "none"} viewBox="0 0 24 24" stroke="currentColor" strokeWidth={active ? 0 : 2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
      </svg>
    ),
  },
  {
    href: "/settings",
    label: "Settings",
    icon: (active: boolean) => (
      <svg className="w-6 h-6" fill={active ? "currentColor" : "none"} viewBox="0 0 24 24" stroke="currentColor" strokeWidth={active ? 0 : 2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
];

export default function BottomNav() {
  const pathname = usePathname();

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 safe-bottom">
      <div className="mx-4 mb-4">
        <div className="glass rounded-3xl border border-dark-border px-6 py-3">
          <div className="flex items-center justify-around">
            {/* Library */}
            <Link
              href="/library"
              className={`flex flex-col items-center gap-1 transition-colors ${
                pathname === "/library" ? "text-accent-cyan" : "text-gray-400"
              }`}
            >
              {navItems[0].icon(pathname === "/library")}
              <span className="text-xs">{navItems[0].label}</span>
            </Link>

            {/* FAB - New Session */}
            <Link
              href="/new"
              className="flex items-center justify-center w-14 h-14 -mt-8 rounded-full bg-gradient-button shadow-lg shadow-accent-purple/30 active:scale-95 transition-transform"
            >
              <svg className="w-7 h-7 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
              </svg>
            </Link>

            {/* Settings */}
            <Link
              href="/settings"
              className={`flex flex-col items-center gap-1 transition-colors ${
                pathname === "/settings" ? "text-accent-cyan" : "text-gray-400"
              }`}
            >
              {navItems[1].icon(pathname === "/settings")}
              <span className="text-xs">{navItems[1].label}</span>
            </Link>
          </div>
        </div>
      </div>
    </nav>
  );
}
