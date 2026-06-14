from __future__ import annotations


def get_nested(data: dict, path: list[str], default=None):
    current = data
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def calculate_bmi(weight_kg: float, height_cm: float) -> float | None:
    if not weight_kg or not height_cm:
        return None
    height_m = height_cm / 100
    if height_m <= 0:
        return None
    return round(weight_kg / (height_m ** 2), 2)


def classify_body_fat(body_fat_percent: float | None, sex: str) -> str:
    if body_fat_percent is None:
        return "desconocido"

    sex = (sex or "").lower()

    if sex == "hombre":
        if body_fat_percent < 15:
            return "bajo"
        if body_fat_percent < 25:
            return "medio"
        return "alto"

    if sex == "mujer":
        if body_fat_percent < 23:
            return "bajo"
        if body_fat_percent < 33:
            return "medio"
        return "alto"

    if body_fat_percent < 20:
        return "bajo"
    if body_fat_percent < 30:
        return "medio"
    return "alto"


def normalize_user_profile(user_data: dict) -> dict:
    personal = get_nested(user_data, ["user_profile", "personal_data"], {})
    physique = get_nested(user_data, ["user_profile", "physique_data"], {})
    goal = get_nested(user_data, ["goal"], {})
    training = get_nested(user_data, ["training_context"], {})
    injury_context = get_nested(user_data, ["injury_context"], {})

    weight = physique.get("weight_kg")
    height = physique.get("height_cm")
    body_fat = physique.get("body_fat_percent")
    sex = personal.get("sex", "")

    return {
        "name": personal.get("name", "Usuario"),
        "age": personal.get("age"),
        "sex": sex,
        "height_cm": height,
        "weight_kg": weight,
        "body_fat_percent": body_fat,
        "muscle_mass_kg": physique.get("muscle_mass_kg"),
        "bmi": calculate_bmi(weight, height),
        "body_fat_category": classify_body_fat(body_fat, sex),
        "goal": goal.get("type", "recomposicion"),
        "days_per_week": int(training.get("days_per_week", 3)),
        "experience_level": training.get("experience_level", "principiante"),
        "free_text_notes": training.get("free_text_notes", ""),
        "injuries": {
            "has_low_back_pain": bool(injury_context.get("has_low_back_pain", False)),
            "low_back_pain_severity": injury_context.get("low_back_pain_severity", "ninguna"),
            "low_back_pain_notes": injury_context.get("low_back_pain_notes", ""),
            "areas": injury_context.get("areas", []),
        },
    }
