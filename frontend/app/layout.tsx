import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Neighborrow — A little closer. A lot more possible.",
  description: "Borrow what you need. Share what you have. Find offers and requests in your neighborhood.",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
