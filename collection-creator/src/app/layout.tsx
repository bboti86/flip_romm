import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RomM Collection Creator",
  description: "Easily generate RomM collections from a list of games",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        {children}
      </body>
    </html>
  );
}
