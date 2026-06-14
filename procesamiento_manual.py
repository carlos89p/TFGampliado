import json
from datetime import datetime
from pathlib import Path

OUTPUT_JSON = "manual_input_ai_ready.json"


def ask_text(question: str, default: str | None = None) -> str:
    value = input(question).strip()
    if not value and default is not None:
        return default
    return value


def ask_int(question: str, minimum: int | None = None, maximum: int | None = None) -> int:
    while True:
        value = input(question).strip()
        try:
            number = int(value)
            if minimum is not None and number < minimum:
                print(f"Introduce un número mayor o igual que {minimum}.")
                continue
            if maximum is not None and number > maximum:
                print(f"Introduce un número menor o igual que {maximum}.")
                continue
            return number
        except ValueError:
            print("Introduce un número entero válido.")


def ask_float(question: str, minimum: float | None = None, maximum: float | None = None) -> float:
    while True:
        value = input(question).strip().replace(",", ".")
        try:
            number = float(value)
            if minimum is not None and number < minimum:
                print(f"Introduce un número mayor o igual que {minimum}.")
                continue
            if maximum is not None and number > maximum:
                print(f"Introduce un número menor o igual que {maximum}.")
                continue
            return number
        except ValueError:
            print("Introduce un número válido.")




def ask_yes_no(question: str, default: str = "n") -> bool:
    default = default.lower().strip()
    if default not in {"s", "n"}:
        default = "n"

    suffix = "[s/n]"
    if default == "s":
        suffix = "[s/n] [s]"
    elif default == "n":
        suffix = "[s/n] [n]"

    while True:
        value = input(f"{question} {suffix}: ").strip().lower()

        if not value:
            value = default

        if value in {"s", "si", "sí", "y", "yes"}:
            return True

        if value in {"n", "no"}:
            return False

        print("Respuesta no válida. Escribe 's' o 'n'.")


def ask_choice(question: str, valid_options: list[str], default: str) -> str:
    valid = {option.lower(): option.lower() for option in valid_options}
    default = default.lower()

    while True:
        value = input(f"{question} ({', '.join(valid_options)}) [{default}]: ").strip().lower()
        if not value:
            return default
        if value in valid:
            return valid[value]
        print(f"Opción no válida. Elige una de: {', '.join(valid_options)}.")


def normalize_goal(goal: str) -> str:
    text = goal.strip().lower().replace(" ", "_")
    aliases = {
        "perder_peso": "perder_grasa",
        "definir": "perder_grasa",
        "definicion": "perder_grasa",
        "ganar_masa": "ganar_musculo",
        "hipertrofia": "ganar_musculo",
        "recomposición": "recomposicion",
        "recomposicion_corporal": "recomposicion",
    }
    return aliases.get(text, text)


def normalize_level(level: str) -> str:
    text = level.strip().lower()
    if text in {"principiante", "novato", "inicial"}:
        return "principiante"
    if text in {"intermedio", "medio"}:
        return "intermedio"
    if text in {"avanzado", "experto"}:
        return "avanzado"
    return text or "principiante"


def build_manual_user_data() -> dict:
    print("=== Introducción manual de datos ===\n")

    name = ask_text("Nombre: ")
    age = ask_int("Edad: ", minimum=12, maximum=100)
    sex = ask_text("Sexo: ")
    height_cm = ask_float("Altura (cm): ", minimum=100, maximum=230)
    weight_kg = ask_float("Peso actual (kg): ", minimum=30, maximum=250)
    body_fat_percent = ask_float("Porcentaje de grasa corporal (%): ", minimum=3, maximum=70)
    muscle_mass_kg = ask_float("Masa muscular (kg): ", minimum=10, maximum=120)

    print("\n=== Objetivo y contexto de entrenamiento ===")
    goal_type = normalize_goal(
        ask_text("Objetivo general (perder_grasa, ganar_musculo, recomposicion): ")
    )
    days_per_week = ask_int("Días que puedes entrenar por semana: ", minimum=1, maximum=7)
    experience_level = normalize_level(
        ask_text("Nivel de experiencia (principiante, intermedio, avanzado): ", default="principiante")
    )

    print("\n=== Lesiones, molestias y limitaciones ===")
    has_low_back_pain = ask_yes_no(
        "¿Tienes molestias de espalda o dolor lumbar que debamos tener en cuenta?",
        default="n"
    )
    low_back_pain_severity = "ninguna"
    low_back_pain_notes = ""

    if has_low_back_pain:
        low_back_pain_severity = ask_choice(
            "Nivel aproximado de molestia lumbar",
            ["leve", "moderada", "alta"],
            default="leve"
        )
        low_back_pain_notes = ask_text(
            "Describe brevemente qué movimientos te molestan o qué quieres evitar: ",
            default=""
        )

    print("\n=== Información adicional opcional ===")
    print("Puedes dejarlo vacío si no aplica.")
    free_text = ask_text(
        "Indica cualquier otra lesión, molestia, limitación, ejercicio que quieras evitar o comentario importante: ",
        default=""
    )

    if has_low_back_pain:
        free_text = " ".join(part for part in [
            free_text,
            "molestias de espalda/lumbar",
            low_back_pain_notes,
        ] if part).strip()

    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "user_profile": {
            "personal_data": {
                "name": name,
                "age": age,
                "sex": sex,
            },
            "physique_data": {
                "height_cm": height_cm,
                "weight_kg": weight_kg,
                "body_fat_percent": body_fat_percent,
                "muscle_mass_kg": muscle_mass_kg,
            },
        },
        "body_composition": {
            "latest_measurement": {
                "created_date": datetime.now().date().isoformat(),
                "metrics": {
                    "weight_kg": weight_kg,
                    "body_fat_percent": body_fat_percent,
                    "muscle_mass_kg": muscle_mass_kg,
                    "height_cm": height_cm,
                },
            },
            "history": [],
        },
        "goal": {
            "type": goal_type,
        },
        "injury_context": {
            "has_low_back_pain": has_low_back_pain,
            "low_back_pain_severity": low_back_pain_severity,
            "low_back_pain_notes": low_back_pain_notes,
            "areas": ["lumbar", "espalda"] if has_low_back_pain else [],
        },
        "training_context": {
            "days_per_week": days_per_week,
            "experience_level": experience_level,
            "free_text_notes": free_text,
        },
    }


def save_json(data: dict, output_path: str = OUTPUT_JSON) -> None:
    Path(output_path).write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def main() -> None:
    user_data = build_manual_user_data()
    save_json(user_data)
    print(f"\nJSON generado correctamente: {OUTPUT_JSON}")
    print(json.dumps(user_data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
