"use client";

import Link from "next/link";

import { useAuth } from "@/components/auth-provider";

/** Landing content shown after login. Real modules arrive in later milestones. */
export function Dashboard() {
  const { user } = useAuth();
  if (user === null) {
    return null;
  }

  return (
    <section className="flex flex-col gap-4">
      <h1 className="text-3xl font-semibold tracking-tight">
        Welcome, {user.full_name}
      </h1>
      <p className="text-sm text-zinc-600">
        You are signed in as{" "}
        <span className="font-medium">
          {user.roles.map((role) => role.name).join(", ")}
        </span>
        . Use the navigation above to open your sections. Modules arrive
        milestone by milestone; this shell already enforces who can see what.
      </p>
      <p className="text-sm text-zinc-500">
        Need to switch accounts?{" "}
        <Link className="underline" href="/login">
          Sign in as someone else
        </Link>
        .
      </p>
    </section>
  );
}
