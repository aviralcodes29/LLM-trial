"""Token usage tracking and cost estimation service.

All database access uses raw psycopg2 SQL queries (no ORM).
"""

import logging
from typing import Optional, Dict, Any

from app.config import settings

logger = logging.getLogger(__name__)


def estimate_token_count(text: str) -> int:
    """Heuristic token counter: ~1 token per 4 English characters."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def calculate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate estimated cost in USD based on configured token rates."""
    input_cost = (prompt_tokens / 1_000_000.0) * settings.INPUT_COST_PER_MILLION_TOKENS
    output_cost = (completion_tokens / 1_000_000.0) * settings.OUTPUT_COST_PER_MILLION_TOKENS
    return round(input_cost + output_cost, 6)


def record_usage(
    conn: Any,
    user_id: Optional[int],
    endpoint: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> dict:
    """Insert a usage record row and return it as a dict."""
    total_tokens = prompt_tokens + completion_tokens
    cost = calculate_cost(prompt_tokens, completion_tokens)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO usage_records
                (user_id, endpoint, model, prompt_tokens, completion_tokens, total_tokens, estimated_cost)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id, user_id, endpoint, model,
                      prompt_tokens, completion_tokens, total_tokens, estimated_cost, timestamp
            """,
            (user_id, endpoint, model, prompt_tokens, completion_tokens, total_tokens, cost),
        )
        record = cur.fetchone()
    conn.commit()

    logger.debug(
        f"[Usage] Logged {total_tokens} tokens (${cost:.6f}) for user {user_id} on {endpoint}"
    )
    return dict(record)


def get_usage_summary(conn: Any, user_id: Optional[int] = None) -> Dict[str, Any]:
    """Retrieve aggregated usage metrics and 20 most recent records for a user."""
    where_clause = "WHERE user_id = %s" if user_id is not None else ""
    params = (user_id,) if user_id is not None else ()

    with conn.cursor() as cur:
        # Totals
        cur.execute(
            f"""
            SELECT
                COUNT(*)                                AS total_requests,
                COALESCE(SUM(prompt_tokens), 0)        AS prompt_tokens,
                COALESCE(SUM(completion_tokens), 0)    AS completion_tokens,
                COALESCE(SUM(total_tokens), 0)         AS total_tokens,
                COALESCE(SUM(estimated_cost), 0.0)     AS estimated_cost
            FROM usage_records
            {where_clause}
            """,
            params,
        )
        sums = cur.fetchone()

        # Recent records
        cur.execute(
            f"""
            SELECT id, endpoint, model, prompt_tokens, completion_tokens,
                   total_tokens, estimated_cost, timestamp
            FROM usage_records
            {where_clause}
            ORDER BY timestamp DESC
            LIMIT 20
            """,
            params,
        )
        recent = cur.fetchall()

    return {
        "user_id": user_id,
        "total_requests": int(sums["total_requests"]) if sums else 0,
        "prompt_tokens": int(sums["prompt_tokens"]) if sums else 0,
        "completion_tokens": int(sums["completion_tokens"]) if sums else 0,
        "total_tokens": int(sums["total_tokens"]) if sums else 0,
        "estimated_cost_usd": round(float(sums["estimated_cost"]), 6) if sums else 0.0,
        "recent_records": [
            {
                "id": r["id"],
                "endpoint": r["endpoint"],
                "model": r["model"],
                "prompt_tokens": r["prompt_tokens"],
                "completion_tokens": r["completion_tokens"],
                "total_tokens": r["total_tokens"],
                "estimated_cost": round(float(r["estimated_cost"]), 6),
                "timestamp": r["timestamp"].isoformat() if r["timestamp"] else None,
            }
            for r in recent
        ],
    }
