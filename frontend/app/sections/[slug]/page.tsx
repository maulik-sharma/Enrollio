"use client";

import { useParams } from "next/navigation";

import { useAuth } from "@/components/auth-provider";
import { AppShell } from "@/components/app-shell";
import { navItemBySlug, visibleNavItems } from "@/lib/navigation";

export default function SectionPage() {
  const params = useParams<{ slug: string }>();
  const { user } = useAuth();

  const slug = typeof params.slug === "string" ? params.slug : "";
  const item = navItemBySlug(slug);
  const allowed =
    user !== null &&
    visibleNavItems(user.permissions).some((visible) => visible.slug === slug);

  let content: React.ReactNode;
  if (item === undefined) {
    content = <p className="text-sm text-zinc-600">This section does not exist.</p>;
  } else if (!allowed) {
    content = (
      <p className="text-sm text-zinc-600">
        You do not have access to this section.
      </p>
    );
  } else {
    content = (
      <div className="flex flex-col gap-3">
        <h1 className="text-3xl font-semibold tracking-tight">{item.label}</h1>
        <p className="text-sm text-zinc-600">
          This module arrives in a later milestone. Authentication, roles, and
          navigation are in place now.
        </p>
      </div>
    );
  }

  return <AppShell>{content}</AppShell>;
}
