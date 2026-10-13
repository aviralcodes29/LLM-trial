"""DocChat AI — Phase 5: RAG Evaluation Framework.

Evaluates the end-to-end RAG pipeline against 15 test cases in eval/questions.json:
  1. Retrieval Hit Rate (was the expected page/chunk retrieved?)
  2. Answer Correctness (keyword match ratio + LLM-as-judge score 1-5)
  3. Correct Refusal Rate on unanswerable questions
Outputs a formatted results table in terminal and saves results to eval/results.md.
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.services.loader import DocumentLoader
from app.services.chunker import TextChunker
from app.services.embedder import GeminiEmbedder
from app.services.vectorstore import ChromaVectorStore
from app.services.llm import GeminiLLM, FALLBACK_MESSAGE
from app.config import settings

logger = logging.getLogger(__name__)


def is_system_refusal(answer: str) -> bool:
    """Return True only if the response is an actual refusal rather than discussing the fallback message."""
    trimmed = answer.strip().lower()
    if trimmed == FALLBACK_MESSAGE.lower():
        return True
    if trimmed.startswith(FALLBACK_MESSAGE.lower()):
        return True
    if "couldn't find this in the uploaded documents" in trimmed and "according to" not in trimmed and "fallback message" not in trimmed:
        return True
    return False


def evaluate_llm_judge(
    question: str,
    answer: str,
    expected_keywords: List[str],
    answerable: bool,
    llm: GeminiLLM,
) -> float:
    """Score the answer from 1 to 5 using LLM-as-a-judge or deterministic rubric."""
    answer_lower = (
        answer.lower()
        .replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
    )
    is_refusal = is_system_refusal(answer)

    # 1. Unanswerable question grading
    if not answerable:
        if is_refusal:
            return 5.0  # Perfect refusal
        else:
            return 1.0  # Hallucinated answer on unanswerable prompt

    # 2. Answerable question: if model refused inappropriately
    if is_refusal:
        return 1.0

    # 3. If Gemini is configured, use LLM-as-a-judge prompt
    if llm._is_configured:
        judge_prompt = (
            "You are an impartial evaluator grading a RAG answer for factual accuracy and grounding.\n"
            "Evaluate the candidate answer against the user question and key expected topics on a 1-5 scale:\n"
            "  5: Fully correct, thorough, grounded in facts, contains all key keywords.\n"
            "  4: Mostly correct with minor omissions.\n"
            "  3: Partially correct, misses key details.\n"
            "  2: Poorly grounded, inaccurate, or vague.\n"
            "  1: Completely incorrect or irrecoverable.\n\n"
            f"Question: {question}\n"
            f"Expected Keywords/Topic: {', '.join(expected_keywords)}\n"
            f"Candidate Answer: {answer}\n\n"
            "Reply strictly with a single JSON object: {\"score\": <1-5 integer>, \"reason\": \"<short sentence>\"}"
        )
        try:
            import google.generativeai as genai
            model = genai.GenerativeModel(model_name=llm.model_name)
            res = model.generate_content(judge_prompt)
            if res and res.text:
                cleaned = res.text.strip().replace("```json", "").replace("```", "").strip()
                data = json.loads(cleaned)
                score = float(data.get("score", 3.0))
                return max(1.0, min(5.0, score))
        except Exception as e:
            logger.debug(f"LLM-as-judge API call failed: {e}. Using deterministic rubric.")

    # 4. Deterministic heuristic rubric
    matched = [kw for kw in expected_keywords if kw.lower() in answer_lower]
    ratio = len(matched) / len(expected_keywords) if expected_keywords else 0.0

    has_citation = "[" in answer and "]" in answer
    if ratio >= 0.9 and has_citation:
        return 5.0
    elif ratio >= 0.6:
        return 4.0 if has_citation else 3.5
    elif ratio >= 0.3:
        return 3.0
    else:
        return 2.0


def run_evaluation(
    doc_path: Optional[Path] = None,
    questions_path: Optional[Path] = None,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
    top_k: Optional[int] = None,
    output_md_path: Optional[Path] = None,
    quiet: bool = False,
) -> Dict[str, Any]:
    """Execute the full evaluation suite and return scored metrics."""
    eval_dir = Path(__file__).resolve().parent
    doc_path = doc_path or (eval_dir / "sample_docs" / "sample_document.pdf")
    questions_path = questions_path or (eval_dir / "questions.json")
    output_md_path = output_md_path or (eval_dir / "results.md")

    chunk_size = chunk_size or getattr(settings, "CHUNK_SIZE", 800)
    chunk_overlap = chunk_overlap or getattr(settings, "CHUNK_OVERLAP", 150)
    top_k = top_k or getattr(settings, "RETRIEVAL_TOP_K", 3)

    if not doc_path.exists():
        raise FileNotFoundError(f"Evaluation document missing at {doc_path}")
    if not questions_path.exists():
        raise FileNotFoundError(f"Evaluation questions missing at {questions_path}")

    # ── 1. Load questions ──────────────────────────────────────────────────
    with open(questions_path, "r", encoding="utf-8") as f:
        questions: List[Dict[str, Any]] = json.load(f)

    # ── 2. Ingest document with specified chunking config ──────────────────
    loader = DocumentLoader()
    pages = loader.load_path(doc_path)
    chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = chunker.split_pages(pages, doc_id="eval_doc_001")

    embedder = GeminiEmbedder(api_key=settings.GEMINI_API_KEY)
    texts = [c["text"] for c in chunks]
    embeddings = embedder.embed_documents(texts)

    eval_chroma_dir = eval_dir / "eval_chroma_db"
    vectorstore = ChromaVectorStore(
        persist_directory=str(eval_chroma_dir),
        collection_name=f"eval_col_cs{chunk_size}_ov{chunk_overlap}",
    )
    # Clear collection if already populated
    try:
        vectorstore.collection.delete(where={"doc_id": "eval_doc_001"})
    except Exception:
        pass
    vectorstore.add_chunks(chunks, embeddings)

    llm = GeminiLLM(
        api_key=settings.GEMINI_API_KEY,
        model_name=settings.GEMINI_MODEL,
        relevance_threshold=settings.RELEVANCE_THRESHOLD,
    )

    # ── 3. Run evaluation per question ────────────────────────────────────
    results = []
    answerable_count = sum(1 for q in questions if q.get("answerable", True))
    unanswerable_count = len(questions) - answerable_count

    retrieval_hits = 0
    keyword_scores = []
    judge_scores = []
    correct_refusals = 0

    for q in questions:
        q_id = q["id"]
        question_text = q["question"]
        expected_keywords = q.get("expected_answer_keywords", [])
        expected_page = q.get("expected_page")
        is_answerable = q.get("answerable", True)

        # Retrieval step
        query_emb = embedder.embed_query(question_text)
        retrieved_chunks = vectorstore.search(query_emb, top_k=top_k)

        # a) Retrieval Hit scoring
        if is_answerable:
            # Check if expected page is among retrieved chunks
            retrieved_pages = [c.get("page") for c in retrieved_chunks if c.get("page") is not None]
            hit = (expected_page in retrieved_pages) if expected_page else len(retrieved_chunks) > 0
            if hit:
                retrieval_hits += 1
        else:
            # For unanswerables, retrieval hit is N/A (or True if none passed threshold)
            filtered = llm.filter_chunks(retrieved_chunks)
            hit = (len(filtered) == 0)

        # b) Answer Generation step
        llm_output = llm.generate_grounded_answer(question_text, retrieved_chunks)
        answer = llm_output["answer"]

        # c) Answer Correctness (Keywords)
        # Normalize curly apostrophes and quotes for robust comparison
        norm_answer = (
            answer.lower()
            .replace("’", "'")
            .replace("‘", "'")
            .replace("“", '"')
            .replace("”", '"')
        )
        if is_answerable:
            matched_kws = [
                kw for kw in expected_keywords
                if kw.lower().replace("’", "'").replace("‘", "'") in norm_answer
            ]
            kw_match_ratio = len(matched_kws) / len(expected_keywords) if expected_keywords else 1.0
            keyword_scores.append(kw_match_ratio)
        else:
            kw_match_ratio = 1.0 if "couldn't find" in norm_answer else 0.0

        # d) LLM-as-Judge Score (1-5)
        judge_score = evaluate_llm_judge(question_text, answer, expected_keywords, is_answerable, llm)
        judge_scores.append(judge_score)

        # e) Correct Refusal on unanswerable
        is_refusal = is_system_refusal(answer)
        if not is_answerable:
            if is_refusal:
                correct_refusals += 1
            refusal_correct = is_refusal
        else:
            refusal_correct = not is_refusal

        results.append({
            "id": q_id,
            "category": q.get("category", "General"),
            "question": question_text,
            "answerable": is_answerable,
            "expected_page": expected_page,
            "retrieval_hit": hit,
            "keyword_match_ratio": kw_match_ratio,
            "judge_score": judge_score,
            "refusal_correct": refusal_correct,
            "answer_preview": answer[:120].replace("\n", " "),
        })

    # ── 4. Aggregate metrics ──────────────────────────────────────────────
    hit_rate = (retrieval_hits / answerable_count) * 100 if answerable_count else 100.0
    kw_accuracy = (sum(keyword_scores) / len(keyword_scores)) * 100 if keyword_scores else 0.0
    avg_judge = sum(judge_scores) / len(judge_scores) if judge_scores else 0.0
    refusal_rate = (correct_refusals / unanswerable_count) * 100 if unanswerable_count else 100.0

    # Composite score [0 - 100%]
    composite_score = (
        (0.35 * hit_rate)
        + (0.30 * kw_accuracy)
        + (0.20 * (avg_judge / 5.0 * 100.0))
        + (0.15 * refusal_rate)
    )

    metrics = {
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "top_k": top_k,
        "total_chunks": len(chunks),
        "total_questions": len(questions),
        "answerable_questions": answerable_count,
        "unanswerable_questions": unanswerable_count,
        "retrieval_hit_rate": round(hit_rate, 2),
        "keyword_accuracy": round(kw_accuracy, 2),
        "avg_judge_score": round(avg_judge, 2),
        "refusal_rate": round(refusal_rate, 2),
        "composite_score": round(composite_score, 2),
        "results": results,
    }

    # ── 5. Render Terminal Table ──────────────────────────────────────────
    if not quiet:
        _print_terminal_results(metrics)

    # ── 6. Write Markdown Report ──────────────────────────────────────────
    _write_markdown_report(metrics, output_md_path)

    return metrics


def _print_terminal_results(metrics: Dict[str, Any]):
    """Print a clean formatted results table in terminal."""
    print("=" * 100)
    print("DocChat AI — Phase 5 RAG Evaluation Results")
    print(
        f"Config: chunk_size={metrics['chunk_size']} | overlap={metrics['chunk_overlap']} | "
        f"top_k={metrics['top_k']} | indexed_chunks={metrics['total_chunks']}"
    )
    print("=" * 100)
    print(
        f"{'ID':<3} | {'Type':<6} | {'Retrieval':<9} | {'KW Match':<8} | {'Judge (1-5)':<11} | {'Refusal':<7} | {'Question (truncated)':<42}"
    )
    print("-" * 100)

    for r in metrics["results"]:
        q_type = "ANS" if r["answerable"] else "UNANS"
        ret_str = "HIT [✓]" if r["retrieval_hit"] else "MISS [✗]"
        kw_str = f"{int(r['keyword_match_ratio'] * 100)}%"
        judge_str = f"{r['judge_score']:.1f} / 5"
        ref_str = "CORRECT" if r["refusal_correct"] else "FAIL"
        q_text = r["question"][:40] + ("…" if len(r["question"]) > 40 else "")

        print(
            f"{r['id']:<3} | {q_type:<6} | {ret_str:<9} | {kw_str:<8} | {judge_str:<11} | {ref_str:<7} | {q_text:<42}"
        )

    print("-" * 100)
    print("SUMMARY METRICS:")
    print(f"  • Retrieval Hit Rate (Answerable) : {metrics['retrieval_hit_rate']}%")
    print(f"  • Keyword Match Accuracy          : {metrics['keyword_accuracy']}%")
    print(f"  • Average LLM-as-Judge Score       : {metrics['avg_judge_score']} / 5.0")
    print(f"  • Correct Refusal Rate (Unanswer)  : {metrics['refusal_rate']}%")
    print(f"  • OVERALL COMPOSITE SCORE          : {metrics['composite_score']}%")
    print("=" * 100)


def _write_markdown_report(metrics: Dict[str, Any], output_path: Path):
    """Write formatted evaluation results to results.md."""
    lines = [
        "# DocChat AI — Phase 5 Evaluation Report",
        "",
        "## 1. Executive Summary",
        "",
        f"- **Evaluation Dataset**: 15 test cases ({metrics['answerable_questions']} answerable, {metrics['unanswerable_questions']} unanswerable)",
        f"- **Chunk Configuration**: Size `{metrics['chunk_size']}` chars, Overlap `{metrics['chunk_overlap']}` chars (`{metrics['total_chunks']}` total chunks indexed)",
        f"- **Retrieval Top-K**: `{metrics['top_k']}`",
        f"- **Composite Quality Score**: **`{metrics['composite_score']}%`**",
        "",
        "| Metric | Score | Target | Status |",
        "| :--- | :---: | :---: | :---: |",
        f"| **Retrieval Hit Rate** | `{metrics['retrieval_hit_rate']}%` | ≥ 90% | {'✅ Pass' if metrics['retrieval_hit_rate'] >= 90 else '⚠️ Review'} |",
        f"| **Keyword Match Accuracy** | `{metrics['keyword_accuracy']}%` | ≥ 80% | {'✅ Pass' if metrics['keyword_accuracy'] >= 80 else '⚠️ Review'} |",
        f"| **LLM-as-Judge Score** | `{metrics['avg_judge_score']} / 5.0` | ≥ 4.0 | {'✅ Pass' if metrics['avg_judge_score'] >= 4.0 else '⚠️ Review'} |",
        f"| **Refusal Precision (Unanswerable)** | `{metrics['refusal_rate']}%` | 100% | {'✅ Pass' if metrics['refusal_rate'] == 100 else '⚠️ Review'} |",
        "",
        "## 2. Granular Test Case Breakdown",
        "",
        "| # | Type | Category | Question | Retrieval | KW Match | Judge | Refusal |",
        "| :-: | :-: | :--- | :--- | :-: | :-: | :-: | :-: |",
    ]

    for r in metrics["results"]:
        q_type = "Answerable" if r["answerable"] else "Unanswerable"
        ret_icon = "✅ Hit" if r["retrieval_hit"] else "❌ Miss"
        kw_fmt = f"{int(r['keyword_match_ratio'] * 100)}%"
        judge_fmt = f"{r['judge_score']:.1f}/5"
        ref_icon = "✅ Correct" if r["refusal_correct"] else "❌ Failed"
        lines.append(
            f"| {r['id']} | {q_type} | {r['category']} | {r['question']} | {ret_icon} | {kw_fmt} | {judge_fmt} | {ref_icon} |"
        )

    lines.extend([
        "",
        "## 3. Evaluation Criteria",
        "",
        "1. **Retrieval Hit**: Evaluates whether the passage containing the ground-truth information (verified by source page number) was retrieved in the top-K ChromaDB candidates.",
        "2. **Answer Correctness**: Evaluates presence of mandatory technical keywords and awards a 1-5 groundedness score based on strict citations and absence of hallucinations.",
        "3. **Refusal Precision**: Verifies that queries with no grounding in the documents are strictly declined with the standard fallback message.",
        "",
    ])

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[Saved] Detailed evaluation results saved to: {output_path}")


if __name__ == "__main__":
    run_evaluation()
