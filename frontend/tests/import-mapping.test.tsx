import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { MappingTable } from "@/components/imports/mapping-table";
import {
  mappingPayload,
  suggestMapping,
  type ColumnMapping,
} from "@/lib/imports-api";

const HEADERS = ["Full Name", "Email Address", "Score", "Notes"];

function Harness() {
  const [mapping, setMapping] = useState<ColumnMapping>(
    suggestMapping(HEADERS, null),
  );
  return (
    <div>
      <MappingTable
        headers={HEADERS}
        mapping={mapping}
        onChange={(source, target) =>
          setMapping((current) => ({ ...current, [source]: target }))
        }
      />
      <output data-testid="payload">
        {JSON.stringify(mappingPayload(mapping))}
      </output>
    </div>
  );
}

describe("import column mapping", () => {
  it("suggests fields from common header names", () => {
    expect(suggestMapping(HEADERS, null)).toEqual({
      "Full Name": "name",
      "Email Address": "email",
      Score: "score",
      Notes: "",
    });
  });

  it("prefers a saved template over header guessing", () => {
    expect(
      suggestMapping(HEADERS, {
        "Full Name": "name",
        "Email Address": "phone",
        Score: "graduation_year",
      }),
    ).toEqual({
      "Full Name": "name",
      "Email Address": "phone",
      Score: "graduation_year",
      Notes: "",
    });
  });

  it("drops ignored columns from the submitted payload", () => {
    expect(
      mappingPayload({
        "Full Name": "name",
        "Email Address": "email",
        Notes: "",
      }),
    ).toEqual({ "Full Name": "name", "Email Address": "email" });
  });

  it("produces the payload the mapping component shows", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.selectOptions(
      screen.getByLabelText("Map Score"),
      "graduation_year",
    );

    expect(JSON.parse(screen.getByTestId("payload").textContent ?? "{}")).toEqual(
      {
        "Full Name": "name",
        "Email Address": "email",
        Score: "graduation_year",
      },
    );
  });
});
