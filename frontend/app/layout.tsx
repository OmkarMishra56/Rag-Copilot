import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Support Copilot — RAG Console",
  description: "Enterprise AI Customer Support Copilot",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-ink text-[#E6EBF1] antialiased">{children}</body>
    </html>
  );
}
