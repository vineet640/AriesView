// Deduplication filter for retrieved chunks.
//
// Weaviate hybrid search merges vector and BM25 results, so the same chunk
// (or immediately adjacent, largely overlapping chunks) can appear more
// than once in the top-k. Sending near-duplicate context wastes LLM context
// window and skews the answer toward the repeated text. Chunks are kept in
// score order; a chunk is dropped when a kept chunk from the same document
// sits at the same position_index, or within `window` positions of it.

function dedupeChunks(chunks, window = 0) {
  const kept = [];
  for (const chunk of chunks) {
    const overlaps = kept.some(
      (k) =>
        k.document_id === chunk.document_id &&
        Math.abs(k.position_index - chunk.position_index) <= window
    );
    if (!overlaps) kept.push(chunk);
  }
  return kept;
}

module.exports = { dedupeChunks };
