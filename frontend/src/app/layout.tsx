/**
 * Root layout component.
 *
 * Defines the global HTML structure, font configuration, and provider
 * wrapping for the entire Next.js application. This file is automatically
 * applied to all routes in the app directory.
 *
 * Key setup:
 *   - ``Inter`` font from Google Fonts for a clean, readable UI.
 *   - Warm sand/ochre theme via Tailwind custom colors on the ``<body>`` element.
 *   - ``Providers`` wraps the app in React Query and authentication context.
 *   - ``Toaster`` from react-hot-toast provides global toast notifications.
 */

import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Toaster } from "react-hot-toast";
import "./globals.css";
import Providers from "./providers";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "OmniCare",
  description: "OmniCare insurance and claims assistant",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body
        id="app-root"
        className={`${inter.className} h-screen flex flex-col overflow-hidden bg-sand-50 text-warm-ink antialiased`}
        data-testid="app-root"
      >
        <Providers>
          {children}
          <Toaster
            position="top-right"
            toastOptions={{
              style: {
                background: "rgba(255, 255, 255, 0.85)",
                color: "#2b2926",
                border: "1px solid rgba(214, 207, 195, 0.5)",
                boxShadow: "0 4px 16px rgba(43,41,38,0.05)",
                opacity: 0.75,
              },
            }}
          />
        </Providers>
      </body>
    </html>
  );
}
