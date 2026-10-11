---
id: llm/rag
title: Retrieval-augmented generation done properly (when not to use RAG, chunking, embeddings, hybrid search with RRF, pgvector vs dedicated vector stores, reranking, citations, permissions, freshness, retrieval evals)
area: llm
read_when: answering questions from your own documents or data, choosing an embedding model or vector store, tuning retrieval quality, adding citations, or keeping an index fresh and permission-aware
verified: 2026-10-10
revisit_days: 90
sources: ["https://www.anthropic.com/engineering/contextual-retrieval", "https://raw.githubusercontent.com/pgvector/pgvector/master/README.md", "https://developers.openai.com/api/docs/guides/embeddings", "https://huggingface.co/BAAI/bge-m3", "https://huggingface.co/spaces/mteb/leaderboard", "https://docs.cohere.com/docs/rerank-overview", "https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion", "https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/", "https://genai.owasp.org/llm-top-10/"]
---
# RAG done properly

RAG = find the right passages, put them in the prompt, make the model answer from them and cite them. Most bad answers are retrieval failures, so measure retrieval separately from generation. Postgres search basics (tsvector, pgvector indexes, when to add a search engine): `data/search-redis`.

## Decision guide

**1. Maybe you do not need RAG.** Anthropic: if the knowledge base is under about 200,000 tokens (about 500 pages), put all of it in the prompt and use prompt caching. Structured questions ("my unpaid invoices this month") are SQL behind a tool, not vector search. RAG is for large, changing, unstructured text.

**2. Chunk by structure, then measure.** Split on headings, articles, FAQ entries or pages, typically a few hundred tokens per chunk (Anthropic), with a little overlap only if passages get cut mid-thought. Keep metadata on every chunk: `doc_id`, title, section path, language, `tenant_id`, access labels, source URL, `updated_at`, content hash. Anthropic's **contextual retrieval** prepends a 50–100-token, model-written description of where the chunk sits in its document before embedding and BM25 indexing; it cut top-20 retrieval failures by 35% (embeddings) and 49% (with BM25), and 67% with reranking, on their test sets.

**3. Embeddings.** Pick by your languages and your eval, not a leaderboard rank alone (MTEB is a useful shortlist, including multilingual tasks). For French/English plus some local-language text, test multilingual models (BGE-M3 supports 100+ languages, inputs up to 8,192 tokens, and dense plus sparse outputs). Store the model id with each vector; changing models means re-embedding everything, so version the index. Mind dimensions: pgvector indexes `vector` up to 2,000 dimensions and `halfvec` up to 4,000; OpenAI's `text-embedding-3-large` is 3,072 by default but accepts a `dimensions` parameter to shorten it.

**4. Hybrid search by default.** Vectors miss exact terms (invoice numbers, error codes, product names, NIU numbers); keyword search (BM25 / Postgres full-text) misses paraphrases. Run both and fuse with Reciprocal Rank Fusion (score = Σ 1/(k + rank); Elasticsearch's default k is 60), which needs no score calibration. pgvector's README recommends exactly this: Postgres full-text search plus RRF or a cross-encoder.

**5. Rerank the top candidates.** Retrieve ~50–100 by hybrid search, rerank with a cross-encoder or a rerank API (Cohere Rerank, self-hosted cross-encoders), keep the top 5–20 for the prompt. Measure the latency it adds.

**6. pgvector or a dedicated vector database.**
| Choose pgvector when | Consider a dedicated store when |
|---|---|
| you already run Postgres; up to millions of chunks; you need joins, transactions and the same row-level permissions as the rest of your data | very large or fast-growing vector sets, many tenants with heavy filtering at high QPS, or you need features you would otherwise build (managed sharding, built-in hybrid) |

pgvector facts to plan for: exact search by default (perfect recall); HNSW gives better speed/recall than IVFFlat but builds slower and uses more memory; with approximate indexes, filters are applied **after** the index scan (with `hnsw.ef_search` = 40 and a filter matching 10% of rows, about 4 rows come back), so enable iterative index scans (0.8.0+) or use partial indexes / partitions per tenant.

**7. Permissions inside the query.** Filter by tenant and the user's access labels in the retrieval query itself, never after generation (OWASP LLM08). A document the user cannot open must never reach the prompt.

**8. Generate with citations.** Give each passage an id in a tag; instruct the model to answer only from passages, cite ids per claim, and say "I don't know" when they do not cover the question. Check in code that every cited id was in the context; show sources to the user with dates.

**9. Freshness.** Re-index on document change (event or content hash), delete chunks when sources are deleted or a user asks for erasure, record `updated_at` and prefer newer passages for time-sensitive questions. Schedule a full re-embed when you change embedding models.

**10. Evaluate in two layers.** Retrieval: a labelled set of question → relevant chunk ids, measured with recall@k and MRR on every chunking/embedding/index change. Generation: faithfulness (claims supported by passages), answer relevance and citation correctness (Ragas names these metrics: context precision/recall, faithfulness, response relevancy). Keep FR and EN questions in the set.

## Examples
```sql
WITH v AS (SELECT id, row_number() OVER (ORDER BY embedding <=> $1) r FROM chunks
           WHERE tenant_id = $2 ORDER BY embedding <=> $1 LIMIT 50),
     k AS (SELECT id, row_number() OVER (ORDER BY ts_rank_cd(tsv, q) DESC) r
           FROM chunks, websearch_to_tsquery('french', $3) q
           WHERE tenant_id = $2 AND tsv @@ q LIMIT 50)
SELECT id, sum(1.0 / (60 + r)) AS rrf FROM (SELECT * FROM v UNION ALL SELECT * FROM k) u
GROUP BY id ORDER BY rrf DESC LIMIT 20;   -- then rerank, keep the top 8
```

## Anti-patterns
- Vector-only search for corpora full of codes and names; one chunk size picked by habit.
- Filtering permissions after retrieval or in the prompt; one shared index across tenants without a filter.
- No retrieval eval ("the answers look fine"); citations never checked; stale chunks after deletes.
- Mixing vectors from two embedding models in one index.

## Checks
- [ ] Written reason RAG beats long context or SQL for this feature.
- [ ] Chunks carry tenant, access, source and timestamp metadata; filters run inside the query.
- [ ] Hybrid retrieval with fusion, then rerank; recall@k measured on a labelled FR/EN set.
- [ ] Answers cite passage ids that are verified in code; deletion removes chunks.

## Sources
- Anthropic, Contextual Retrieval: https://www.anthropic.com/engineering/contextual-retrieval
- pgvector README (indexes, filtering, iterative scans, hybrid search): https://raw.githubusercontent.com/pgvector/pgvector/master/README.md
- OpenAI embeddings guide (dimensions): https://developers.openai.com/api/docs/guides/embeddings
- BGE-M3 model card: https://huggingface.co/BAAI/bge-m3 · MTEB leaderboard: https://huggingface.co/spaces/mteb/leaderboard
- Cohere Rerank overview: https://docs.cohere.com/docs/rerank-overview
- Reciprocal Rank Fusion (formula, rank_constant default): https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion
- Ragas metrics: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/
- OWASP Top 10 for LLM Applications (LLM08): https://genai.owasp.org/llm-top-10/
