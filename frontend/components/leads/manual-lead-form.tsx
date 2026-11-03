"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { ApiError } from "@/lib/api";
import { createLead, fetchCatalogues } from "@/lib/leads-api";
import type { Catalogues, LeadCreateResponse } from "@/lib/types";

type FormValues = {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  programme_id: string;
  campus_id: string;
  source_id: string;
  admission_cycle: string;
  academic_score: string;
  graduation_year: string;
};

const EMPTY: FormValues = {
  first_name: "",
  last_name: "",
  email: "",
  phone: "",
  programme_id: "",
  campus_id: "",
  source_id: "",
  admission_cycle: "",
  academic_score: "",
  graduation_year: "",
};

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function validate(values: FormValues): Record<string, string> {
  const errors: Record<string, string> = {};
  if (values.first_name.trim() === "") {
    errors.first_name = "A first name is required.";
  }
  const email = values.email.trim();
  const phone = values.phone.trim();
  if (email === "" && phone === "") {
    errors.email = "Enter an email address or a phone number.";
    errors.phone = "Enter an email address or a phone number.";
  }
  if (email !== "" && !EMAIL_PATTERN.test(email)) {
    errors.email = "Enter a valid email address.";
  }
  if (values.academic_score !== "") {
    const score = Number(values.academic_score);
    if (Number.isNaN(score) || score < 0 || score > 100) {
      errors.academic_score = "Score must be between 0 and 100.";
    }
  }
  if (values.graduation_year !== "") {
    const year = Number(values.graduation_year);
    if (!Number.isInteger(year) || year < 1950 || year > 2100) {
      errors.graduation_year = "Enter a year between 1950 and 2100.";
    }
  }
  return errors;
}

export function ManualLeadForm() {
  const router = useRouter();
  const { user } = useAuth();
  const canAssign = user?.permissions.includes("leads.assign") === true;
  const [values, setValues] = useState<FormValues>(EMPTY);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [catalogues, setCatalogues] = useState<Catalogues | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [duplicate, setDuplicate] = useState<LeadCreateResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchCatalogues()
      .then((data) => {
        if (!cancelled) {
          setCatalogues(data);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setMessage("Catalogue options could not be loaded; you can still save.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function update(field: keyof FormValues, value: string) {
    setValues((current) => ({ ...current, [field]: value }));
    setErrors((current) => {
      const next = { ...current };
      delete next[field];
      return next;
    });
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const found = validate(values);
    setErrors(found);
    if (Object.keys(found).length > 0) {
      return;
    }

    setSubmitting(true);
    setMessage(null);
    setDuplicate(null);
    try {
      const created = await createLead({
        first_name: values.first_name.trim(),
        last_name: values.last_name.trim(),
        email: values.email.trim() || undefined,
        phone: values.phone.trim() || undefined,
        programme_id: values.programme_id || undefined,
        campus_id: values.campus_id || undefined,
        source_id: values.source_id || undefined,
        admission_cycle: values.admission_cycle.trim() || undefined,
        academic_score: values.academic_score || undefined,
        graduation_year:
          values.graduation_year === ""
            ? undefined
            : Number(values.graduation_year),
      });
      if (created.duplicate_detected) {
        setDuplicate(created);
        return;
      }
      router.push(`/sections/leads/${created.id}`);
    } catch (caught) {
      setMessage(
        caught instanceof ApiError
          ? caught.message
          : "The lead could not be saved. Try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="flex flex-col gap-6" onSubmit={handleSubmit} noValidate>
      {message !== null && (
        <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">
          {message}
        </p>
      )}
      {duplicate !== null && (
        <div className="rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800" role="status">
          <p className="font-medium">That contact already has a lead for this enquiry.</p>
          <p className="mt-1">
            We reused the existing record instead of creating a duplicate.{" "}
            <Link
              className="underline"
              href={`/sections/leads/${duplicate.id}`}
            >
              Open the existing lead
            </Link>
            .
          </p>
        </div>
      )}

      <fieldset className="grid gap-4 rounded-xl border border-zinc-200 bg-white p-5 sm:grid-cols-2">
        <legend className="px-1 text-sm font-semibold text-zinc-900">
          Student
        </legend>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-zinc-700">First name *</span>
          <input
            className="rounded-md border border-zinc-300 px-3 py-2 text-zinc-900 outline-none focus:border-zinc-500"
            onChange={(event) => update("first_name", event.target.value)}
            value={values.first_name}
          />
          {errors.first_name !== undefined && (
            <span className="text-xs text-red-600">{errors.first_name}</span>
          )}
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-zinc-700">Last name</span>
          <input
            className="rounded-md border border-zinc-300 px-3 py-2 text-zinc-900 outline-none focus:border-zinc-500"
            onChange={(event) => update("last_name", event.target.value)}
            value={values.last_name}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-zinc-700">Email</span>
          <input
            className="rounded-md border border-zinc-300 px-3 py-2 text-zinc-900 outline-none focus:border-zinc-500"
            onChange={(event) => update("email", event.target.value)}
            type="email"
            value={values.email}
          />
          {errors.email !== undefined && (
            <span className="text-xs text-red-600">{errors.email}</span>
          )}
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-zinc-700">Phone</span>
          <input
            className="rounded-md border border-zinc-300 px-3 py-2 text-zinc-900 outline-none focus:border-zinc-500"
            onChange={(event) => update("phone", event.target.value)}
            placeholder="+91…"
            value={values.phone}
          />
          {errors.phone !== undefined && (
            <span className="text-xs text-red-600">{errors.phone}</span>
          )}
        </label>
      </fieldset>

      <fieldset className="grid gap-4 rounded-xl border border-zinc-200 bg-white p-5 sm:grid-cols-2">
        <legend className="px-1 text-sm font-semibold text-zinc-900">
          Enquiry
        </legend>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-zinc-700">Programme</span>
          <select
            className="rounded-md border border-zinc-300 bg-white px-3 py-2 text-zinc-900 outline-none focus:border-zinc-500"
            onChange={(event) => update("programme_id", event.target.value)}
            value={values.programme_id}
          >
            <option value="">No programme</option>
            {catalogues?.programmes.map((programme) => (
              <option key={programme.id} value={programme.id}>
                {programme.name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-zinc-700">Campus</span>
          <select
            className="rounded-md border border-zinc-300 bg-white px-3 py-2 text-zinc-900 outline-none focus:border-zinc-500"
            onChange={(event) => update("campus_id", event.target.value)}
            value={values.campus_id}
          >
            <option value="">No campus</option>
            {catalogues?.campuses.map((campus) => (
              <option key={campus.id} value={campus.id}>
                {campus.name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-zinc-700">Source</span>
          <select
            className="rounded-md border border-zinc-300 bg-white px-3 py-2 text-zinc-900 outline-none focus:border-zinc-500"
            onChange={(event) => update("source_id", event.target.value)}
            value={values.source_id}
          >
            <option value="">No source</option>
            {catalogues?.sources.map((source) => (
              <option key={source.id} value={source.id}>
                {source.name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-zinc-700">Admission cycle</span>
          <input
            className="rounded-md border border-zinc-300 px-3 py-2 text-zinc-900 outline-none focus:border-zinc-500"
            onChange={(event) => update("admission_cycle", event.target.value)}
            placeholder="2026-fall"
            value={values.admission_cycle}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-zinc-700">Score</span>
          <input
            className="rounded-md border border-zinc-300 px-3 py-2 text-zinc-900 outline-none focus:border-zinc-500"
            onChange={(event) => update("academic_score", event.target.value)}
            placeholder="0–100"
            type="number"
            value={values.academic_score}
          />
          {errors.academic_score !== undefined && (
            <span className="text-xs text-red-600">{errors.academic_score}</span>
          )}
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-zinc-700">Graduation year</span>
          <input
            className="rounded-md border border-zinc-300 px-3 py-2 text-zinc-900 outline-none focus:border-zinc-500"
            onChange={(event) => update("graduation_year", event.target.value)}
            placeholder="2027"
            type="number"
            value={values.graduation_year}
          />
          {errors.graduation_year !== undefined && (
            <span className="text-xs text-red-600">{errors.graduation_year}</span>
          )}
        </label>
        {canAssign && (
          <p className="text-xs text-zinc-500 sm:col-span-2">
            Managers can reassign this lead from the lead detail page.
          </p>
        )}
      </fieldset>

      <div className="flex gap-2">
        <button
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-60"
          disabled={submitting}
          type="submit"
        >
          {submitting ? "Saving…" : "Create lead"}
        </button>
        <button
          className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100"
          onClick={() => router.back()}
          type="button"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
