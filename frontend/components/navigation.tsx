import Link from "next/link";

import { visibleNavItems } from "@/lib/navigation";

/** Role-aware navigation: only items the user's permissions allow. */
export function Navigation({
  permissions,
}: {
  permissions: readonly string[];
}) {
  const items = visibleNavItems(permissions);

  if (items.length === 0) {
    return (
      <p className="text-sm text-zinc-500">
        No sections are available for this account yet.
      </p>
    );
  }

  return (
    <nav aria-label="Main navigation">
      <ul className="flex flex-wrap gap-x-4 gap-y-2 text-sm">
        {items.map((item) => (
          <li key={item.slug}>
            <Link
              className="text-zinc-600 underline-offset-4 hover:text-zinc-900 hover:underline"
              href={`/sections/${item.slug}`}
            >
              {item.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
