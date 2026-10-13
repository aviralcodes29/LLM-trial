# DocChat AI — Phase 5 Evaluation Report

## 1. Executive Summary

- **Evaluation Dataset**: 15 test cases (10 answerable, 5 unanswerable)
- **Chunk Configuration**: Size `1200` chars, Overlap `200` chars (`5` total chunks indexed)
- **Retrieval Top-K**: `8`
- **Composite Quality Score**: **`100.0%`**

| Metric | Score | Target | Status |
| :--- | :---: | :---: | :---: |
| **Retrieval Hit Rate** | `100.0%` | ≥ 90% | ✅ Pass |
| **Keyword Match Accuracy** | `100.0%` | ≥ 80% | ✅ Pass |
| **LLM-as-Judge Score** | `5.0 / 5.0` | ≥ 4.0 | ✅ Pass |
| **Refusal Precision (Unanswerable)** | `100.0%` | 100% | ✅ Pass |

## 2. Granular Test Case Breakdown

| # | Type | Category | Question | Retrieval | KW Match | Judge | Refusal |
| :-: | :-: | :--- | :--- | :-: | :-: | :-: | :-: |
| 1 | Answerable | Document Loader | What library does DocumentLoader use to extract text from PDF files? | ✅ Hit | 100% | 5.0/5 | ✅ Correct |
| 2 | Answerable | Validation | What is the maximum allowed file upload size for documents? | ✅ Hit | 100% | 5.0/5 | ✅ Correct |
| 3 | Answerable | Chunking | What chunk size and overlap does the TextChunker use by default? | ✅ Hit | 100% | 5.0/5 | ✅ Correct |
| 4 | Answerable | Chunking | How does the TextChunker prevent semantic cliff effects when splitting text? | ✅ Hit | 100% | 5.0/5 | ✅ Correct |
| 5 | Answerable | Embeddings | What embedding model and batch size does the GeminiEmbedder use? | ✅ Hit | 100% | 5.0/5 | ✅ Correct |
| 6 | Answerable | Vector Storage | Which vector database and distance metric are used for persistent chunk storage? | ✅ Hit | 100% | 5.0/5 | ✅ Correct |
| 7 | Answerable | Vector Storage | What three core methods does the ChromaVectorStore interface expose? | ✅ Hit | 100% | 5.0/5 | ✅ Correct |
| 8 | Answerable | Retrieval & Grounding | What relevance score threshold is required before retrieved chunks are sent to the LLM? | ✅ Hit | 100% | 5.0/5 | ✅ Correct |
| 9 | Answerable | Retrieval & Grounding | What exact fallback message is returned when retrieved context is insufficient? | ✅ Hit | 100% | 5.0/5 | ✅ Correct |
| 10 | Answerable | Memory & Streaming | How many messages does the conversation memory retain per session? | ✅ Hit | 100% | 5.0/5 | ✅ Correct |
| 11 | Unanswerable | Unanswerable / Out of Domain | What is the monthly subscription price for the DocChat AI enterprise plan? | ❌ Miss | 100% | 5.0/5 | ✅ Correct |
| 12 | Unanswerable | Unanswerable / Out of Domain | What is the capital city of Australia? | ❌ Miss | 100% | 5.0/5 | ✅ Correct |
| 13 | Unanswerable | Unanswerable / Out of Domain | How does DocChat AI integrate with Slack and Microsoft Teams? | ❌ Miss | 100% | 5.0/5 | ✅ Correct |
| 14 | Unanswerable | Unanswerable / Out of Domain | What weather forecast is expected in Tokyo next week? | ❌ Miss | 100% | 5.0/5 | ✅ Correct |
| 15 | Unanswerable | Unanswerable / Out of Domain | What programming language is used to train the underlying Gemini foundational model? | ❌ Miss | 100% | 5.0/5 | ✅ Correct |

## 3. Evaluation Criteria

1. **Retrieval Hit**: Evaluates whether the passage containing the ground-truth information (verified by source page number) was retrieved in the top-K ChromaDB candidates.
2. **Answer Correctness**: Evaluates presence of mandatory technical keywords and awards a 1-5 groundedness score based on strict citations and absence of hallucinations.
3. **Refusal Precision**: Verifies that queries with no grounding in the documents are strictly declined with the standard fallback message.


## 4. Configuration Comparison Matrix (Chunk Size 500/800/1200 & Top-K 3/5/8)

A full grid search of 9 configurations was evaluated to identify the optimal balance between retrieval recall, grounding precision, and prompt token efficiency:

| Rank | Chunk Size | Overlap | Top-K | Chunks | Retrieval Hit | KW Accuracy | LLM Judge | Refusal | Composite Score | Note |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| 1 | `800` | `150` | `3` | `8` | 100.0% | 100.0% | 5.0/5.0 | 100.0% | **100.0%** | **★ Winner** |
| 2 | `1200` | `200` | `3` | `5` | 100.0% | 100.0% | 5.0/5.0 | 100.0% | **100.0%** |  |
| 3 | `800` | `150` | `5` | `8` | 100.0% | 100.0% | 5.0/5.0 | 100.0% | **100.0%** | Baseline |
| 4 | `1200` | `200` | `5` | `5` | 100.0% | 100.0% | 5.0/5.0 | 100.0% | **100.0%** |  |
| 5 | `800` | `150` | `8` | `8` | 100.0% | 100.0% | 5.0/5.0 | 100.0% | **100.0%** |  |
| 6 | `1200` | `200` | `8` | `5` | 100.0% | 100.0% | 5.0/5.0 | 100.0% | **100.0%** |  |
| 7 | `500` | `100` | `3` | `12` | 100.0% | 90.0% | 4.8/5.0 | 100.0% | **96.2%** |  |
| 8 | `500` | `100` | `5` | `12` | 100.0% | 90.0% | 4.8/5.0 | 100.0% | **96.2%** |  |
| 9 | `500` | `100` | `8` | `12` | 100.0% | 90.0% | 4.8/5.0 | 100.0% | **96.2%** |  |

### Before vs. After Optimization Summary

- **Baseline Configuration**: Chunk Size `800` / Overlap `150` / Top-K `5`
  - Baseline Retrieval Hit: `100.0%`
  - Baseline Keyword Match: `100.0%`
  - Baseline Judge Score: `5.0 / 5.0`
  - Baseline Composite Score: `100.0%`

- **Best Configuration Selected**: Chunk Size `800` / Overlap `150` / Top-K `3`
  - Optimized Retrieval Hit: `100.0%`
  - Optimized Keyword Match: `100.0%`
  - Optimized Judge Score: `5.0 / 5.0`
  - Optimized Composite Score: `100.0%`

> **Decision Rationale**: Chunk size `800` with overlap `150` and Top-K `3` maximizes semantic recall while minimizing prompt token overhead and retrieval latency.
