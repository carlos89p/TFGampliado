from __future__ import annotations


LEVEL_ORDER = {
    "principiante": 1,
    "intermedio": 2,
    "avanzado": 3,
}


BAD_NAME_KEYWORDS = [
    "holman",
    "metaburn",
    "fyr",
    "fyr2",
    "tyler",
    "gethin",
    "uns ",
    "hm ",
    "un ",
    "partner",
    "janda",
    "rocket",
    "monster",
    "killer",
    "crusher",
    "sprawl",
    "burpee",
    "agility",
    "ladder",
    "jump",
    "plyo",
    "crossfit",
    "complex",
    "duck walk",
    "juggle",
    "wax-on",
    "wax-off",
    "pop ",
    "throw",
    "explosive",
]

BAD_NAME_PREFIXES = [
    "30 ",
    "am ",
    "kv ",
    "tbs ",
]


MUSCLE_ALIASES = {
        "isquiotibiales": ["isquiotibiales", "isquiosurales", "femorales", "hamstrings", "hamstring"],
    "isquiosurales": ["isquiotibiales", "isquiosurales", "femorales", "hamstrings", "hamstring"],
    "femorales": ["isquiotibiales", "isquiosurales", "femorales", "hamstrings", "hamstring"],
    "hamstrings": ["isquiotibiales", "isquiosurales", "femorales", "hamstrings", "hamstring"],
    "hamstring": ["isquiotibiales", "isquiosurales", "femorales", "hamstrings", "hamstring"],
}


def normalize_text(value: str) -> str:
    return (value or "").strip().lower()


def accepted_muscle_names(muscle_group: str) -> set[str]:
    muscle = normalize_text(muscle_group)
    return set(MUSCLE_ALIASES.get(muscle, [muscle]))


def is_marketing_or_weird_exercise(name: str) -> bool:
    text = normalize_text(name)

    if any(text.startswith(prefix) for prefix in BAD_NAME_PREFIXES):
        return True

    return any(keyword in text for keyword in BAD_NAME_KEYWORDS)


def is_level_allowed(exercise_level: str, user_level: str) -> bool:
    exercise_score = LEVEL_ORDER.get(normalize_text(exercise_level), 2)
    user_score = LEVEL_ORDER.get(normalize_text(user_level), 1)

    if user_score == 1:
        # El dataset marca muchos ejercicios básicos como intermedios.
        return exercise_score <= 2

    return exercise_score <= user_score


def filter_catalog(
    catalog: list[dict],
    muscle_group: str,
    user_level: str,
    avoid_keywords: list[str] | None = None,
    allowed_types: list[str] | None = None,
) -> list[dict]:
    avoid_keywords = avoid_keywords or []
    allowed_types = allowed_types or ["fuerza"]

    valid_muscles = accepted_muscle_names(muscle_group)
    result = []

    for exercise in catalog:
        name = exercise.get("name", "")
        clean_name = normalize_text(name)
        level = normalize_text(exercise.get("level", ""))
        muscle = normalize_text(exercise.get("muscle_group", ""))
        exercise_type = normalize_text(exercise.get("type", ""))

        if not clean_name:
            continue

        if muscle not in valid_muscles:
            continue

        if exercise_type not in allowed_types:
            continue

        if not is_level_allowed(level, user_level):
            continue

        if is_marketing_or_weird_exercise(clean_name):
            continue

        if any(keyword.lower() in clean_name for keyword in avoid_keywords):
            continue

        result.append(exercise)

    return result
