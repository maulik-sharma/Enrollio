"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { MappingTable } from "@/components/imports/mapping-table";
import { ApiError } from "@/lib/api";
import {
  fetchImportJob,
  fetchMappingTemplate,
  mappingPayload,
  submitMapping,
  suggestMapping,
  uploadImport,
  type ColumnMapping,
} from "@/lib/imports-api";
import { downloadImportErrors, saveBlob } from "@/lib/leads-api";
import type { ImportJob } from "@/lib/types";

type Step = "upload" | "map" | "results";

const MAX_BYTES = 10 * 1024 * 1024;

function sleep(milliseconds: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, milliseconds);
  });
}

function pollUntilDone(jobId: string): Promise<ImportJob> {
  let attempts = 0;
  return (async function poll(): Promise<ImportJob> {
    const job = await fetchImportJob(jobId);
    if (job.status === "completed" || job.status === "failed") {
      return job;
    }
    attempts += 1;
    if (attempts > 60) {
      return job;
    }
    await sleep(1000);
    return poll();
  })();
}

export function ImportWizard() {
  const [step, setStep] = useState<Step>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [sourceName, setSourceName] = useState("");
  const [job, setJob] = useState<ImportJob | null>(null);
  const [mapping, setMapping] = useState<ColumnMapping>({});
  const [savedTemplate, setSavedTemplate] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ImportJob | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (file === null) {
      return;
    }
    if (sourceName.trim() === "") {
      setSourceName(file.name.replace(/\.(csv|xlsx)$/i, ""));
    }
  }, [file, sourceName]);

  const payload = useMemo(() => mappingPayload(mapping), [mapping]);
  const targets = useMemo(() => new Set(Object.values(payload)), [payload]);
  const mappingErrors = useMemo(() => {
    const problems: string[] = [];
    if (!targets.has("name")) {
      problems.push("Map one column to the student name.");
    }
    if (!targets.has("email") && !targets.has("phone")) {
      problems.push("Map at least one of email or phone.");
    }
    return problems;
  }, [targets]);

  function chooseFile(selected: File | null) {
    setError(null);
    if (selected === null) {
      setFile(null);
      return;
    }
    if (!/\.(csv|xlsx)$/i.test(selected.name)) {
      setError("Choose a .csv or .xlsx file.");
      return;
    }
    if (selected.size > MAX_BYTES) {
      setError("The file is larger than 10 MB.");
      return;
    }
    setFile(selected);
    setSourceName(selected.name.replace(/\.(csv|xlsx)$/i, ""));
  }

  async function handleUpload(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (file === null) {
      setError("Choose a file first.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const uploaded = await uploadImport(file, sourceName);
      const template = await fetchMappingTemplate(uploaded.source_name).catch(
        () => null,
      );
      setSavedTemplate(template !== null);
      setMapping(suggestMapping(uploaded.headers, template?.mapping ?? null));
      setJob(uploaded);
      setStep("map");
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "The file could not be uploaded.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleStart(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (job === null || mappingErrors.length > 0) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const started = await submitMapping(job.id, payload);
      const finished =
        started.status === "completed" || started.status === "failed"
          ? started
          : await pollUntilDone(started.id);
      setResult(finished);
      setStep("results");
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "The import could not be started.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function downloadErrors() {
    if (result === null) {
      return;
    }
    try {
      saveBlob(await downloadImportErrors(result.id), `import-${result.id}-errors.csv`);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Download failed.",
      );
    }
  }

  function reset() {
    setStep("upload");
    setFile(null);
    setJob(null);
    setResult(null);
    setMapping({});
    setSavedTemplate(false);
    setError(null);
    if (fileInput.current !== null) {
      fileInput.current.value = "";
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <ol className="flex flex-wrap gap-2 text-xs">
        {(["upload", "map", "results"] as Step[]).map((name, index) => {
          const active = name === step;
          return (
            <li
              className={
                active
                  ? "rounded-full bg-zinc-900 px-3 py-1 font-medium text-white"
                  : "rounded-full bg-zinc-100 px-3 py-1 text-zinc-600"
              }
              key={name}
            >
              {index + 1}. {name === "map" ? "Map columns" : name}
            </li>
          );
        })}
      </ol>

      {error !== null && (
        <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">
          {error}
        </p>
      )}

      {step === "upload" && (
        <form
          className="flex flex-col gap-4 rounded-xl border border-zinc-200 bg-white p-6"
          onSubmit={handleUpload}
        >
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Import leads</h1>
            <p className="mt-1 text-sm text-zinc-600">
              Upload a CSV or XLSX file with up to 10,000 rows. Nothing is
              created until you confirm the column mapping.
            </p>
          </div>

          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-zinc-700">Partner or source name</span>
            <input
              className="rounded-md border border-zinc-300 px-3 py-2 text-zinc-900 outline-none focus:border-zinc-500"
              onChange={(event) => setSourceName(event.target.value)}
              placeholder="e.g. Coaching Partner"
              value={sourceName}
            />
            <span className="text-xs text-zinc-500">
              Saved mappings are reused by this name next time.
            </span>
          </label>

          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-zinc-700">File</span>
            <input
              accept=".csv,.xlsx"
              className="rounded-md border border-dashed border-zinc-300 px-3 py-6 text-sm text-zinc-600 file:mr-4 file:rounded-md file:border-0 file:bg-zinc-900 file:px-3 file:py-2 file:text-sm file:font-medium file:text-white"
              onChange={(event) => chooseFile(event.target.files?.[0] ?? null)}
              ref={fileInput}
              type="file"
            />
            <span className="text-xs text-zinc-500">
              {file === null ? "No file selected" : `${file.name} · ${Math.ceil(file.size / 1024)} KB`}
            </span>
          </label>

          <div className="flex gap-2">
            <button
              className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-60"
              disabled={busy || file === null}
              type="submit"
            >
              {busy ? "Reading columns…" : "Continue to mapping"}
            </button>
            <Link
              className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100"
              href="/sections/leads"
            >
              Cancel
            </Link>
          </div>
        </form>
      )}

      {step === "map" && job !== null && (
        <form className="flex flex-col gap-4" onSubmit={handleStart}>
          <div className="rounded-xl border border-zinc-200 bg-white p-6">
            <h1 className="text-2xl font-semibold tracking-tight">Map columns</h1>
            <p className="mt-1 text-sm text-zinc-600">
              {job.original_filename} · {job.total_rows} rows ·{" "}
              {job.headers.length} columns
              {savedTemplate ? " · saved mapping loaded" : ""}
            </p>
            <p className="mt-2 text-sm text-zinc-600">
              Name is required, plus at least one of email or phone. Leave
              columns that do not apply on “Ignore this column”.
            </p>
          </div>

          <MappingTable
            headers={job.headers}
            mapping={mapping}
            onChange={(source, target) =>
              setMapping((current) => ({ ...current, [source]: target }))
            }
          />

          <div className="rounded-xl border border-zinc-200 bg-white p-4 text-sm text-zinc-600">
            <p className="font-medium text-zinc-800">Preview</p>
            <p className="mt-1">
              {Object.keys(payload).length} of {job.headers.length} columns will
              be imported into {job.total_rows} rows. Duplicate contacts are
              flagged; invalid rows are rejected with a reason in the report.
            </p>
            {mappingErrors.length > 0 && (
              <ul className="mt-2 list-disc pl-5 text-red-700">
                {mappingErrors.map((problem) => (
                  <li key={problem}>{problem}</li>
                ))}
              </ul>
            )}
          </div>

          <div className="flex gap-2">
            <button
              className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-60"
              disabled={busy || mappingErrors.length > 0}
              type="submit"
            >
              {busy ? "Importing…" : "Start import"}
            </button>
            <button
              className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100"
              onClick={reset}
              type="button"
            >
              Back
            </button>
          </div>
        </form>
      )}

      {step === "results" && result !== null && (
        <div className="flex flex-col gap-4">
          <div className="rounded-xl border border-zinc-200 bg-white p-6">
            <h1 className="text-2xl font-semibold tracking-tight">
              {result.status === "failed" ? "Import failed" : "Import finished"}
            </h1>
            <p className="mt-1 text-sm text-zinc-600">
              {result.original_filename} · {result.total_rows} rows
            </p>
            {result.status === "failed" && (
              <p className="mt-3 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
                {result.error_message ?? "Processing did not complete."}
              </p>
            )}
            {result.status === "processing" && (
              <p className="mt-3 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800">
                Processing is still running. Refresh this page in a moment.
              </p>
            )}
          </div>

          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-5">
            {[
              ["Rows", result.total_rows],
              ["Created", result.created_count],
              ["Merged", result.merged_count],
              ["Duplicates", result.duplicate_count],
              ["Rejected", result.rejected_count],
            ].map(([label, value]) => (
              <div
                className="rounded-xl border border-zinc-200 bg-white p-4"
                key={String(label)}
              >
                <dt className="text-xs uppercase tracking-wide text-zinc-500">
                  {label}
                </dt>
                <dd
                  className="mt-1 text-2xl font-semibold text-zinc-900"
                  data-testid={`count-${String(label).toLowerCase()}`}
                >
                  {value}
                </dd>
              </div>
            ))}
          </dl>

          <div className="flex flex-wrap gap-2">
            {result.rejected_count > 0 && (
              <button
                className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100"
                onClick={() => void downloadErrors()}
                type="button"
              >
                Download error report (CSV)
              </button>
            )}
            <Link
              className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700"
              href="/sections/leads"
            >
              View leads
            </Link>
            <button
              className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100"
              onClick={reset}
              type="button"
            >
              Import another file
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
