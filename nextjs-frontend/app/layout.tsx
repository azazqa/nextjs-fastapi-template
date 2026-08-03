import type { Metadata } from "next";
import { Noto_Sans_KR } from "next/font/google";
import NextTopLoader from "nextjs-toploader";
import { Toaster } from "@/components/ui/sonner";
import "./globals.css";

const notoSansKR = Noto_Sans_KR({
  subsets: ["latin"],
  weight: ["100", "200", "300", "400", "500", "700", "900"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "HRD Work24",
  description: "HRD Work24 Application",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${notoSansKR.variable}`}>
        <NextTopLoader color="#2563eb" height={3} showSpinner={false} />
        {children}
        <Toaster richColors />
      </body>
    </html>
  );
}
