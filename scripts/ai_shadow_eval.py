"""
Measures the AI quiz-question reader (shadow mode, core/ai_question_shadow.py)
against the real course documents in assets/doc-course-test/.

Run from the project root:

    python -m scripts.ai_shadow_eval            # free: lists the quizzes with gaps and estimates the cost
    python -m scripts.ai_shadow_eval --run      # calls the AI for those quizzes (needs .env: see below)
    python -m scripts.ai_shadow_eval --run --all   # also quizzes the parser reads fully (false-positive check)
    python -m scripts.ai_shadow_eval --report   # free: table from the records already in ai_shadow/

--run needs in .env: GEMINI_API_KEY, AI_BUDGET_USD, AI_COST_PER_1M_INPUT_TOKENS_USD,
AI_COST_PER_1M_OUTPUT_TOKENS_USD (AI_QUESTIONS_SHADOW isn't needed here).
A quiz already recorded with the same text isn't sent again.
"""
import argparse
import glob
import json
import logging
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)  # the splitter writes to the relative "workspace/" folder

from config.settings import Config  # noqa: E402
from core import ai_question_shadow as shadow  # noqa: E402

DOCS_DIR = os.path.join(ROOT, "assets", "doc-course-test")
EVAL_COURSE = "_ai_shadow_eval"
# Rough output size per question (stem + options + evidence as JSON).
OUTPUT_TOKENS_PER_QUESTION = 120


def quizzes_of(path: str, index: int) -> list:
    """[(key, name, html)] for every Cuestionario the splitter finds in one .docx."""
    from core.data_parser import parse_docx_to_html, run_docx_splitting_workflow
    course_id = f"{EVAL_COURSE}_{index}"
    course_dir = os.path.join(ROOT, "workspace", course_id)
    try:
        html = parse_docx_to_html(path, course_id)
        os.makedirs(course_dir, exist_ok=True)
        with open(os.path.join(course_dir, "raw_docx_extracted.html"), "w", encoding="utf-8") as f:
            f.write(html)
        manifest = run_docx_splitting_workflow(course_id) or {}
        found = []
        for unit, acts in sorted(manifest.items(), key=lambda kv: str(kv[0])):
            for act_num, info in sorted(acts.items(), key=lambda kv: str(kv[0])):
                if info.get("tipo") != "Cuestionario" or not info.get("file"):
                    continue
                with open(os.path.join(course_dir, "actividades", info["file"]), encoding="utf-8") as f:
                    found.append((f"a{act_num}", info["file"], f.read()))
        return found
    finally:
        shutil.rmtree(course_dir, ignore_errors=True)


def doc_key(path: str) -> str:
    """Stable record folder per document (ai_shadow/<doc>/)."""
    rel = os.path.relpath(path, DOCS_DIR).replace("\\", "/")
    return "eval_" + "".join(c if c.isalnum() else "_" for c in os.path.splitext(rel)[0])[:60]


def _call_cost(excerpt: str, questions: int) -> float:
    input_tokens = len(shadow.build_prompt("bloque", excerpt)) // 4
    output_tokens = max(questions, 1) * OUTPUT_TOKENS_PER_QUESTION
    return input_tokens / 1e6 * (Config.AI_COST_PER_1M_INPUT_TOKENS_USD or 1.5)         + output_tokens / 1e6 * (Config.AI_COST_PER_1M_OUTPUT_TOKENS_USD or 9.0)


def estimate(html: str, gaps: list, parsed: list, expected: int) -> tuple:
    """(cheapest, worst) cost: settled at the first level vs. escalated to the whole activity."""
    from actions.html_transformer import question_excerpts
    excerpts, block = question_excerpts(html)
    flagged = [i for i, q in enumerate(parsed) if shadow._answer_problem(q)]
    calls = []
    if flagged and "faltan_preguntas" not in gaps and len(flagged) <= shadow.MAX_QUESTION_CALLS             and len(excerpts) == len(parsed):
        calls.append(sum(_call_cost(excerpts[i], 1) for i in flagged))
    if block:
        calls.append(_call_cost(block, expected))
    if html != block:
        calls.append(_call_cost(html, expected))
    return calls[0], sum(calls)


def report() -> None:
    records = []
    for path in sorted(glob.glob(os.path.join(shadow.SHADOW_DIR, "*", "*.json"))):
        with open(path, encoding="utf-8") as f:
            records.append(json.load(f))
    if not records:
        print("No hay registros en ai_shadow/ todavía.")
        return

    cols = ["parser", "ia", "esperadas", "ia_validas", "ia_rechazadas", "nuevas_validas",
            "respuestas_completadas", "respuestas_distintas", "tipo_distinto", "solo_parser"]
    print(f"{'documento / actividad':44} {'brechas':24} {'nivel':9} {'llam.':>5} "
          + " ".join(f"{c[:9]:>9}" for c in cols) + "  resuelta")
    totals = {c: 0 for c in cols}
    solved = errors = 0
    levels = {}
    for r in records:
        label = f"{r['curso']}/{r['actividad']}"[:44]
        gaps = ",".join(r.get("brechas", [])) or "-"
        calls = len(r.get("intentos", []))
        if "error" in r:
            errors += 1
            print(f"{label:44} {gaps[:24]:24} {'-':9} {calls:>5} ERROR: {r['error'][:60]}")
            continue
        m = r["metricas"]
        for c in cols:
            totals[c] += m.get(c, 0)
        solved += r["resuelta"]
        if r["resuelta"]:
            levels[r["nivel_final"]] = levels.get(r["nivel_final"], 0) + 1
        print(f"{label:44} {gaps[:24]:24} {r['nivel_final']:9} {calls:>5} "
              + " ".join(f"{m.get(c, 0):>9}" for c in cols) + f"  {'sí' if r['resuelta'] else 'no'}")

    spent = sum(r.get("tokens", {}).get("input", 0) for r in records), sum(r.get("tokens", {}).get("output", 0) for r in records)
    ok = len(records) - errors
    print()
    print(f"Actividades: {len(records)} ({errors} con error)")
    if ok:
        checked = totals["ia_validas"] + totals["ia_rechazadas"]
        print(f"Preguntas de la IA verificadas contra el documento: {totals['ia_validas']} de {checked}"
              f" ({totals['ia_validas'] / checked:.0%})" if checked else "La IA no devolvió preguntas.")
        print(f"Preguntas nuevas (el parser no las leyó) y verificadas: {totals['nuevas_validas']}")
        print(f"Respuestas correctas que la IA completó (verificadas): {totals['respuestas_completadas']}")
        print(f"Respuestas en las que IA y parser no coinciden: {totals['respuestas_distintas']}  <- revisar a mano")
        print(f"Tipos en los que IA y parser no coinciden: {totals['tipo_distinto']}")
        by_level = ", ".join(f"{n} con nivel {lvl}" for lvl, n in levels.items())
        print(f"Actividades resueltas: {solved} de {ok}" + (f" ({by_level})" if by_level else ""))
    print(f"Tokens: {spent[0]} de entrada, {spent[1]} de salida")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", action="store_true", help="call the AI (costs money)")
    parser.add_argument("--all", action="store_true", help="include quizzes without gaps")
    parser.add_argument("--report", action="store_true", help="only summarize ai_shadow/")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    logging.disable(logging.WARNING)  # the splitter logs every document; only this report matters here
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if args.report:
        report()
        return

    if args.run:
        from core.ai_budget_guard import total_spent_usd
        if Config.AI_BUDGET_USD <= 0 or Config.AI_COST_PER_1M_INPUT_TOKENS_USD <= 0 or Config.AI_COST_PER_1M_OUTPUT_TOKENS_USD <= 0:
            sys.exit("Define AI_BUDGET_USD, AI_COST_PER_1M_INPUT_TOKENS_USD y AI_COST_PER_1M_OUTPUT_TOKENS_USD (> 0) en .env antes de --run.")
        from core.ai_structurer import get_gemini_client
        client = get_gemini_client(require_feature_flag=False)
        if client is None:
            sys.exit("No hay cliente de IA (falta GEMINI_API_KEY o se alcanzó el tope de gasto).")
        print(f"Gastado hasta ahora según el registro: ${total_spent_usd():.4f} de ${Config.AI_BUDGET_USD:.2f}")

    paths = sorted(glob.glob(os.path.join(DOCS_DIR, "**", "*.docx"), recursive=True))
    total_cost = 0.0
    sent = 0
    for i, path in enumerate(paths):
        rel = os.path.relpath(path, DOCS_DIR)
        for key, name, html in quizzes_of(path, i):
            gaps, parsed, summary = shadow.find_gaps(html)
            if not gaps and not args.all:
                continue
            cheapest, worst = estimate(html, gaps, parsed, summary["esperadas"])
            recorded = os.path.exists(shadow.record_path(doc_key(path), key, html))
            print(f"{rel[:55]:55} {key:5} {summary['encontradas']:>3}/{summary['esperadas']:<3} "
                  f"{','.join(gaps) or 'sin brecha':32} ~${cheapest:.3f}–{worst:.3f}" + ("  (ya registrado)" if recorded else ""))
            if recorded:
                continue
            total_cost += worst
            if args.run:
                record = shadow.run_shadow(doc_key(path), key, html, name, client=client, force=True)
                sent += 1
                if record and "error" in record:
                    print(f"    error: {record['error'][:200]}")
                    if any(code in record["error"] for code in ("401", "403", "UNAUTHENTICATED", "PERMISSION_DENIED")):
                        sys.exit("
La clave de la IA no es válida (GEMINI_API_KEY). Se detuvo la evaluación; no se guardó nada.")

    print()
    if args.run:
        print(f"Enviadas a la IA: {sent}. Resumen:\n")
        report()
    else:
        print(f"Costo estimado para las pendientes: hasta ~${total_cost:.2f} si todas escalan hasta la actividad "
              "(estimación; el real queda en ai_usage_ledger.json).")
        print("Nada se envió a la IA. Para ejecutar: python -m scripts.ai_shadow_eval --run")


if __name__ == "__main__":
    main()
