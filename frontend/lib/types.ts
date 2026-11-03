export type Role = {
  id: string;
  slug: string;
  name: string;
};

export type CurrentUser = {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  roles: Role[];
  permissions: string[];
};

export type LifecycleStatus =
  | "new_enquiry"
  | "contacted"
  | "engaged"
  | "qualified"
  | "counselling_scheduled"
  | "counselling_completed"
  | "application_started"
  | "application_submitted"
  | "admission_offered"
  | "converted"
  | "lost"
  | "disqualified"
  | "unresponsive"
  | "opted_out";

export type StudentSummary = {
  id: string;
  first_name: string;
  last_name: string;
  email_normalised: string | null;
  phone_e164: string | null;
  academic_score: string | null;
  graduation_year: number | null;
};

export type Student = StudentSummary & {
  date_of_birth: string | null;
};

export type Lead = {
  id: string;
  student_id: string;
  programme_id: string | null;
  campus_id: string | null;
  source_id: string | null;
  admission_cycle: string;
  lifecycle_status: LifecycleStatus;
  assigned_counsellor_id: string | null;
  import_job_id: string | null;
  created_at: string;
  updated_at: string;
};

export type LeadListItem = Lead & {
  student: StudentSummary;
  programme_name: string | null;
  campus_name: string | null;
  source_name: string | null;
  assigned_counsellor_name: string | null;
};

export type LeadList = {
  items: LeadListItem[];
  next_cursor: string | null;
};

export type ConsentRecord = {
  id: string;
  student_id: string;
  channel: "email" | "whatsapp" | "sms" | "phone";
  category: "transactional" | "promotional";
  granted: boolean;
  source: string;
  method: string;
  recorded_at: string;
};

export type LeadDetail = {
  lead: Lead;
  student: Student;
  consent_summary: ConsentRecord[];
  assessments: Record<string, unknown>[];
  allowed_transitions: LifecycleStatus[];
  programme_name: string | null;
  campus_name: string | null;
  source_name: string | null;
  assigned_counsellor_name: string | null;
};

export type ProgrammeOption = {
  id: string;
  name: string;
  code: string | null;
};

export type CampusOption = {
  id: string;
  name: string;
  city: string | null;
};

export type LeadSourceOption = {
  id: string;
  name: string;
};

export type Catalogues = {
  programmes: ProgrammeOption[];
  campuses: CampusOption[];
  sources: LeadSourceOption[];
};

export type ImportJob = {
  id: string;
  source_name: string;
  original_filename: string;
  file_type: string;
  status: "uploaded" | "processing" | "completed" | "failed";
  headers: string[];
  mapping: Record<string, string> | null;
  total_rows: number;
  created_count: number;
  merged_count: number;
  rejected_count: number;
  duplicate_count: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type MappingTemplate = {
  source_name: string;
  mapping: Record<string, string>;
  updated_at: string;
};

export type LeadCreateResponse = Lead & {
  duplicate_detected: boolean;
};
