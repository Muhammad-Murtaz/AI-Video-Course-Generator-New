import type { Metadata } from "next";
import { DM_Sans } from "next/font/google";
import "./globals.css";
import { ClerkProvider } from "@clerk/nextjs";
import { Toaster } from "@/components/ui/sonner";
import Provider from "./Provider";

const font = DM_Sans({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "AI Video Course Generator",
  description: "Generate complete educational video courses with AI — slides, narration, and captions.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <ClerkProvider>
      <html lang="en">
        <body className={font.className}>
          <Provider>{children}</Provider>
          <Toaster position="top-center" richColors />
        </body>
      </html>
    </ClerkProvider>
  );
}