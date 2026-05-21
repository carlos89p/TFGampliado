from __future__ import annotations


def get_progression_notes(goal: str, experience_level: str) -> list[str]:
    goal = (goal or "recomposicion").lower()
    level = (experience_level or "principiante").lower()

    notes = [
        "Mantén 1-3 repeticiones en recámara en la mayoría de series.",
        "Prioriza la técnica antes de aumentar peso.",
    ]

    if level == "principiante":
        notes.append("Cuando completes todas las repeticiones con buena técnica, aumenta ligeramente la carga la próxima sesión.")
    else:
        notes.append("Aplica sobrecarga progresiva semanal mediante más carga, más repeticiones o mejor control técnico.")

    if goal == "perder_grasa":
        notes.append("Mantén descansos moderados y añade cardio suave o pasos diarios si el objetivo principal es perder grasa.")
    elif goal == "ganar_musculo":
        notes.append("Busca progresar especialmente en ejercicios multiarticulares y mantén un volumen recuperable.")
    else:
        notes.append("Combina progresión de fuerza con control del volumen para favorecer recomposición corporal.")

    return notes
