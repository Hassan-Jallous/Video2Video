import type { Metadata, Viewport } from "next";
import "./globals.css";
import MobileLayout from "@/components/layout/MobileLayout";

export const metadata: Metadata = {
  title: "Video2Video",
  description: "AI-Powered TikTok Product Video Clone Platform",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Video2Video",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  themeColor: "#0A0A0F",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        <MobileLayout>{children}</MobileLayout>
      </body>
    </html>
  );
}
