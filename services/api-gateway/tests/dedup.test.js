const { dedupeChunks } = require("../src/dedup");

const chunk = (document_id, position_index, text = "t") => ({
  document_id,
  position_index,
  text,
});

describe("dedupeChunks", () => {
  test("removes exact position duplicates from the same document", () => {
    const result = dedupeChunks([chunk("a", 3), chunk("a", 3), chunk("a", 7)]);
    expect(result).toHaveLength(2);
    expect(result.map((c) => c.position_index)).toEqual([3, 7]);
  });

  test("keeps same position across different documents", () => {
    const result = dedupeChunks([chunk("a", 3), chunk("b", 3)]);
    expect(result).toHaveLength(2);
  });

  test("keeps the higher-ranked chunk (input order preserved)", () => {
    const first = chunk("a", 3, "high score");
    const result = dedupeChunks([first, chunk("a", 3, "low score")]);
    expect(result[0].text).toBe("high score");
  });

  test("window drops adjacent overlapping chunks", () => {
    const result = dedupeChunks([chunk("a", 3), chunk("a", 4), chunk("a", 9)], 1);
    expect(result.map((c) => c.position_index)).toEqual([3, 9]);
  });

  test("empty input", () => {
    expect(dedupeChunks([])).toEqual([]);
  });
});
