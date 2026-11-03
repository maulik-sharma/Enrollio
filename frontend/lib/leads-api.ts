import { apiJson, apiRequest, apiVoid } from "@/lib/api";
import type {
  Catalogues,
  Lead,
  LeadCreateResponse,
  LeadDetail,
  LeadList,
  LifecycleStatus,
} from "@/lib/types";

export type LeadFilters = {
  search?: string;
  lifecycle_status?: string;
  programme_id?: string;
  source_id?: string;
  campus_id?: string;
};

export type ManualLeadInput = {
  first_name: string;
  last_name?: string;
  email?: string;
  phone?: string;
  programme_id?: string;
  campus_id?: string;
  source_id?: string;
  admission_cycle?: string;
  academic_score?: string;
  graduation_year?: number;
};

const LIST_LIMIT = 20;

function queryString(params: Record<string, string | undefined>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") {
      query.set(key, value);
    }
  }
  const rendered = query.toString();
  return rendered ? `?${rendered}` : "";
}

export function fetchLeads(
  filters: LeadFilters,
  cursor: string | null,
): Promise<LeadList> {
  return apiJson<LeadList>(
    `/api/leads${queryString({
      ...filters,
      cursor: cursor ?? undefined,
      limit: String(LIST_LIMIT),
      sort: "-created_at",
    })}`,
  );
}

export function fetchLead(leadId: string): Promise<LeadDetail> {
  return apiJson<LeadDetail>(`/api/leads/${leadId}`);
}

export function createLead(input: ManualLeadInput): Promise<LeadCreateResponse> {
  return apiJson<LeadCreateResponse>("/api/leads", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function transitionLead(
  leadId: string,
  toState: LifecycleStatus,
  reason: string,
): Promise<Lead> {
  return apiJson<Lead>(`/api/leads/${leadId}/lifecycle`, {
    method: "POST",
    body: JSON.stringify({ to_state: toState, reason }),
  });
}

export function fetchCatalogues(): Promise<Catalogues> {
  return apiJson<Catalogues>("/api/catalogues");
}

export function grantConsent(
  studentId: string,
  channel: string,
  category: string,
): Promise<void> {
  return apiVoid(`/api/students/${studentId}/consent`, {
    method: "POST",
    body: JSON.stringify({
      channel,
      category,
      granted: true,
      source: "staff",
      method: "manual_entry",
    }),
  });
}

export function revokeConsent(
  studentId: string,
  channel: string,
  category: string,
): Promise<void> {
  return apiVoid(
    `/api/students/${studentId}/consent/${channel}/${category}?source=staff&method=manual_entry`,
    { method: "DELETE" },
  );
}

export async function downloadImportErrors(jobId: string): Promise<Blob> {
  const response = await apiRequest(`/api/imports/${jobId}/errors.csv`);
  if (!response.ok) {
    throw new Error("The error report could not be downloaded");
  }
  return response.blob();
}

/** Trigger a browser download for an in-memory blob. */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
