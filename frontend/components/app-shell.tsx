"use client";

import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth-provider";
import { Navigation } from "@/components/navigation";
import { RequireAuth } from "@/components/require-auth";

/** Header, role-aware navigation, logout, and the protected content area. */
export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const router = useRouter();

  async function handleLogout() {
    await logout();
    router.replace("/login");
  }

  return (
    <RequireAuth>
      <div className="flex min-h-screen flex-col">
        <header className="border-b border-zinc-200 bg-white">
          <div className="mx-auto flex w-full max-w-5xl flex-col gap-4 px-6 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-lg font-semibold tracking-tight">Enrollio</p>
              {user !== null && (
                <p className="text-xs text-zinc-500">
                  {user.full_name} ·{" "}
                  {user.roles.map((role) => role.name).join(", ")}
                </p>
              )}
            </div>

            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-6">
              <Navigation permissions={user?.permissions ?? []} />
              <button
                className="self-start rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium text-zinc-700 hover:bg-zinc-100"
                onClick={handleLogout}
                type="button"
              >
                Log out
              </button>
            </div>
          </div>
        </header>

        <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-10">
          {children}
        </main>
      </div>
    </RequireAuth>
  );
}
