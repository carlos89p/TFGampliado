from __future__ import annotations

import random


PRIMARY_KEYWORDS = {
    "pecho": [
        "chest press",
        "bench press",
        "push-up",
        "push up",
        "press",
    ],
    "espalda": [
        "seated row",
        "machine row",
        "row",
        "lat pulldown",
        "pulldown",
        "pull-down",
        "pull-up",
        "chin-up",
    ],
    "hombros": [
        "shoulder press",
        "lateral raise",
        "rear delt",
        "face pull",
        "front raise",
    ],
    "biceps": [
        "cable curl",
        "machine curl",
        "dumbbell curl",
        "curl",
    ],
    "triceps": [
        "pushdown",
        "pressdown",
        "extension",
        "dip",
    ],
    "cuadriceps": [
        "leg press",
        "squat",
        "lunge",
        "split squat",
        "leg extension",
    ],
    "isquiotibiales": [
        "leg curl",
        "hamstring curl",
        "lying leg curl",
        "seated leg curl",
        "romanian deadlift",
        "stiff-legged deadlift",
        "deadlift",
    ],
    "femorales": [
        "leg curl",
        "hamstring curl",
        "lying leg curl",
        "seated leg curl",
        "romanian deadlift",
        "stiff-legged deadlift",
        "deadlift",
    ],
    "hamstrings": [
        "leg curl",
        "hamstring curl",
        "lying leg curl",
        "seated leg curl",
        "romanian deadlift",
        "stiff-legged deadlift",
        "deadlift",
    ],
    "gluteos": [
        "hip thrust",
        "glute bridge",
        "bridge",
        "pull-through",
    ],
    "gemelos": [
        "calf raise",
        "calf press",
    ],
    "abdomen": [
        "plank",
        "crunch",
        "leg raise",
        "reverse crunch",
        "pallof",
    ],
    "trapecios": [
        "shrug",
        "face pull",
    ],
    "antebrazos": [
        "wrist curl",
        "farmer",
        "reverse curl",
    ],
}


EASY_EQUIPMENT_BONUS = {
    "maquina": 6,
    "polea": 5,
    "mancuernas": 3,
    "peso_corporal": 2,
    "barra": 0,
    "bandas": 1,
    "otro": -4,
}


BAD_WORDS = [
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
    "complex",
    "duck walk",
    "juggle",
    "wax-on",
    "wax-off",
    "pop ",
    "30 ",
]


TOO_DYNAMIC_FOR_BEGINNER = [
    "jump",
    "burpee",
    "swing",
    "clean",
    "snatch",
    "juggle",
    "sprawl",
    "duck walk",
    "crawl",
    "pike",
    "handstand",
    "man maker",
]


def exercise_family(name: str) -> str:
    text = (name or "").lower()

    families = [
        "bench press",
        "chest press",
        "shoulder press",
        "leg press",
        "leg curl",
        "leg extension",
        "calf raise",
        "hip thrust",
        "glute bridge",
        "pull-up",
        "chin-up",
        "pulldown",
        "push-up",
        "deadlift",
        "squat",
        "lunge",
        "row",
        "curl",
        "raise",
        "extension",
        "plank",
        "crunch",
        "twist",
        "dip",
        "shrug",
    ]

    for family in families:
        if family in text:
            return family

    words = text.replace("-", " ").replace("/", " ").split()
    return words[0] if words else text


def has_bad_name(name: str) -> bool:
    text = (name or "").lower()
    return any(word in text for word in BAD_WORDS)


def score_exercise(exercise: dict, target_muscle: str, user_level: str) -> int:
    name = (exercise.get("name") or "").lower()
    equipment = (exercise.get("equipment") or "").lower()
    level = (exercise.get("level") or "").lower()

    score = 0

    if has_bad_name(name):
        score -= 120

    if any(word in name for word in ["stretch", "smr", "foam roll", "mobility"]):
        score -= 100

    if " to " in name:
        score -= 25

    if user_level == "principiante":
        if any(word in name for word in TOO_DYNAMIC_FOR_BEGINNER):
            score -= 70

    for keyword in PRIMARY_KEYWORDS.get(target_muscle, []):
        if keyword in name:
            score += 14

    score += EASY_EQUIPMENT_BONUS.get(equipment, 0)

    if user_level == "principiante":
        if equipment in {"maquina", "polea"}:
            score += 10
        elif equipment == "mancuernas":
            score += 4
        elif equipment == "barra":
            score -= 4

    simple_bonus_words = [
        "machine",
        "seated",
        "standing",
        "dumbbell",
        "cable",
        "smith",
        "press",
        "row",
        "curl",
        "raise",
        "extension",
        "leg press",
        "leg curl",
        "pulldown",
        "pushdown",
    ]

    if any(word in name for word in simple_bonus_words):
        score += 4

    if len(name.split()) > 5:
        score -= 15

    if level == "principiante":
        score += 5

    return score


def select_exercise(
    candidates: list[dict],
    target_muscle: str,
    used_exercise_ids: set[int],
    used_families_day: set[str],
    user_level: str = "principiante",
) -> dict | None:
    available = []

    for exercise in candidates:
        exercise_id = exercise.get("id")
        name = exercise.get("name", "")

        if exercise_id in used_exercise_ids:
            continue

        family = exercise_family(name)
        if family in used_families_day:
            continue

        available.append(exercise)

    if not available:
        return None

    available.sort(
        key=lambda item: score_exercise(item, target_muscle, user_level),
        reverse=True,
    )

    best_score = score_exercise(available[0], target_muscle, user_level)
    top = [
        item for item in available
        if score_exercise(item, target_muscle, user_level) >= best_score - 4
    ]

    selected = random.choice(top[:5]) if top else available[0]

    used_exercise_ids.add(selected["id"])
    used_families_day.add(exercise_family(selected.get("name", "")))

    return selected
