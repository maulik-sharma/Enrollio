"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/components/auth-provider";

/**
 * Client-side guard: renders a loading state while the refresh cookie is
 * exchanged, then sends unauthenticated visitors to /login.
 */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user === null) {
      router.replace("/login");
    }
  }, [loading, user, router]);

  if (loading) {
    return (
      <p className="p-8 text-sm text-zinc-500" role="status">
        Restoring session…
      </p>
    );
  }

  if (user === null) {
    return null;
  }

  return <>{children}</>;
}
