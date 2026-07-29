const { assemblePrompt, SYSTEM_MESSAGE } = require("../src/prompt");

describe("assemblePrompt", () => {
  const chunks = [
    {
      text: "Tenant may terminate with 90 days notice.",
      source_file: "Lease_TenantA.pdf",
      section_label: "Termination Clause",
    },
    {
      text: "Base rent is $42 per square foot.",
      source_file: "Lease_TenantA.pdf",
      section_label: "Rent Provisions",
    },
  ];

  test("numbers context blocks with source labels", () => {
    const { prompt } = assemblePrompt(chunks, "Can the tenant terminate early?");
    expect(prompt).toContain("[1] Source: Lease_TenantA.pdf | Section: Termination Clause");
    expect(prompt).toContain("[2] Source: Lease_TenantA.pdf | Section: Rent Provisions");
    expect(prompt).toContain("Tenant may terminate with 90 days notice.");
  });

  test("ends with the user query", () => {
    const { prompt } = assemblePrompt(chunks, "Can the tenant terminate early?");
    expect(prompt.trimEnd().endsWith("User: Can the tenant terminate early?")).toBe(true);
  });

  test("system message restricts answers to context", () => {
    const { system } = assemblePrompt(chunks, "q");
    expect(system).toBe(SYSTEM_MESSAGE);
    expect(system).toMatch(/only the provided document context|based only on the provided/i);
  });
});
