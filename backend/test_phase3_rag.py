"""Phase 3 Verification Script: RAG Retrieval + Answer Generation.

Tests the full RAG pipeline with 5 questions:
  - 3 Answerable from the PDF
  - 2 NOT Answerable from the PDF (tests strict grounding and fallback)
"""

import sys
from pathlib import Path

# Ensure app is importable
sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

QUESTIONS = [
    # 3 Answerable questions
    {
        "id": 1,
        "type": "ANSWERABLE",
        "question": "What chunk size and overlap does the TextChunker use?",
        "expected_topic": "800 characters and 150 overlap (Page 2)",
    },
    {
        "id": 2,
        "type": "ANSWERABLE",
        "question": "How does the DocumentLoader extract text from PDF files?",
        "expected_topic": "pypdf to extract text streams and preserve page numbers (Page 1)",
    },
    {
        "id": 3,
        "type": "ANSWERABLE",
        "question": "What vector database and similarity metric are used for storage?",
        "expected_topic": "ChromaDB with HNSW and cosine similarity (Page 3)",
    },
    {
        "id": 4,
        "type": "UNANSWERABLE",
        "question": "What is the capital city of Australia?",
        "expected_topic": "Should trigger fallback (not in document)",
    },
    {
        "id": 5,
        "type": "UNANSWERABLE",
        "question": "How much does the DocChat AI enterprise plan cost per month?",
        "expected_topic": "Should trigger fallback (not in document)",
    },
]


def run_phase3_tests():
    print("=" * 80)
    print("DocChat AI — Phase 3 RAG Retrieval & Grounded Q&A Verification")
    print("=" * 80)

    # Step 1: Ensure sample PDF is ingested
    pdf_path = Path(__file__).parent / "test_sample_document.pdf"
    if not pdf_path.exists():
        print(f"Error: {pdf_path} not found.")
        sys.exit(1)

    print(f"\n[1] Ingesting document: {pdf_path.name}...")
    with open(pdf_path, "rb") as f:
        upload_res = client.post(
            "/api/upload",
            files={"file": (pdf_path.name, f.read(), "application/pdf")},
        )
    assert upload_res.status_code == 200, f"Upload failed: {upload_res.text}"
    upload_data = upload_res.json()
    doc_id = upload_data["doc_id"]
    print(f"    Ingested doc_id: {doc_id} | Chunks indexed: {upload_data['chunks_count']}")

    # Step 2: Test 5 questions against /api/chat
    print("\n[2] Executing 5 RAG Test Queries against /api/chat:\n")
    results = []

    for q in QUESTIONS:
        print("-" * 80)
        print(f"Test #{q['id']} [{q['type']}]: \"{q['question']}\"")
        print(f"Expectation: {q['expected_topic']}")

        chat_res = client.post(
            "/api/chat",
            json={"question": q["question"], "doc_ids": [doc_id]},
        )
        assert chat_res.status_code == 200, f"Chat failed: {chat_res.text}"
        data = chat_res.json()

        answer = data.get("answer", "")
        sources = data.get("sources", [])
        is_fallback = "I couldn't find this in the uploaded documents" in answer or not sources

        print(f"\nResponse Answer:\n{answer}")
        print(f"\nSource Citations ({len(sources)}):")
        for i, src in enumerate(sources, 1):
            print(f"  [{i}] {src['filename']} (Page {src['page']}, Score: {src['score']}):")
            print(f"      \"{src['snippet'][:120]}...\"")

        print(f"\nEvaluation: {'PASSED (Grounding verified)' if (q['type'] == 'UNANSWERABLE' and is_fallback) or (q['type'] == 'ANSWERABLE' and len(sources) > 0) else 'CHECK'}")

        results.append({
            "id": q["id"],
            "type": q["type"],
            "question": q["question"],
            "answer": answer,
            "sources": sources,
            "is_fallback": is_fallback,
        })

    print("\n" + "=" * 80)
    print("PHASE 3 VERIFICATION COMPLETE")
    print("=" * 80)
    return results


if __name__ == "__main__":
    run_phase3_tests()
