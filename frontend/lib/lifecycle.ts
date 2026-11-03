import type { LifecycleStatus } from "@/lib/types";

export const LIFECYCLE_LABELS: Record<LifecycleStatus, string> = {
  new_enquiry: "New enquiry",
  contacted: "Contacted",
  engaged: "Engaged",
  qualified: "Qualified",
  counselling_scheduled: "Counselling scheduled",
  counselling_completed: "Counselling completed",
  application_started: "Application started",
  application_submitted: "Application submitted",
  admission_offered: "Admission offered",
  converted: "Converted",
  lost: "Lost",
  disqualified: "Disqualified",
  unresponsive: "Unresponsive",
  opted_out: "Opted out",
};

const TONES: Record<string, string> = {
  new_enquiry: "bg-sky-50 text-sky-700 ring-sky-200",
  contacted: "bg-blue-50 text-blue-700 ring-blue-200",
  engaged: "bg-indigo-50 text-indigo-700 ring-indigo-200",
  qualified: "bg-violet-50 text-violet-700 ring-violet-200",
  counselling_scheduled: "bg-amber-50 text-amber-700 ring-amber-200",
  counselling_completed: "bg-amber-50 text-amber-800 ring-amber-200",
  application_started: "bg-orange-50 text-orange-700 ring-orange-200",
  application_submitted: "bg-orange-50 text-orange-800 ring-orange-200",
  admission_offered: "bg-lime-50 text-lime-700 ring-lime-200",
  converted: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  lost: "bg-zinc-100 text-zinc-600 ring-zinc-200",
  disqualified: "bg-zinc-100 text-zinc-600 ring-zinc-200",
  unresponsive: "bg-zinc-100 text-zinc-600 ring-zinc-200",
  opted_out: "bg-rose-50 text-rose-700 ring-rose-200",
};

export function lifecycleLabel(status: string): string {
  return LIFECYCLE_LABELS[status as LifecycleStatus] ?? status;
}

export function lifecycleTone(status: string): string {
  return TONES[status] ?? "bg-zinc-100 text-zinc-600 ring-zinc-200";
}

export function lifecycleOptions(): { value: string; label: string }[] {
  return Object.entries(LIFECYCLE_LABELS).map(([value, label]) => ({
    value,
    label,
  }));
}

export function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function studentName(student: {
  first_name: string;
  last_name: string;
}): string {
  return `${student.first_name} ${student.last_name}`.trim();
}
