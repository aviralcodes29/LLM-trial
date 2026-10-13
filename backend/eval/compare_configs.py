"""DocChat AI — Phase 5: Grid Search Configuration Comparison.

Compares RAG configurations across chunk sizes (500, 800, 1200) and top_k values (3, 5, 8).
Evaluates retrieval hit rate, keyword accuracy, judge score, and refusal precision.
Ranks all configurations and applies the optimal configuration as the system default.
"""

import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from eval.run_eval import run_evaluation
from app.config import settings

# Grid search parameter space
GRID_CONFIGS = [
    # chunk_size, chunk_overlap, top_k
    (500, 100, 3),
    (500, 100, 5),
    (500, 100, 8),
    (800, 150, 3),
    (800, 150, 5),
    (800, 150, 8),
    (1200, 200, 3),
    (1200, 200, 5),
    (1200, 200, 8),
]


def run_comparison(apply_best: bool = True) -> Dict[str, Any]:
    """Execute grid search across all configurations and rank results."""
    print("=" * 105)
    print("DocChat AI — Phase 5 Grid Search: Configuration Optimization Matrix")
    print(f"Testing {len(GRID_CONFIGS)} parameter combinations across Chunk Size (500/800/1200) & Top-K (3/5/8)...")
    print("=" * 105)

    eval_dir = Path(__file__).resolve().parent
    results_md_path = eval_dir / "results.md"

    evaluated_configs: List[Dict[str, Any]] = []

    for cs, ov, top_k in GRID_CONFIGS:
        print(f"  • Evaluating config: chunk_size={cs:<4} | overlap={ov:<3} | top_k={top_k} ...", end="", flush=True)
        metrics = run_evaluation(
            chunk_size=cs,
            chunk_overlap=ov,
            top_k=top_k,
            quiet=True,
        )
        print(
            f" Hit={metrics['retrieval_hit_rate']}% | KW={metrics['keyword_accuracy']}% | "
            f"Judge={metrics['avg_judge_score']}/5 | Score={metrics['composite_score']}%"
        )
        evaluated_configs.append(metrics)

    # ── Multi-objective ranking ────────────────────────────────────────────
    # Primary: Composite Score (accuracy & grounding)
    # Secondary: Token efficiency (smaller top_k & optimal chunk size reduce latency & LLM prompt tokens)
    def ranking_key(c: Dict[str, Any]):
        # Penalize larger top_k slightly (0.1 pt per k) if composite score is identical, to favor lower latency
        efficiency_bonus = (10 - c["top_k"]) * 0.1
        return (c["composite_score"], efficiency_bonus)

    ranked_configs = sorted(evaluated_configs, key=ranking_key, reverse=True)
    best_config = ranked_configs[0]

    # Baseline config is the default (800 / 150 / 5)
    baseline_config = next(
        (c for c in evaluated_configs if c["chunk_size"] == 800 and c["top_k"] == 5),
        evaluated_configs[0],
    )

    # ── Display comparison table ──────────────────────────────────────────
    _print_comparison_table(ranked_configs, best_config, baseline_config)

    # ── Append comparison table to results.md ─────────────────────────────
    _append_comparison_to_markdown(ranked_configs, best_config, baseline_config, results_md_path)

    # ── Apply best config as default ──────────────────────────────────────
    if apply_best:
        _apply_best_config(best_config)

    return {
        "ranked_configs": ranked_configs,
        "best_config": best_config,
        "baseline_config": baseline_config,
    }


def _print_comparison_table(
    ranked: List[Dict[str, Any]],
    best: Dict[str, Any],
    baseline: Dict[str, Any],
):
    """Print ASCII comparison table in terminal."""
    print("\n" + "=" * 105)
    print("GRID SEARCH CONFIGURATION RANKING RESULTS")
    print("=" * 105)
    print(
        f"{'Rank':<5} | {'Chunk Size':<10} | {'Overlap':<7} | {'Top-K':<5} | {'Chunks':<6} | "
        f"{'Retrieval Hit':<13} | {'KW Match':<8} | {'Judge (1-5)':<11} | {'Refusal':<7} | {'Composite':<9}"
    )
    print("-" * 105)

    for rank, c in enumerate(ranked, start=1):
        is_best = (c == best)
        is_base = (c == baseline)
        flag = " [★ BEST]" if is_best else (" [DEFAULT]" if is_base else "")

        print(
            f"{rank:<5} | {c['chunk_size']:<10} | {c['chunk_overlap']:<7} | {c['top_k']:<5} | {c['total_chunks']:<6} | "
            f"{c['retrieval_hit_rate']:>5.1f}%       | {c['keyword_accuracy']:>5.1f}%  | "
            f"{c['avg_judge_score']:>4.1f} / 5.0   | {c['refusal_rate']:>5.1f}%  | "
            f"{c['composite_score']:>5.1f}%{flag}"
        )

    print("-" * 105)
    print(f"★ OPTIMAL CONFIGURATION SELECTED:")
    print(
        f"  • Chunk Size : {best['chunk_size']} chars\n"
        f"  • Overlap    : {best['chunk_overlap']} chars\n"
        f"  • Top-K      : {best['top_k']} passages\n"
        f"  • Score      : {best['composite_score']}% (Hit={best['retrieval_hit_rate']}%, KW={best['keyword_accuracy']}%, Judge={best['avg_judge_score']}/5)"
    )
    print("=" * 105)


def _append_comparison_to_markdown(
    ranked: List[Dict[str, Any]],
    best: Dict[str, Any],
    baseline: Dict[str, Any],
    output_path: Path,
):
    """Append the grid search comparison matrix to results.md."""
    lines = [
        "",
        "## 4. Configuration Comparison Matrix (Chunk Size 500/800/1200 & Top-K 3/5/8)",
        "",
        "A full grid search of 9 configurations was evaluated to identify the optimal balance between retrieval recall, grounding precision, and prompt token efficiency:",
        "",
        "| Rank | Chunk Size | Overlap | Top-K | Chunks | Retrieval Hit | KW Accuracy | LLM Judge | Refusal | Composite Score | Note |",
        "| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |",
    ]

    for rank, c in enumerate(ranked, start=1):
        note = "**★ Winner**" if c == best else ("Baseline" if c == baseline else "")
        lines.append(
            f"| {rank} | `{c['chunk_size']}` | `{c['chunk_overlap']}` | `{c['top_k']}` | `{c['total_chunks']}` | "
            f"{c['retrieval_hit_rate']}% | {c['keyword_accuracy']}% | {c['avg_judge_score']}/5.0 | "
            f"{c['refusal_rate']}% | **{c['composite_score']}%** | {note} |"
        )

    lines.extend([
        "",
        "### Before vs. After Optimization Summary",
        "",
        f"- **Baseline Configuration**: Chunk Size `{baseline['chunk_size']}` / Overlap `{baseline['chunk_overlap']}` / Top-K `{baseline['top_k']}`",
        f"  - Baseline Retrieval Hit: `{baseline['retrieval_hit_rate']}%`",
        f"  - Baseline Keyword Match: `{baseline['keyword_accuracy']}%`",
        f"  - Baseline Judge Score: `{baseline['avg_judge_score']} / 5.0`",
        f"  - Baseline Composite Score: `{baseline['composite_score']}%`",
        "",
        f"- **Best Configuration Selected**: Chunk Size `{best['chunk_size']}` / Overlap `{best['chunk_overlap']}` / Top-K `{best['top_k']}`",
        f"  - Optimized Retrieval Hit: `{best['retrieval_hit_rate']}%`",
        f"  - Optimized Keyword Match: `{best['keyword_accuracy']}%`",
        f"  - Optimized Judge Score: `{best['avg_judge_score']} / 5.0`",
        f"  - Optimized Composite Score: `{best['composite_score']}%`",
        "",
        f"> **Decision Rationale**: Chunk size `{best['chunk_size']}` with overlap `{best['chunk_overlap']}` and Top-K `{best['top_k']}` maximizes semantic recall while minimizing prompt token overhead and retrieval latency.",
        "",
    ])

    existing_content = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
    # Avoid duplicate sections if re-run
    if "## 4. Configuration Comparison Matrix" in existing_content:
        base_part = existing_content.split("## 4. Configuration Comparison Matrix")[0].strip()
        output_path.write_text(base_part + "\n" + "\n".join(lines), encoding="utf-8")
    else:
        output_path.write_text(existing_content + "\n" + "\n".join(lines), encoding="utf-8")

    print(f"[Updated] Appended comparison matrix to: {output_path}")


def _apply_best_config(best: Dict[str, Any]):
    """Apply the best configuration as the default in config.py and .env."""
    backend_root = Path(__file__).resolve().parent.parent
    config_py_path = backend_root / "app" / "config.py"
    env_path = backend_root / ".env"

    cs = best["chunk_size"]
    ov = best["chunk_overlap"]
    top_k = best["top_k"]

    # 1. Update backend/app/config.py
    if config_py_path.exists():
        content = config_py_path.read_text(encoding="utf-8")
        # Ensure CHUNK_SIZE and CHUNK_OVERLAP exist in Settings
        if "CHUNK_SIZE:" not in content:
            content = content.replace(
                "RETRIEVAL_TOP_K: int = 5",
                f"CHUNK_SIZE: int = {cs}\n    CHUNK_OVERLAP: int = {ov}\n    RETRIEVAL_TOP_K: int = {top_k}",
            )
        else:
            import re
            content = re.sub(r"CHUNK_SIZE:\s*int\s*=\s*\d+", f"CHUNK_SIZE: int = {cs}", content)
            content = re.sub(r"CHUNK_OVERLAP:\s*int\s*=\s*\d+", f"CHUNK_OVERLAP: int = {ov}", content)
            content = re.sub(r"RETRIEVAL_TOP_K:\s*int\s*=\s*\d+", f"RETRIEVAL_TOP_K: int = {top_k}", content)

        config_py_path.write_text(content, encoding="utf-8")
        print(f"[Applied] Updated backend/app/config.py defaults: CHUNK_SIZE={cs}, CHUNK_OVERLAP={ov}, RETRIEVAL_TOP_K={top_k}")

    # 2. Update .env if present
    if env_path.exists():
        env_content = env_path.read_text(encoding="utf-8")
        import re
        if "CHUNK_SIZE=" in env_content:
            env_content = re.sub(r"CHUNK_SIZE=\d+", f"CHUNK_SIZE={cs}", env_content)
        else:
            env_content += f"\nCHUNK_SIZE={cs}"

        if "CHUNK_OVERLAP=" in env_content:
            env_content = re.sub(r"CHUNK_OVERLAP=\d+", f"CHUNK_OVERLAP={ov}", env_content)
        else:
            env_content += f"\nCHUNK_OVERLAP={ov}"

        if "RETRIEVAL_TOP_K=" in env_content:
            env_content = re.sub(r"RETRIEVAL_TOP_K=\d+", f"RETRIEVAL_TOP_K={top_k}", env_content)
        else:
            env_content += f"\nRETRIEVAL_TOP_K={top_k}"

        env_path.write_text(env_content.strip() + "\n", encoding="utf-8")
        print(f"[Applied] Updated backend/.env: CHUNK_SIZE={cs}, CHUNK_OVERLAP={ov}, RETRIEVAL_TOP_K={top_k}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare DocChat AI RAG configurations.")
    parser.add_argument("--apply-best", action="store_true", default=True, help="Set the best configuration as default")
    args = parser.parse_args()
    run_comparison(apply_best=args.apply_best)
