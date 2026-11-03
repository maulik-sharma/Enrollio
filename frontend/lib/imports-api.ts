import { apiJson, apiRequest } from "@/lib/api";
import type { ImportJob, MappingTemplate } from "@/lib/types";

/** System fields accepted by the backend mapping endpoint. */
export const SYSTEM_FIELDS = [
  { value: "name", label: "Full name", required: true },
  { value: "email", label: "Email" },
  { value: "phone", label: "Phone" },
  { value: "course", label: "Course / programme" },
  { value: "campus", label: "Campus" },
  { value: "source", label: "Lead source" },
  { value: "score", label: "Score (0–100)" },
  { value: "graduation_year", label: "Graduation year" },
  { value: "admission_cycle", label: "Admission cycle" },
] as const;

export type SystemField = (typeof SYSTEM_FIELDS)[number]["value"];

/** Source column -> system field, as the API expects it. */
export type ColumnMapping = Record<string, SystemField | "">;

export async function uploadImport(
  file: File,
  sourceName: string,
): Promise<ImportJob> {
  const body = new FormData();
  body.append("file", file);
  if (sourceName.trim() !== "") {
    body.append("source_name", sourceName.trim());
  }
  return apiJson<ImportJob>("/api/leads/import", { method: "POST", body });
}

export async function fetchMappingTemplate(
  sourceName: string,
): Promise<MappingTemplate | null> {
  const response = await apiRequest(
    `/api/imports/mapping-template?source_name=${encodeURIComponent(sourceName)}`,
  );
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error("The saved mapping could not be loaded");
  }
  return (await response.json()) as MappingTemplate;
}

export function submitMapping(
  jobId: string,
  mapping: Record<string, string>,
): Promise<ImportJob> {
  return apiJson<ImportJob>(`/api/imports/${jobId}/mapping`, {
    method: "POST",
    body: JSON.stringify({ mapping }),
  });
}

export function fetchImportJob(jobId: string): Promise<ImportJob> {
  return apiJson<ImportJob>(`/api/imports/${jobId}`);
}

/** Drop empty target selections before sending the mapping. */
export function mappingPayload(mapping: ColumnMapping): Record<string, string> {
  const payload: Record<string, string> = {};
  for (const [source, target] of Object.entries(mapping)) {
    if (target !== "") {
      payload[source] = target;
    }
  }
  return payload;
}

/** Guess a target field from a header, so most uploads need no edits. */
export function suggestMapping(
  headers: readonly string[],
  saved: Record<string, string> | null,
): ColumnMapping {
  const mapping: ColumnMapping = {};
  for (const header of headers) {
    mapping[header] = "";
  }
  if (saved !== null) {
    for (const header of headers) {
      const savedTarget = saved[header];
      if (savedTarget !== undefined && isSystemField(savedTarget)) {
        mapping[header] = savedTarget;
      }
    }
    return mapping;
  }

  const synonyms: Record<string, SystemField> = {
    name: "name",
    "full name": "name",
    "student name": "name",
    email: "email",
    "email address": "email",
    "e-mail": "email",
    phone: "phone",
    mobile: "phone",
    "phone number": "phone",
    "mobile number": "phone",
    course: "course",
    programme: "course",
    program: "course",
    campus: "campus",
    source: "source",
    "lead source": "source",
    score: "score",
    percentage: "score",
    "graduation year": "graduation_year",
    "passing year": "graduation_year",
    "admission cycle": "admission_cycle",
    cycle: "admission_cycle",
  };
  for (const header of headers) {
    const target = synonyms[header.trim().toLowerCase()];
    if (target !== undefined) {
      mapping[header] = target;
    }
  }
  return mapping;
}

function isSystemField(value: string): value is SystemField {
  return SYSTEM_FIELDS.some((field) => field.value === value);
}
