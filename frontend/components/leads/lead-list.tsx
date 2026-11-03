"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { ApiError } from "@/lib/api";
import type { LeadFilters } from "@/lib/leads-api";
import { fetchCatalogues, fetchLeads } from "@/lib/leads-api";
import {
  formatDate,
  lifecycleLabel,
  lifecycleOptions,
  lifecycleTone,
  studentName,
} from "@/lib/lifecycle";
import type { Catalogues, LeadListItem } from "@/lib/types";

const EMPTY_FILTERS: LeadFilters = {};

type LoadState = "idle" | "loading" | "error";

export function LeadList({ scope }: { scope: "all" | "assigned" }) {
  const { user } = useAuth();
  const canManage =
    user?.permissions.includes("leads.view_all") === true && scope === "all";
  const canCreate =
    user?.permissions.includes("leads.view_all") === true ||
    user?.permissions.includes("leads.view_assigned") === true;

  const [draft, setDraft] = useState<LeadFilters>(EMPTY_FILTERS);
  const [filters, setFilters] = useState<LeadFilters>(EMPTY_FILTERS);
  const [catalogues, setCatalogues] = useState<Catalogues | null>(null);
  const [items, setItems] = useState<LeadListItem[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  const [page, setPage] = useState(0);
  const cursor = cursors[page] ?? null;
  const [state, setState] = useState<LoadState>("idle");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchCatalogues()
      .then((data) => {
        if (!cancelled) {
          setCatalogues(data);
        }
      })
      .catch(() => {
        // Filters stay usable without catalogue options.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setState("loading");
    setError(null);

    fetchLeads(filters, cursor)
      .then((pageData) => {
        if (cancelled) {
          return;
        }
        setItems(pageData.items);
        setNextCursor(pageData.next_cursor);
        setState("idle");
      })
      .catch((caught: unknown) => {
        if (cancelled) {
          return;
        }
        setError(
          caught instanceof ApiError
            ? caught.message
            : "The lead list could not be loaded.",
        );
        setState("error");
      });

    return () => {
      cancelled = true;
    };
  }, [filters, cursor]);

  const applyFilters = useCallback(() => {
    setFilters(draft);
    setPage(0);
    setCursors([null]);
  }, [draft]);

  const clearFilters = useCallback(() => {
    setDraft(EMPTY_FILTERS);
    setFilters(EMPTY_FILTERS);
    setPage(0);
    setCursors([null]);
  }, []);

  const showNext = useCallback(() => {
    if (nextCursor === null) {
      return;
    }
    setCursors((current) => [...current.slice(0, page + 1), nextCursor]);
    setPage((value) => value + 1);
  }, [nextCursor, page]);

  const showPrevious = useCallback(() => {
    setPage((value) => Math.max(0, value - 1));
  }, []);

  const activeFilterCount = useMemo(
    () => Object.values(filters).filter((value) => value !== "").length,
    [filters],
  );

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">
            {scope === "all" ? "Leads" : "My leads"}
          </h1>
          <p className="mt-1 text-sm text-zinc-600">
            {scope === "all"
              ? "Every enquiry in the admission funnel."
              : "Enquiries assigned to you."}
          </p>
        </div>
        {canManage && (
          <div className="flex flex-wrap gap-2">
            <Link
              className="rounded-md bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-700"
              href="/sections/leads/new"
            >
              New lead
            </Link>
            <Link
              className="rounded-md border border-zinc-300 px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100"
              href="/sections/leads/import"
            >
              Import leads
            </Link>
          </div>
        )}
        {!canManage && canCreate && (
          <Link
            className="self-start rounded-md bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-700"
            href="/sections/leads/new"
          >
            New lead
          </Link>
        )}
      </div>

      <form
        className="grid gap-3 rounded-xl border border-zinc-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-3"
        onSubmit={(event) => {
          event.preventDefault();
          applyFilters();
        }}
      >
        <label className="flex flex-col gap-1 text-sm lg:col-span-3">
          <span className="font-medium text-zinc-700">Search</span>
          <input
            className="rounded-md border border-zinc-300 px-3 py-2 text-zinc-900 outline-none focus:border-zinc-500"
            onChange={(event) =>
              setDraft({ ...draft, search: event.target.value })
            }
            placeholder="Name, email, or phone"
            type="search"
            value={draft.search ?? ""}
          />
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-zinc-700">Lifecycle</span>
          <select
            className="rounded-md border border-zinc-300 bg-white px-3 py-2 text-zinc-900 outline-none focus:border-zinc-500"
            onChange={(event) =>
              setDraft({ ...draft, lifecycle_status: event.target.value })
            }
            value={draft.lifecycle_status ?? ""}
          >
            <option value="">Any stage</option>
            {lifecycleOptions().map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-zinc-700">Programme</span>
          <select
            className="rounded-md border border-zinc-300 bg-white px-3 py-2 text-zinc-900 outline-none focus:border-zinc-500"
            onChange={(event) =>
              setDraft({ ...draft, programme_id: event.target.value })
            }
            value={draft.programme_id ?? ""}
          >
            <option value="">Any programme</option>
            {catalogues?.programmes.map((programme) => (
              <option key={programme.id} value={programme.id}>
                {programme.name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-zinc-700">Source</span>
          <select
            className="rounded-md border border-zinc-300 bg-white px-3 py-2 text-zinc-900 outline-none focus:border-zinc-500"
            onChange={(event) =>
              setDraft({ ...draft, source_id: event.target.value })
            }
            value={draft.source_id ?? ""}
          >
            <option value="">Any source</option>
            {catalogues?.sources.map((source) => (
              <option key={source.id} value={source.id}>
                {source.name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-zinc-700">Campus</span>
          <select
            className="rounded-md border border-zinc-300 bg-white px-3 py-2 text-zinc-900 outline-none focus:border-zinc-500"
            onChange={(event) =>
              setDraft({ ...draft, campus_id: event.target.value })
            }
            value={draft.campus_id ?? ""}
          >
            <option value="">Any campus</option>
            {catalogues?.campuses.map((campus) => (
              <option key={campus.id} value={campus.id}>
                {campus.name}
              </option>
            ))}
          </select>
        </label>

        <div className="flex items-end gap-2 lg:col-span-2">
          <button
            className="rounded-md bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-700"
            type="submit"
          >
            Apply filters
          </button>
          <button
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100"
            onClick={clearFilters}
            type="button"
          >
            Clear
          </button>
          {activeFilterCount > 0 && (
            <span className="pb-2 text-xs text-zinc-500">
              {activeFilterCount} active
            </span>
          )}
        </div>
      </form>

      {state === "error" && (
        <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">
          {error}
        </p>
      )}

      <div className="overflow-hidden rounded-xl border border-zinc-200 bg-white">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="bg-zinc-50 text-xs uppercase tracking-wide text-zinc-500">
            <tr>
              <th className="px-4 py-3 font-medium">Student</th>
              <th className="px-4 py-3 font-medium">Enquiry</th>
              <th className="px-4 py-3 font-medium">Stage</th>
              <th className="px-4 py-3 font-medium">Owner</th>
              <th className="px-4 py-3 font-medium">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {state === "loading" && (
              <tr>
                <td className="px-4 py-8 text-zinc-500" colSpan={5}>
                  Loading leads…
                </td>
              </tr>
            )}
            {state !== "loading" && items.length === 0 && (
              <tr>
                <td className="px-4 py-8 text-zinc-500" colSpan={5}>
                  No leads match these filters yet.
                </td>
              </tr>
            )}
            {state !== "loading" &&
              items.map((lead) => (
                <tr className="hover:bg-zinc-50" key={lead.id}>
                  <td className="px-4 py-3">
                    <Link
                      className="font-medium text-zinc-900 underline-offset-4 hover:underline"
                      href={`/sections/leads/${lead.id}`}
                    >
                      {studentName(lead.student)}
                    </Link>
                    <p className="text-xs text-zinc-500">
                      {lead.student.email_normalised ??
                        lead.student.phone_e164 ??
                        "No contact"}
                    </p>
                  </td>
                  <td className="px-4 py-3 text-zinc-600">
                    <p>{lead.programme_name ?? "No programme"}</p>
                    <p className="text-xs text-zinc-500">
                      {[lead.campus_name, lead.admission_cycle]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${lifecycleTone(
                        lead.lifecycle_status,
                      )}`}
                    >
                      {lifecycleLabel(lead.lifecycle_status)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-zinc-600">
                    {lead.assigned_counsellor_name ?? "Unassigned"}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-zinc-500">
                    {formatDate(lead.created_at)}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-sm">
        <p className="text-zinc-500">Page {page + 1}</p>
        <div className="flex gap-2">
          <button
            className="rounded-md border border-zinc-300 px-3 py-1.5 font-medium text-zinc-700 hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={page === 0}
            onClick={showPrevious}
            type="button"
          >
            Previous
          </button>
          <button
            className="rounded-md border border-zinc-300 px-3 py-1.5 font-medium text-zinc-700 hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={nextCursor === null}
            onClick={showNext}
            type="button"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
