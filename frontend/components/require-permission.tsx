"use client";

import { useAuth } from "@/components/auth-provider";

/** Render children only when the signed-in user holds ``permission``. */
export function RequirePermission({
  permission,
  children,
}: {
  permission: string;
  children: React.ReactNode;
}) {
  const { user } = useAuth();
  if (user === null) {
    return null;
  }
  if (!user.permissions.includes(permission)) {
    return (
      <p className="rounded-lg bg-zinc-100 px-4 py-3 text-sm text-zinc-700">
        You do not have access to this section.
      </p>
    );
  }
  return <>{children}</>;
}
