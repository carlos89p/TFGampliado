from __future__ import annotations

from datetime import datetime

from .user_rules import normalize_user_profile
from .notes_rules import extract_restrictions
from .split_rules import choose_split
from .volume_rules import get_volume_rules
from .muscle_rules import target_muscle_slots
from .exercise_filter import filter_catalog
from .exercise_selector import select_exercise
from .progression_rules import get_progression_notes


def build_day(
    day_config: dict,
    catalog: list[dict],
    user_profile: dict,
    restrictions: dict,
    used_exercise_ids: set[int],
) -> dict:
    volume = get_volume_rules(
        goal=user_profile["goal"],
        experience_level=user_profile["experience_level"],
        day_focus=day_config["focus"],
    )

    muscle_slots = target_muscle_slots(
        focus=day_config["focus"],
        exercises_per_day=volume["exercises_per_day"],
    )

    used_families_day = set()
    exercises = []

    for muscle in muscle_slots:
        candidates = filter_catalog(
            catalog=catalog,
            muscle_group=muscle,
            user_level=user_profile["experience_level"],
            avoid_keywords=restrictions["avoid_keywords"],
            allowed_types=["fuerza"],
        )

        selected = select_exercise(
            candidates=candidates,
            target_muscle=muscle,
            used_exercise_ids=used_exercise_ids,
            used_families_day=used_families_day,
            user_level=user_profile["experience_level"],
        )

        if selected is None:
            exercises.append({
                "exercise_id": None,
                "name": f"No se encontró ejercicio válido para {muscle}",
                "muscle_group": muscle,
                "equipment": None,
                "level": None,
                "sets": volume["sets"],
                "reps": volume["reps"],
                "rest": volume["rest"],
            })
            continue

        exercises.append({
            "exercise_id": selected["id"],
            "name": selected["name"],
            "muscle_group": selected["muscle_group"],
            "equipment": selected["equipment"],
            "level": selected["level"],
            "sets": volume["sets"],
            "reps": volume["reps"],
            "rest": volume["rest"],
        })

    return {
        "day": day_config["day"],
        "name": day_config["name"],
        "focus": day_config["focus"],
        "exercises": exercises,
    }


def build_routine(user_data: dict, catalog: list[dict]) -> dict:
    user_profile = normalize_user_profile(user_data)
    restrictions = extract_restrictions(user_profile["free_text_notes"])
    split = choose_split(
        days_per_week=user_profile["days_per_week"],
        experience_level=user_profile["experience_level"],
    )

    used_exercise_ids = set()
    days = []

    for day_config in split["days"]:
        days.append(
            build_day(
                day_config=day_config,
                catalog=catalog,
                user_profile=user_profile,
                restrictions=restrictions,
                used_exercise_ids=used_exercise_ids,
            )
        )

    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "generator": "rules_based_v2",
        "user_summary": user_profile,
        "detected_restrictions": restrictions,
        "split": {
            "name": split["split_name"],
            "days_per_week": user_profile["days_per_week"],
        },
        "routine": days,
        "progression_notes": get_progression_notes(
            goal=user_profile["goal"],
            experience_level=user_profile["experience_level"],
        ),
    }
