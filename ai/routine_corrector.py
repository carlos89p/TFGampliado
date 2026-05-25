from __future__ import annotations

import copy
import json
import re
from datetime import datetime

from .ollama_client import OllamaError, call_ollama_chat, DEFAULT_MODEL
from .routine_validator import validate_routine_with_ai
from rules.exercise_filter import filter_catalog
from rules.exercise_selector import score_exercise


CORRECTION_SYSTEM_PROMPT = """
Eres un entrenador personal y corrector técnico de rutinas.
Tu tarea NO es inventar ejercicios.
Tu tarea es elegir sustitutos únicamente desde una lista cerrada de candidatos reales del catálogo.

Reglas obligatorias:
- Devuelve siempre JSON válido.
- No uses Markdown.
- No inventes ejercicios.
- El campo selected_exercise_id debe ser uno de los IDs incluidos en candidates.
- Si ningún candidato es adecuado, usa selected_exercise_id: null.
""".strip()


LOCAL_BAD_KEYWORDS = [
    "throw",
    "explosive",
    "holman",
    "metaburn",
    "fyr",
    "fyr2",
    "tyler",
    "gethin",
    "uns ",
    "hm ",
    "partner",
    "burpee",
    "sprawl",
    "jump",
    "juggle",
    "complex",
    "wax-on",
    "wax-off",
    "30 ",
    "dumbbell fix",
]


def _extract_json_object(text: str) -> dict:
    text = (text or "").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("La IA no devolvió un objeto JSON reconocible.")

    return json.loads(match.group(0))


def _exercise_has_local_problem(exercise: dict, user_level: str) -> str | None:
    name = (exercise.get("name") or "").lower()

    if exercise.get("exercise_id") is None:
        return "No se encontró ejercicio válido."

    if any(keyword in name for keyword in LOCAL_BAD_KEYWORDS):
        return "Nombre asociado a ejercicio explosivo, comercial o poco adecuado."

    if user_level == "principiante" and "deadlift" in name and "stiff-legged" not in name:
        return "Peso muerto o variante técnica poco prioritaria para principiante."

    if user_level == "principiante" and (exercise.get("level") or "").lower() == "avanzado":
        return "Ejercicio avanzado para principiante."

    return None


def _collect_problematic_positions(routine: dict, ai_validation: dict) -> list[dict]:
    """
    IMPORTANTE:
    La IA puede detectar observaciones, pero NO debe provocar reemplazos automáticos
    por simples warnings.

    Solo se sustituyen ejercicios si hay un problema local determinista grave.
    """
    user_level = (routine.get("user_summary", {}).get("experience_level") or "principiante").lower()
    problems = []

    for day_index, day in enumerate(routine.get("routine", [])):
        for exercise_index, exercise in enumerate(day.get("exercises", [])):
            reason = _exercise_has_local_problem(exercise, user_level)

            if reason:
                problems.append({
                    "day_index": day_index,
                    "exercise_index": exercise_index,
                    "exercise": exercise,
                    "reason": reason,
                })

    return problems


def _used_ids(routine: dict) -> set[int]:
    result = set()

    for day in routine.get("routine", []):
        for exercise in day.get("exercises", []):
            exercise_id = exercise.get("exercise_id")
            if isinstance(exercise_id, int):
                result.add(exercise_id)

    return result


def _candidate_payload(candidate: dict, target_muscle: str, user_level: str) -> dict:
    return {
        "exercise_id": candidate.get("id"),
        "name": candidate.get("name"),
        "muscle_group": candidate.get("muscle_group"),
        "equipment": candidate.get("equipment"),
        "level": candidate.get("level"),
        "type": candidate.get("type"),
        "score": score_exercise(candidate, target_muscle, user_level),
    }


def _find_replacement_candidates(
    catalog: list[dict],
    routine: dict,
    problematic_exercise: dict,
    max_candidates: int = 12,
) -> list[dict]:
    user_level = (routine.get("user_summary", {}).get("experience_level") or "principiante").lower()
    target_muscle = problematic_exercise.get("muscle_group")
    used = _used_ids(routine)

    old_id = problematic_exercise.get("exercise_id")
    if isinstance(old_id, int):
        used.discard(old_id)

    candidates = filter_catalog(
        catalog=catalog,
        muscle_group=target_muscle,
        user_level=user_level,
        avoid_keywords=[],
        allowed_types=["fuerza"],
    )

    candidates = [
        c for c in candidates
        if c.get("id") not in used
        and c.get("name") != problematic_exercise.get("name")
    ]

    candidates.sort(
        key=lambda item: score_exercise(item, target_muscle, user_level),
        reverse=True,
    )

    candidates = [
        c for c in candidates
        if score_exercise(c, target_muscle, user_level) >= 0
    ]

    return candidates[:max_candidates]


def _choose_replacement_with_ai(
    problematic: dict,
    candidates: list[dict],
    routine: dict,
    model: str | None = None,
) -> dict:
    user_summary = routine.get("user_summary", {})
    old_exercise = problematic["exercise"]
    target_muscle = old_exercise.get("muscle_group")
    user_level = user_summary.get("experience_level", "principiante")

    candidate_payload = [
        _candidate_payload(c, target_muscle, user_level)
        for c in candidates
    ]

    prompt = f"""
Elige el mejor sustituto para un ejercicio problemático.

Perfil del usuario:
{json.dumps(user_summary, ensure_ascii=False, indent=2)}

Ejercicio problemático:
{json.dumps(old_exercise, ensure_ascii=False, indent=2)}

Motivo de sustitución:
{problematic["reason"]}

Candidatos permitidos del catálogo:
{json.dumps(candidate_payload, ensure_ascii=False, indent=2)}

Devuelve exclusivamente este JSON:
{{
  "selected_exercise_id": 123,
  "reason": "Motivo breve de la elección."
}}

Recuerda:
- selected_exercise_id debe ser uno de los candidatos.
- Si ninguno es adecuado, selected_exercise_id debe ser null.
""".strip()

    raw_response = call_ollama_chat(
        messages=[
            {"role": "system", "content": CORRECTION_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        model=model,
        timeout=120,
        temperature=0.0,
    )

    parsed = _extract_json_object(raw_response)
    selected_id = parsed.get("selected_exercise_id")

    valid_ids = {c.get("id") for c in candidates}
    if selected_id not in valid_ids:
        return {
            "selected_exercise_id": None,
            "reason": parsed.get("reason", "La IA no eligió un ID válido."),
            "raw_response": raw_response,
        }

    return {
        "selected_exercise_id": selected_id,
        "reason": parsed.get("reason", ""),
        "raw_response": raw_response,
    }


def _apply_replacement(
    corrected_routine: dict,
    problem: dict,
    replacement: dict,
    ai_reason: str,
) -> dict:
    day_index = problem["day_index"]
    exercise_index = problem["exercise_index"]
    old_exercise = corrected_routine["routine"][day_index]["exercises"][exercise_index]

    new_exercise = {
        "exercise_id": replacement["id"],
        "name": replacement["name"],
        "muscle_group": replacement["muscle_group"],
        "equipment": replacement["equipment"],
        "level": replacement["level"],
        "sets": old_exercise.get("sets"),
        "reps": old_exercise.get("reps"),
        "rest": old_exercise.get("rest"),
    }

    corrected_routine["routine"][day_index]["exercises"][exercise_index] = new_exercise

    return {
        "day": corrected_routine["routine"][day_index].get("name"),
        "old_exercise": old_exercise,
        "new_exercise": new_exercise,
        "problem_reason": problem["reason"],
        "selection_reason": ai_reason,
    }


def correct_routine_with_ai(
    routine: dict,
    catalog: list[dict],
    model: str | None = None,
    enabled: bool = True,
) -> dict:
    corrected = copy.deepcopy(routine)

    result = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "model": model or DEFAULT_MODEL,
        "enabled": enabled,
        "status": "not_run",
        "changes_applied": [],
        "problems_detected": [],
        "errors": [],
    }

    if not enabled:
        corrected["ai_correction"] = {
            **result,
            "status": "disabled",
        }
        return {
            "corrected_routine": corrected,
            "ai_validation_initial": None,
            "ai_correction": corrected["ai_correction"],
            "ai_validation_final": None,
        }

    initial_validation = validate_routine_with_ai(corrected, model=model, enabled=True)
    problems = _collect_problematic_positions(corrected, initial_validation)

    result["problems_detected"] = [
        {
            "day": corrected["routine"][p["day_index"]].get("name"),
            "exercise_name": p["exercise"].get("name"),
            "exercise_id": p["exercise"].get("exercise_id"),
            "muscle_group": p["exercise"].get("muscle_group"),
            "reason": p["reason"],
        }
        for p in problems
    ]

    if not problems:
        result["status"] = "no_changes_needed"
        corrected["ai_validation"] = initial_validation
        corrected["ai_correction"] = result
        return {
            "corrected_routine": corrected,
            "ai_validation_initial": initial_validation,
            "ai_correction": result,
            "ai_validation_final": initial_validation,
        }

    try:
        for problem in problems:
            candidates = _find_replacement_candidates(
                catalog=catalog,
                routine=corrected,
                problematic_exercise=problem["exercise"],
            )

            if not candidates:
                result["errors"].append({
                    "exercise_name": problem["exercise"].get("name"),
                    "error": "No se encontraron candidatos válidos en el catálogo.",
                })
                continue

            try:
                ai_choice = _choose_replacement_with_ai(
                    problematic=problem,
                    candidates=candidates,
                    routine=corrected,
                    model=model,
                )
                selected_id = ai_choice.get("selected_exercise_id")
                ai_reason = ai_choice.get("reason", "")
            except (OllamaError, ValueError, json.JSONDecodeError) as exc:
                selected_id = candidates[0]["id"]
                ai_reason = f"Fallback por reglas porque la IA no eligió sustituto válido: {exc}"

            replacement = next((c for c in candidates if c.get("id") == selected_id), None)
            if replacement is None:
                result["errors"].append({
                    "exercise_name": problem["exercise"].get("name"),
                    "error": "La IA no seleccionó un candidato válido.",
                })
                continue

            change = _apply_replacement(
                corrected_routine=corrected,
                problem=problem,
                replacement=replacement,
                ai_reason=ai_reason,
            )
            result["changes_applied"].append(change)

        result["status"] = "corrected" if result["changes_applied"] else "no_valid_replacements"

    except Exception as exc:
        result["status"] = "correction_failed"
        result["errors"].append({"error": str(exc)})

    final_validation = validate_routine_with_ai(corrected, model=model, enabled=True)

    corrected["ai_validation_initial"] = initial_validation
    corrected["ai_correction"] = result
    corrected["ai_validation"] = final_validation

    return {
        "corrected_routine": corrected,
        "ai_validation_initial": initial_validation,
        "ai_correction": result,
        "ai_validation_final": final_validation,
    }