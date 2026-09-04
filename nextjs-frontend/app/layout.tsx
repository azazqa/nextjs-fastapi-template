import type { Metadata } from "next";
import { Noto_Sans_KR } from "next/font/google";
import NextTopLoader from "nextjs-toploader";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import "./globals.css";
import { cn } from "@/lib/utils";

const notoSansKR = Noto_Sans_KR({
  subsets: ["latin"],
  weight: ["100", "200", "300", "400", "500", "700", "900"],
  variable: "--font-sans",
  display: "swap",
});

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
    <html lang="ko" className={cn("font-sans", notoSansKR.variable)}>
      <body>
        <TooltipProvider delayDuration={0}>
          <NextTopLoader color="var(--primary)" height={3} showSpinner={false} />
          {children}
          <Toaster richColors />
        </TooltipProvider>
      </body>
    </html>
  );
}
