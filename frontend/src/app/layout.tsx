import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "StratAI — AI Strategy Built for Your Business",
  description:
    "StratAI analyzes market trends, competitor landscapes, and industry data to generate actionable strategies for your business. Powered by AI, built for decision-makers.",
  keywords: "AI strategy, business strategy, market analysis, competitor intelligence, AI agents",
  openGraph: {
    title: "StratAI — AI Strategy Built for Your Business",
    description: "AI-powered market analysis and business strategy generation for modern teams.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
