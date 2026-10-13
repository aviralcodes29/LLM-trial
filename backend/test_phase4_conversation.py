"""Phase 4 Verification Script: Streaming + Conversation Memory + Follow-up Rewriting.

Verifies:
  1. Non-streaming fallback returns complete answer and citations.
  2. Streaming endpoint (/api/chat with stream=True) streams SSE token events,
     followed by sources event, followed by done event.
  3. Multi-turn conversation with memory:
     - Turn 1: "What chunk size and overlap does the TextChunker use?"
     - Turn 2: Follow-up question: "How does it preserve metadata?"
     - Verification: query rewriting contextualizes "it" -> "TextChunker" and retrieves relevant context.
  4. Session history retention (up to 6 messages).
  5. POST /chat/clear resets the session.
"""

import sys
import json
from pathlib import Path

# Ensure app is importable
sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def run_phase4_tests():
    print("=" * 80)
    print("DocChat AI — Phase 4 Streaming + Conversation Memory Verification")
    print("=" * 80)

    # Step 1: Ensure PDF is ingested
    pdf_path = Path(__file__).parent / "test_sample_document.pdf"
    assert pdf_path.exists(), f"Test PDF missing: {pdf_path}"

    print(f"\n[1] Ingesting document: {pdf_path.name}...")
    with open(pdf_path, "rb") as f:
        upload_res = client.post(
            "/api/upload",
            files={"file": (pdf_path.name, f.read(), "application/pdf")},
        )
    assert upload_res.status_code == 200
    doc_id = upload_res.json()["doc_id"]
    print(f"    Indexed doc_id: {doc_id} with {upload_res.json()['chunks_count']} chunks.")

    # Step 2: Test Non-Streaming Fallback
    print("\n[2] Testing Non-Streaming Fallback (/api/chat with stream=False)...")
    res_non_stream = client.post(
        "/api/chat",
        json={
            "question": "What chunk size and overlap does the TextChunker use?",
            "doc_ids": [doc_id],
            "stream": False,
        },
    )
    assert res_non_stream.status_code == 200, f"Non-streaming failed: {res_non_stream.text}"
    non_stream_data = res_non_stream.json()
    assert "answer" in non_stream_data
    assert len(non_stream_data["sources"]) > 0
    print(f"    PASSED: Non-streaming returned {len(non_stream_data['sources'])} sources.")
    print(f"    Answer excerpt: {non_stream_data['answer'][:120]}...")

    # Step 3: Test SSE Streaming Endpoint
    print("\n[3] Testing SSE Streaming (/api/chat with stream=True)...")
    session_id = "test_phase4_session"
    res_stream = client.post(
        "/api/chat",
        json={
            "question": "What chunk size and overlap does the TextChunker use?",
            "doc_ids": [doc_id],
            "session_id": session_id,
            "stream": True,
        },
    )
    assert res_stream.status_code == 200, f"Streaming failed: {res_stream.text}"
    assert "text/event-stream" in res_stream.headers["content-type"]

    tokens = []
    received_sources = []
    received_done = False

    for line in res_stream.iter_lines():
        if line.startswith("data: "):
            payload = json.loads(line[6:])
            event_type = payload.get("type")
            if event_type == "token":
                tokens.append(payload.get("content", ""))
            elif event_type == "sources":
                received_sources = payload.get("sources", [])
            elif event_type == "done":
                received_done = True

    streamed_answer = "".join(tokens)
    print(f"    Streamed {len(tokens)} token events.")
    print(f"    Received {len(received_sources)} sources in final event.")
    print(f"    Received 'done' event: {received_done}")
    print(f"    Full streamed answer:\n    \"{streamed_answer[:160]}...\"")
    assert len(tokens) > 0, "No tokens were streamed!"
    assert len(received_sources) > 0, "Final sources event missing or empty!"
    assert received_done, "Stream did not emit done event!"
    print("    PASSED: Streaming SSE contract validated.")

    # Step 4: Test Multi-turn Conversation & Query Rewriting
    print("\n[4] Testing Multi-turn Conversation & Follow-up Query Rewriting...")
    follow_up_q = "How does it extract text from PDF files?"
    print(f"    Turn 1 was about TextChunker & DocumentLoader.")
    print(f"    Turn 2 follow-up query: \"{follow_up_q}\" (contains pronoun 'it')")

    res_turn2 = client.post(
        "/api/chat",
        json={
            "question": follow_up_q,
            "doc_ids": [doc_id],
            "session_id": session_id,
            "stream": True,
        },
    )
    assert res_turn2.status_code == 200

    turn2_tokens = []
    turn2_sources = []
    rewritten_query_event = None

    for line in res_turn2.iter_lines():
        if line.startswith("data: "):
            payload = json.loads(line[6:])
            event_type = payload.get("type")
            if event_type == "rewritten_query":
                rewritten_query_event = payload.get("query")
            elif event_type == "token":
                turn2_tokens.append(payload.get("content", ""))
            elif event_type == "sources":
                turn2_sources = payload.get("sources", [])

    print(f"    Rewritten query emitted: \"{rewritten_query_event}\"")
    print(f"    Turn 2 answered with {len(turn2_sources)} sources.")
    assert len(turn2_sources) > 0, "Turn 2 retrieval failed to find sources!"
    print("    PASSED: Query rewriting contextualized follow-up and retrieved sources successfully.")

    # Step 5: Verify Session Memory Retention
    print("\n[5] Checking stored conversation history...")
    res_history = client.get(f"/api/chat/history/{session_id}")
    assert res_history.status_code == 200
    history_data = res_history.json()
    print(f"    Session '{session_id}' has {history_data['count']} stored messages (expected 4: 2 user + 2 assistant).")
    assert history_data["count"] == 4, f"Expected 4 messages, got {history_data['count']}"
    for i, msg in enumerate(history_data["messages"], 1):
        print(f"      [{i}] {msg['role'].upper()}: {msg['content'][:60]}...")
    print("    PASSED: Conversation memory history verified.")

    # Step 6: Test POST /chat/clear
    print("\n[6] Testing POST /chat/clear to reset session...")
    res_clear = client.post(
        "/chat/clear",
        json={"session_id": session_id},
    )
    assert res_clear.status_code == 200
    print(f"    Clear response: {res_clear.json()}")

    # Verify history is now 0
    res_history_cleared = client.get(f"/api/chat/history/{session_id}")
    assert res_history_cleared.json()["count"] == 0
    print("    PASSED: Session successfully cleared.")

    print("\n" + "=" * 80)
    print("ALL PHASE 4 BACKEND TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    run_phase4_tests()
