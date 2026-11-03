"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { ApiError } from "@/lib/api";
import {
  fetchLead,
  grantConsent,
  revokeConsent,
  transitionLead,
} from "@/lib/leads-api";
import {
  formatDate,
  formatDateTime,
  lifecycleLabel,
  lifecycleTone,
  studentName,
} from "@/lib/lifecycle";
import type {
  ConsentRecord,
  LeadDetail,
  LifecycleStatus,
} from "@/lib/types";

const CHANNELS = ["email", "whatsapp", "sms", "phone"] as const;
const CATEGORIES = ["transactional", "promotional"] as const;

function latestConsent(
  records: ConsentRecord[],
  channel: string,
  category: string,
): ConsentRecord | null {
  return (
    records.find(
      (record) => record.channel === channel && record.category === category,
    ) ?? null
  );
}

export function LeadDetailView({ leadId }: { leadId: string }) {
  const { user } = useAuth();
  const canManage = user?.permissions.includes("leads.view_all") === true;
  const backHref = canManage ? "/sections/leads" : "/sections/my-leads";

  const [detail, setDetail] = useState<LeadDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [target, setTarget] = useState<LifecycleStatus | "">("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setDetail(await fetchLead(leadId));
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "This lead could not be loaded.",
      );
    } finally {
      setLoading(false);
    }
  }, [leadId]);

  useEffect(() => {
    void load();
  }, [load]);

  const consent = useMemo(() => detail?.consent_summary ?? [], [detail]);

  async function submitTransition(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (target === "" || reason.trim() === "") {
      return;
    }
    setBusy(true);
    setNotice(null);
    try {
      await transitionLead(leadId, target, reason.trim());
      setReason("");
      setTarget("");
      setNotice("Lifecycle updated.");
      await load();
    } catch (caught) {
      setNotice(
        caught instanceof ApiError
          ? caught.message
          : "The lifecycle change was rejected.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function toggleConsent(
    channel: string,
    category: string,
    granted: boolean,
  ) {
    if (detail === null) {
      return;
    }
    setBusy(true);
    setNotice(null);
    try {
      if (granted) {
        await revokeConsent(detail.student.id, channel, category);
      } else {
        await grantConsent(detail.student.id, channel, category);
      }
      await load();
    } catch (caught) {
      setNotice(
        caught instanceof ApiError
          ? caught.message
          : "The consent change could not be saved.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <p className="text-sm text-zinc-500">Loading lead…</p>;
  }
  if (error !== null || detail === null) {
    return (
      <div className="flex flex-col gap-3">
        <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">
          {error ?? "This lead does not exist."}
        </p>
        <Link className="text-sm underline" href={backHref}>
          Back to leads
        </Link>
      </div>
    );
  }

  const { lead, student } = detail;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <Link className="text-sm text-zinc-500 underline-offset-4 hover:underline" href={backHref}>
          ← Back to {canManage ? "all leads" : "my leads"}
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-3xl font-semibold tracking-tight">
            {studentName(student)}
          </h1>
          <span
            className={`inline-flex rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset ${lifecycleTone(
              lead.lifecycle_status,
            )}`}
          >
            {lifecycleLabel(lead.lifecycle_status)}
          </span>
        </div>
        <p className="text-sm text-zinc-500">
          Created {formatDate(lead.created_at)} · {lead.admission_cycle}
        </p>
      </div>

      {notice !== null && (
        <p className="rounded-lg bg-zinc-100 px-4 py-3 text-sm text-zinc-700" role="status">
          {notice}
        </p>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <section className="flex flex-col gap-3 rounded-xl border border-zinc-200 bg-white p-5 lg:col-span-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Enquiry
          </h2>
          <dl className="grid gap-4 sm:grid-cols-2">
            <div>
              <dt className="text-xs text-zinc-500">Programme</dt>
              <dd className="text-sm text-zinc-900">
                {detail.programme_name ?? "Not set"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-zinc-500">Campus</dt>
              <dd className="text-sm text-zinc-900">
                {detail.campus_name ?? "Not set"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-zinc-500">Source</dt>
              <dd className="text-sm text-zinc-900">
                {detail.source_name ?? "Not set"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-zinc-500">Owner</dt>
              <dd className="text-sm text-zinc-900">
                {detail.assigned_counsellor_name ?? "Unassigned"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-zinc-500">Last updated</dt>
              <dd className="text-sm text-zinc-900">
                {formatDateTime(lead.updated_at)}
              </dd>
            </div>
          </dl>
        </section>

        <section className="flex flex-col gap-3 rounded-xl border border-zinc-200 bg-white p-5">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Student
          </h2>
          <dl className="flex flex-col gap-3 text-sm">
            <div>
              <dt className="text-xs text-zinc-500">Email</dt>
              <dd className="text-zinc-900">
                {student.email_normalised ?? "Not provided"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-zinc-500">Phone</dt>
              <dd className="text-zinc-900">
                {student.phone_e164 ?? "Not provided"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-zinc-500">Score</dt>
              <dd className="text-zinc-900">
                {student.academic_score ?? "Not set"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-zinc-500">Graduation year</dt>
              <dd className="text-zinc-900">
                {student.graduation_year ?? "Not set"}
              </dd>
            </div>
          </dl>
        </section>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="flex flex-col gap-4 rounded-xl border border-zinc-200 bg-white p-5">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Lifecycle
          </h2>
          {detail.allowed_transitions.length === 0 ? (
            <p className="text-sm text-zinc-600">
              No lifecycle changes are available for your role at this stage.
            </p>
          ) : (
            <form className="flex flex-col gap-3" onSubmit={submitTransition}>
              <label className="flex flex-col gap-1 text-sm">
                <span className="font-medium text-zinc-700">Move to</span>
                <select
                  className="rounded-md border border-zinc-300 bg-white px-3 py-2 text-zinc-900 outline-none focus:border-zinc-500"
                  onChange={(event) =>
                    setTarget(event.target.value as LifecycleStatus | "")
                  }
                  value={target}
                >
                  <option value="">Choose a stage</option>
                  {detail.allowed_transitions.map((state) => (
                    <option key={state} value={state}>
                      {lifecycleLabel(state)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-sm">
                <span className="font-medium text-zinc-700">Reason</span>
                <input
                  className="rounded-md border border-zinc-300 px-3 py-2 text-zinc-900 outline-none focus:border-zinc-500"
                  onChange={(event) => setReason(event.target.value)}
                  placeholder="What changed?"
                  value={reason}
                />
              </label>
              <button
                className="self-start rounded-md bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-60"
                disabled={busy || target === "" || reason.trim() === ""}
                type="submit"
              >
                {busy ? "Saving…" : "Update stage"}
              </button>
            </form>
          )}
        </section>

        <section className="flex flex-col gap-4 rounded-xl border border-zinc-200 bg-white p-5">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
              Consent
            </h2>
            {!canManage && (
              <span className="text-xs text-zinc-500">Read only</span>
            )}
          </div>
          <div className="overflow-hidden rounded-lg border border-zinc-200">
            <table className="w-full text-left text-xs">
              <thead className="bg-zinc-50 uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="px-3 py-2 font-medium">Channel</th>
                  {CATEGORIES.map((category) => (
                    <th className="px-3 py-2 font-medium" key={category}>
                      {category}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {CHANNELS.map((channel) => (
                  <tr key={channel}>
                    <td className="px-3 py-2 font-medium capitalize text-zinc-700">
                      {channel}
                    </td>
                    {CATEGORIES.map((category) => {
                      const record = latestConsent(consent, channel, category);
                      const granted = record?.granted === true;
                      return (
                        <td className="px-3 py-2" key={category}>
                          <span
                            className={
                              granted
                                ? "text-emerald-700"
                                : record === null
                                  ? "text-zinc-400"
                                  : "text-rose-700"
                            }
                          >
                            {granted
                              ? "Granted"
                              : record === null
                                ? "No record"
                                : "Revoked"}
                          </span>
                          {canManage && (
                            <button
                              className="ml-2 underline disabled:opacity-50"
                              disabled={busy}
                              onClick={() =>
                                void toggleConsent(channel, category, granted)
                              }
                              type="button"
                            >
                              {granted ? "Revoke" : "Grant"}
                            </button>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <section className="flex flex-col gap-3 rounded-xl border border-dashed border-zinc-300 bg-white p-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
          Timeline
        </h2>
        <p className="text-sm text-zinc-600">
          Communication history will appear here once email and WhatsApp land in
          M3. Lifecycle changes are already recorded in the database.
        </p>
      </section>
    </div>
  );
}
