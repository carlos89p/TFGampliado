from __future__ import annotations

from copy import deepcopy


LOW_BACK_INJURY_KEYS = {"espalda", "lumbar", "dolor_lumbar", "molestia_lumbar"}

LOW_BACK_AVOID_KEYWORDS = [
    "deadlift",
    "stiff-legged deadlift",
    "romanian deadlift",
    "good morning",
    "back extension",
    "hyperextension",
    "bent-over row",
    "bent over row",
    "t-bar row",
    "barbell row",
    "back squat",
    "front squat",
    "overhead squat",
    "power clean",
    "clean",
    "snatch",
    "thruster",
    "swing",
    "jump",
    "plyo",
    "burpee",
    "sprawl",
    "throw",
    "twist",
    "russian twist",
    "rollout",
    "ab rollout",
]

LOW_BACK_PREFERRED_KEYWORDS = [
    "bird dog",
    "dead bug",
    "plank",
    "side plank",
    "pallof",
    "glute bridge",
    "hip thrust",
    "seated row",
    "machine row",
    "lat pulldown",
    "pulldown",
    "leg curl",
    "leg press",
    "cable",
    "machine",
    "seated",
]

LOW_BACK_SAFE_CORE_KEYWORDS = [
    "bird dog",
    "dead bug",
    "plank",
    "side plank",
    "pallof",
    "mcgill modified curl-up",
    "cat-cow",
]

LOW_BACK_EVIDENCE = {
    "source": "Hayden JA, Ellis J, Ogilvie R, Malmivaara A, van Tulder MW. Exercise therapy for chronic low back pain. Cochrane Database Syst Rev. 2021;9(9):CD009790. doi: 10.1002/14651858.CD009790.pub2.",
    "summary": (
        "La revisión Cochrane indica que el ejercicio probablemente reduce el dolor frente a no tratamiento, "
        "atención habitual o placebo en personas adultas con dolor lumbar crónico inespecífico. La adaptación "
        "se orienta a mantener actividad física con ejercicios progresivos, fortalecimiento, core, movilidad y "
        "trabajo aeróbico, ajustando necesidades, preferencias y capacidades del usuario."
    ),
    "exercise_types_considered": [
        "fortalecimiento muscular",
        "core strengthening / estabilidad lumbopélvica",
        "flexibilidad y movilidad",
        "ejercicio aeróbico",
        "ejercicios mixtos progresivos",
    ],
}


def has_low_back_issue(user_profile: dict, restrictions: dict | None = None) -> bool:
    restrictions = restrictions or {}
    injuries = {str(item).lower() for item in restrictions.get("injuries", [])}
    structured = user_profile.get("injuries", {}) if isinstance(user_profile, dict) else {}
    notes = (user_profile.get("free_text_notes", "") if isinstance(user_profile, dict) else "").lower()

    if injuries & LOW_BACK_INJURY_KEYS:
        return True

    if isinstance(structured, dict):
        if structured.get("has_low_back_pain") is True:
            return True
        injury_list = {str(item).lower() for item in structured.get("areas", [])}
        if injury_list & LOW_BACK_INJURY_KEYS:
            return True

    return any(word in notes for word in ["espalda", "lumbar", "lumbalgia", "ciatica", "ciática"])


def enrich_restrictions_for_injuries(user_profile: dict, restrictions: dict) -> dict:
    """Añade reglas específicas cuando se detecta molestia lumbar/espalda."""
    enriched = deepcopy(restrictions)
    enriched.setdefault("injuries", [])
    enriched.setdefault("avoid_keywords", [])
    enriched.setdefault("preferred_keywords", [])
    enriched.setdefault("evidence_based_recommendations", [])
    enriched.setdefault("training_adjustments", [])

    if has_low_back_issue(user_profile, enriched):
        enriched["injuries"] = sorted(set(enriched["injuries"] + ["espalda", "lumbar"]))
        enriched["avoid_keywords"] = sorted(set(enriched["avoid_keywords"] + LOW_BACK_AVOID_KEYWORDS))
        enriched["preferred_keywords"] = sorted(set(enriched["preferred_keywords"] + LOW_BACK_PREFERRED_KEYWORDS))
        enriched["evidence_based_recommendations"].append(LOW_BACK_EVIDENCE)
        enriched["training_adjustments"].extend([
            "Mantener ejercicio físico, pero con progresión conservadora y control técnico.",
            "Priorizar estabilidad del core, fortalecimiento general, movilidad y trabajo aeróbico suave.",
            "Evitar inicialmente cargas axiales pesadas, bisagras de cadera pesadas y movimientos explosivos si provocan dolor.",
            "Usar alternativas más controladas como máquinas, poleas, ejercicios sentados y peso corporal cuando sea posible.",
            "Detener o modificar cualquier ejercicio que aumente claramente el dolor lumbar durante la sesión.",
        ])

    enriched["injuries"] = sorted(set(enriched["injuries"]))
    enriched["avoid_keywords"] = sorted(set(enriched["avoid_keywords"]))
    enriched["preferred_keywords"] = sorted(set(enriched["preferred_keywords"]))
    enriched["training_adjustments"] = list(dict.fromkeys(enriched["training_adjustments"]))

    return enriched


def adapt_volume_for_injuries(volume: dict, user_profile: dict, restrictions: dict) -> dict:
    """Reduce ligeramente el volumen inicial si hay molestia lumbar."""
    adjusted = dict(volume)

    if has_low_back_issue(user_profile, restrictions):
        adjusted["sets"] = min(int(adjusted.get("sets", 3)), 3)
        adjusted["exercises_per_day"] = max(4, min(int(adjusted.get("exercises_per_day", 5)), 5))
        adjusted["rest"] = "90-120 segundos"
        adjusted["injury_volume_adjustment"] = "Volumen moderado por molestia lumbar/espalda. Priorizar técnica y tolerancia al dolor."

    return adjusted


def low_back_bonus_for_exercise(exercise: dict) -> int:
    """Puntuación extra/penalización para seleccionar ejercicios más compatibles con molestia lumbar."""
    name = (exercise.get("name") or "").lower()
    equipment = (exercise.get("equipment") or "").lower()
    muscle = (exercise.get("muscle_group") or "").lower()

    score = 0

    if any(keyword in name for keyword in LOW_BACK_AVOID_KEYWORDS):
        score -= 80

    if any(keyword in name for keyword in LOW_BACK_PREFERRED_KEYWORDS):
        score += 20

    if muscle == "abdomen" and any(keyword in name for keyword in LOW_BACK_SAFE_CORE_KEYWORDS):
        score += 35

    if muscle == "espalda" and any(keyword in name for keyword in ["seated row", "machine row", "lat pulldown", "pulldown"]):
        score += 25

    if muscle in {"isquiotibiales", "isquiosurales", "hamstrings", "femorales"}:
        if "leg curl" in name:
            score += 30
        if "deadlift" in name or "clean" in name or "snatch" in name:
            score -= 90

    if muscle == "gluteos" and any(keyword in name for keyword in ["glute bridge", "hip thrust"]):
        score += 25

    if muscle == "cuadriceps":
        if "leg press" in name:
            score += 25
        if "squat" in name and "machine" not in name and "smith" not in name:
            score -= 20

    if muscle == "abdomen" and any(keyword in name for keyword in [
        "jack",
        "walk",
        "walk-out",
        "up-down",
        "push-up",
        "leg raise",
        "hip dip",
        "spider",
        "elevated",
        "copenhagen",
        "rollout",
        "sit-up",
        "sit up",
        "crunch",
        "reach",
        "fire hydrant",
        "lateral raise",
        "march",
        "pulse",
        "shift",
        "judo",
        "v-up",
        "hip raise",
        "wood chop",
        "side bend",
        "scissor",
        "leg lift",
        "curl up",
    ]):
        score -= 45

    if muscle == "abdomen" and any(keyword in name for keyword in [
        "jack",
        "walk",
        "walk-out",
        "up-down",
        "push-up",
        "leg raise",
        "hip dip",
        "spider",
        "elevated",
        "copenhagen",
        "rollout",
        "sit-up",
        "sit up",
        "crunch",
        "reach",
        "fire hydrant",
        "lateral raise",
        "march",
        "pulse",
        "shift",
        "judo",
        "v-up",
        "hip raise",
        "wood chop",
        "side bend",
        "scissor",
        "leg lift",
        "curl up",
    ]):
        score -= 45

    if equipment in {"maquina", "polea"}:
        score += 10
    elif equipment == "barra":
        score -= 12

    return score


def build_injury_progression_notes(user_profile: dict, restrictions: dict) -> list[str]:
    if not has_low_back_issue(user_profile, restrictions):
        return []

    return [
        "Por la molestia lumbar/espalda indicada, la rutina se ha adaptado para mantener actividad física sin reposo absoluto prolongado.",
        "Antes de cada sesión, realiza 5-10 minutos de calentamiento suave y movilidad controlada de cadera/columna sin dolor.",
        "Trabaja el core con ejercicios de estabilidad y control, evitando flexiones, giros o extensiones lumbares agresivas si generan síntomas.",
        "Mantén una intensidad moderada: termina las series con margen y evita llegar al fallo técnico.",
        "Esta adaptación no sustituye valoración médica o fisioterapéutica si el dolor es intenso, irradiado, progresivo o aparece con hormigueo/pérdida de fuerza.",
    ]
