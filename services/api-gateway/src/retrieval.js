// Retrieval: embed the query with the same SBERT model used at ingestion
// (both vectors must live in the same vector space for cosine similarity to
// be meaningful), then run Weaviate hybrid search (semantic + BM25) scoped
// to the portfolios the token grants access to.

const EMBEDDING_URL = process.env.EMBEDDING_URL || "http://localhost:8001";
const WEAVIATE_URL = process.env.WEAVIATE_URL || "http://localhost:8080";
const TOP_K = 5;

async function embedQuery(query) {
  const res = await fetch(`${EMBEDDING_URL}/embed`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ texts: [query] }),
  });
  if (!res.ok) throw new Error(`Embedding service error: ${res.status}`);
  const data = await res.json();
  return data.vectors[0];
}

async function hybridSearch(query, vector, portfolios, limit = TOP_K) {
  // Role-based access: unless the token grants "*", restrict retrieval to
  // the user's portfolios via a where filter.
  const whereClause = portfolios.includes("*")
    ? ""
    : `where: {path: ["portfolio"], operator: ContainsAny, valueText: ${JSON.stringify(portfolios)}},`;

  const gql = `{
    Get {
      Chunk(
        ${whereClause}
        hybrid: {query: ${JSON.stringify(query)}, vector: ${JSON.stringify(vector)}, alpha: 0.5}
        limit: ${limit}
      ) {
        text
        document_id
        source_file
        section_label
        position_index
        _additional { score }
      }
    }
  }`;

  const res = await fetch(`${WEAVIATE_URL}/v1/graphql`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query: gql }),
  });
  if (!res.ok) throw new Error(`Weaviate error: ${res.status}`);
  const data = await res.json();
  if (data.errors) throw new Error(`Weaviate GraphQL: ${JSON.stringify(data.errors)}`);
  return (data.data.Get.Chunk || []).map((c) => ({
    ...c,
    score: parseFloat(c._additional.score),
  }));
}

async function retrieve(query, portfolios) {
  const vector = await embedQuery(query);
  // Over-fetch so the dedup filter can still return a full top-5.
  return hybridSearch(query, vector, portfolios, TOP_K * 2);
}

module.exports = { retrieve, embedQuery, hybridSearch, TOP_K };
