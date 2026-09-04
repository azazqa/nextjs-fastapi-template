import type { Metadata } from "next";
import { Noto_Sans_KR, Inter } from "next/font/google";
import NextTopLoader from "nextjs-toploader";
import { Toaster } from "@/components/ui/sonner";
import "./globals.css";
import { cn } from "@/lib/utils";

const inter = Inter({subsets:['latin'],variable:'--font-sans'});

export const metadata: Metadata = {
  title: "Application",
  description: "Application Description",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={cn("font-sans", inter.variable)}>
      <body className={`${inter.variable}`}>
        <NextTopLoader color="#2563eb" height={3} showSpinner={false} />
        {children}
        <Toaster richColors />
      </body>
    </html>
  );
}
