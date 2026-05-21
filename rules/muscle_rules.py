from __future__ import annotations



def target_muscle_slots(focus: list[str], exercises_per_day: int) -> list[str]:
    """
    Devuelve los grupos musculares que se deben cubrir en cada día.

    Esta versión rota la lista de músculos en vez de cortarla directamente,
    para evitar que desaparezcan grupos importantes como tríceps o abdomen.
    """

    focus_set = set(focus)

    if "upper" in focus_set:
        priority = [
            "pecho",
            "espalda",
            "hombros",
            "biceps",
            "triceps",
            "abdomen",
        ]

    elif "lower" in focus_set:
        priority = [
            "cuadriceps",
            "isquiosurales",
            "gluteos",
            "gemelos",
            "abdomen",
        ]

    elif "push" in focus_set:
        priority = [
            "pecho",
            "hombros",
            "triceps",
            "abdomen",
        ]

    elif "pull" in focus_set:
        priority = [
            "espalda",
            "biceps",
            "trapecios",
            "antebrazos",
            "abdomen",
        ]

    elif "core" in focus_set:
        priority = [
            "abdomen",
        ]

    elif "full_body" in focus_set:
        priority = [
            "cuadriceps",
            "espalda",
            "pecho",
            "isquiosurales",
            "gluteos",
            "hombros",
            "abdomen",
        ]

    else:
        priority = [
            "pecho",
            "espalda",
            "cuadriceps",
            "isquiosurales",
            "gluteos",
            "abdomen",
        ]

    result = []
    i = 0

    while len(result) < exercises_per_day:
        result.append(priority[i % len(priority)])
        i += 1

    return result
