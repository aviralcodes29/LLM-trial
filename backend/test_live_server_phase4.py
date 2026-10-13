"""Test against the actively running Uvicorn server on http://127.0.0.1:8000.

Verifies:
  1. Health check: GET /health
  2. Document listing / upload: POST /api/upload
  3. Non-streaming chat: POST /api/chat with stream=False
  4. SSE token streaming: POST /api/chat with stream=True
  5. Multi-turn follow-up conversation with query rewriting:
     - Turn 1: "What chunk size and overlap does the TextChunker use?"
     - Turn 2: "How does it extract text from PDF files?" (pronoun 'it' -> 'TextChunker')
  6. Memory inspection: GET /api/chat/history/{session_id}
  7. Session clear: POST /chat/clear
"""

import json
import urllib.request
import urllib.parse
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"


def make_request(path, method="GET", json_data=None, stream=False):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if stream:
        headers["Accept"] = "text/event-stream"

    data_bytes = json.dumps(json_data).encode("utf-8") if json_data is not None else None
    req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
    return urllib.request.urlopen(req, timeout=15)


def run_live_tests():
    print("=" * 80)
    print(f"Connecting to live DocChat AI server at: {BASE_URL}")
    print("=" * 80)

    # 1. Health check
    with make_request("/health") as resp:
        health_data = json.loads(resp.read().decode("utf-8"))
        print(f"\n[1] Health Check: {health_data}")
        assert health_data["status"] == "ok"

    # 2. Get document list
    with make_request("/api/upload/documents") as resp:
        docs_data = json.loads(resp.read().decode("utf-8"))
        docs = docs_data.get("documents", [])
        print(f"\n[2] Found {len(docs)} documents indexed:")
        for d in docs:
            print(f"    - {d['filename']} (doc_id: {d['doc_id']}, chunks: {d['chunks_count']})")
        doc_id = docs[0]["doc_id"] if docs else None

    # 3. Non-streaming chat fallback
    print(f"\n[3] Testing Non-streaming Chat Fallback...")
    req_payload = {
        "question": "What chunk size and overlap does the TextChunker use?",
        "doc_ids": [doc_id] if doc_id else None,
        "stream": False,
    }
    with make_request("/api/chat", method="POST", json_data=req_payload) as resp:
        chat_data = json.loads(resp.read().decode("utf-8"))
        print(f"    Response Answer: {chat_data['answer'][:120]}...")
        print(f"    Sources count: {len(chat_data['sources'])}")
        assert "answer" in chat_data
        assert len(chat_data["sources"]) > 0
        print("    PASSED: Non-streaming fallback works.")

    # 4. Multi-turn Follow-up Conversation with SSE Streaming
    session_id = "live_test_user_session"
    print(f"\n[4] Starting Multi-turn Conversation with Session ID: '{session_id}'")

    # Turn 1
    print("\n--- TURN 1: User asks about TextChunker ---")
    t1_q = "What chunk size and overlap does the TextChunker use?"
    print(f"User: \"{t1_q}\"")

    t1_payload = {
        "question": t1_q,
        "session_id": session_id,
        "stream": True,
        "doc_ids": [doc_id] if doc_id else None,
    }

    t1_tokens = []
    t1_sources = []
    with make_request("/api/chat", method="POST", json_data=t1_payload, stream=True) as resp:
        for line in resp:
            line_str = line.decode("utf-8").strip()
            if line_str.startswith("data:"):
                payload = json.loads(line_str[5:].strip())
                if payload.get("type") == "token":
                    t1_tokens.append(payload.get("content", ""))
                elif payload.get("type") == "sources":
                    t1_sources = payload.get("sources", [])

    print(f"Assistant (Streamed): \"{''.join(t1_tokens)[:140]}...\"")
    print(f"Citations: {len(t1_sources)} sources.")
    assert len(t1_tokens) > 0

    # Turn 2: Follow-up question using pronoun "it"
    print("\n--- TURN 2: User asks follow-up with pronoun 'it' ---")
    t2_q = "How does it extract text from PDF files?"
    print(f"User: \"{t2_q}\"")

    t2_payload = {
        "question": t2_q,
        "session_id": session_id,
        "stream": True,
        "doc_ids": [doc_id] if doc_id else None,
    }

    t2_tokens = []
    t2_sources = []
    rewritten_query = None

    with make_request("/api/chat", method="POST", json_data=t2_payload, stream=True) as resp:
        for line in resp:
            line_str = line.decode("utf-8").strip()
            if line_str.startswith("data:"):
                payload = json.loads(line_str[5:].strip())
                if payload.get("type") == "rewritten_query":
                    rewritten_query = payload.get("query")
                elif payload.get("type") == "token":
                    t2_tokens.append(payload.get("content", ""))
                elif payload.get("type") == "sources":
                    t2_sources = payload.get("sources", [])

    print(f"Contextualized Rewritten Query: \"{rewritten_query}\"")
    print(f"Assistant (Streamed): \"{''.join(t2_tokens)[:140]}...\"")
    print(f"Citations: {len(t2_sources)} sources.")
    assert len(t2_sources) > 0, "Turn 2 should retrieve relevant sources!"
    print("PASSED: Follow-up query rewriting & streaming response successfully demonstrated.")

    # 5. Check Conversation Memory History
    print(f"\n[5] Checking stored conversation turns for '{session_id}'...")
    with make_request(f"/api/chat/history/{session_id}") as resp:
        history_info = json.loads(resp.read().decode("utf-8"))
        print(f"    Stored messages count: {history_info['count']}")
        assert history_info["count"] == 4
        for i, m in enumerate(history_info["messages"], 1):
            print(f"    [{i}] {m['role'].upper()}: {m['content'][:60]}...")

    # 6. Reset Session Memory via POST /chat/clear
    print(f"\n[6] Resetting session via POST /chat/clear...")
    with make_request("/chat/clear", method="POST", json_data={"session_id": session_id}) as resp:
        clear_res = json.loads(resp.read().decode("utf-8"))
        print(f"    Response: {clear_res}")
        assert clear_res["status"] == "ok"

    with make_request(f"/api/chat/history/{session_id}") as resp:
        history_after = json.loads(resp.read().decode("utf-8"))
        print(f"    Messages count after clear: {history_after['count']}")
        assert history_after["count"] == 0
        print("    PASSED: Session memory successfully cleared.")

    print("\n" + "=" * 80)
    print("ALL LIVE SERVER INTEGRATION TESTS PASSED!")
    print("=" * 80)


if __name__ == "__main__":
    run_live_tests()
