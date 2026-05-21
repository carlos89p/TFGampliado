from __future__ import annotations


def get_volume_rules(goal: str, experience_level: str, day_focus: list[str]) -> dict:
    goal = (goal or "recomposicion").lower()
    level = (experience_level or "principiante").lower()

    if level == "principiante":
        exercises_per_day = 5
        sets = 3
    elif level == "intermedio":
        exercises_per_day = 6
        sets = 3
    else:
        exercises_per_day = 7
        sets = 4

    if "core" in day_focus and len(day_focus) == 1:
        exercises_per_day = min(exercises_per_day, 4)

    if goal == "ganar_musculo":
        reps = "8-12"
        rest = "90-120 segundos"
    elif goal == "perder_grasa":
        reps = "10-15"
        rest = "60-90 segundos"
    else:
        reps = "8-12"
        rest = "75-120 segundos"

    return {
        "exercises_per_day": exercises_per_day,
        "sets": sets,
        "reps": reps,
        "rest": rest,
    }
