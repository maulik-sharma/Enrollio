import type { Metadata } from "next";
import "./globals.css";

import { AuthProvider } from "@/components/auth-provider";

export const metadata: Metadata = {
  title: "Enrollio",
  description: "Intelligent admission enquiry and lead nurturing.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
