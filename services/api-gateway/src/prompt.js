// Prompt assembly: system message + top-k chunks as numbered context blocks
// with source labels + the user query. The system message restricts the
// model to the provided context to prevent hallucination — critical for
// legal and financial documents.

const SYSTEM_MESSAGE = `You are an AI assistant for commercial real estate professionals.
Answer questions based only on the provided document context below.
If the answer is not present in the context, state that explicitly.
Do not speculate or draw on outside knowledge.`;

function assemblePrompt(chunks, query) {
  const context = chunks
    .map(
      (c, i) =>
        `[${i + 1}] Source: ${c.source_file} | Section: ${c.section_label}\n${c.text}`
    )
    .join("\n\n");
  return {
    system: SYSTEM_MESSAGE,
    prompt: `Context:\n${context}\n\nUser: ${query}`,
  };
}

module.exports = { assemblePrompt, SYSTEM_MESSAGE };
