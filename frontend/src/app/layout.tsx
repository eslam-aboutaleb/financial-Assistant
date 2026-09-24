import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Toaster } from "react-hot-toast";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "OmniCare Assistant",
  description: "OmniCare Financial customer assistant chat",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${inter.className} h-screen flex flex-col overflow-hidden bg-gray-950 text-gray-100`}
      >
        {children}
        <Toaster
          position="bottom-center"
          toastOptions={{ style: { background: "#1f2937", color: "#fff" } }}
        />
      </body>
    </html>
  );
}
