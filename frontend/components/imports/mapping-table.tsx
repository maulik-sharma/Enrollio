"use client";

import { SYSTEM_FIELDS, type ColumnMapping, type SystemField } from "@/lib/imports-api";

export function MappingTable({
  headers,
  mapping,
  onChange,
  disabled = false,
}: {
  headers: readonly string[];
  mapping: ColumnMapping;
  onChange: (source: string, target: SystemField | "") => void;
  disabled?: boolean;
}) {
  const used = new Set(
    Object.values(mapping).filter((value): value is SystemField => value !== ""),
  );

  return (
    <div className="overflow-hidden rounded-xl border border-zinc-200 bg-white">
      <table className="w-full text-left text-sm">
        <thead className="bg-zinc-50 text-xs uppercase tracking-wide text-zinc-500">
          <tr>
            <th className="px-4 py-3 font-medium">Source column</th>
            <th className="px-4 py-3 font-medium">System field</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-100">
          {headers.map((header) => {
            const selected = mapping[header] ?? "";
            return (
              <tr key={header}>
                <td className="px-4 py-3 font-medium text-zinc-800">{header}</td>
                <td className="px-4 py-3">
                  <select
                    aria-label={`Map ${header}`}
                    className="w-full max-w-xs rounded-md border border-zinc-300 bg-white px-3 py-2 text-zinc-900 outline-none focus:border-zinc-500 disabled:bg-zinc-100"
                    disabled={disabled}
                    onChange={(event) =>
                      onChange(header, event.target.value as SystemField | "")
                    }
                    value={selected}
                  >
                    <option value="">Ignore this column</option>
                    {SYSTEM_FIELDS.map((field) => (
                      <option
                        disabled={used.has(field.value) && selected !== field.value}
                        key={field.value}
                        value={field.value}
                      >
                        {field.label}
                        {"required" in field && field.required ? " *" : ""}
                      </option>
                    ))}
                  </select>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
