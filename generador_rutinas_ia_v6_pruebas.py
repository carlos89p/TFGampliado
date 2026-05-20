import json
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Any

# ============================================================
# CONFIGURACIÓN
# ============================================================

CATALOG_PATHS = [
    Path("processed_context/exercises_catalog.json"),
    Path("context/exercises_catalog.json"),
    Path("exercises_catalog.json"),
]

OUTPUT_USER_JSON = "manual_input_ai_ready.json"
OUTPUT_ROUTINE_MD = "rutina_profesional_generada.md"
OUTPUT_ROUTINE_TXT = "rutina_profesional_generada.txt"
OUTPUT_RAW_AI = "respuesta_ia_raw.txt"

TEST_OUTPUT_DIR = Path("pruebas_rutinas")

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen2.5:14b"

MAX_EXERCISES_PER_BODY_PART = 10
MAX_TOTAL_EXERCISES_FOR_PROMPT = 240


# ============================================================
# FORMULARIO MANUAL
# Igual al cuestionario proporcionado por el usuario.
# ============================================================

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

    print("\n=== Información adicional opcional ===")
    print("Puedes dejarlo vacío si no aplica.")
    free_text = ask_text(
        "Indica cualquier lesión, molestia, limitación, ejercicio que quieras evitar o comentario importante: ",
        default=""
    )

    return make_user_data(
        name=name,
        age=age,
        sex=sex,
        height_cm=height_cm,
        weight_kg=weight_kg,
        body_fat_percent=body_fat_percent,
        muscle_mass_kg=muscle_mass_kg,
        goal_type=goal_type,
        days_per_week=days_per_week,
        experience_level=experience_level,
        free_text=free_text,
    )


def make_user_data(
    name: str,
    age: int,
    sex: str,
    height_cm: float,
    weight_kg: float,
    body_fat_percent: float,
    muscle_mass_kg: float,
    goal_type: str,
    days_per_week: int,
    experience_level: str,
    free_text: str = "",
) -> dict:
    goal_type = normalize_goal(goal_type)
    experience_level = normalize_level(experience_level)

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
        "training_context": {
            "days_per_week": days_per_week,
            "experience_level": experience_level,
            "free_text_notes": free_text,
        },
    }


def save_user_json(data: dict, output_path: Path | str = OUTPUT_USER_JSON) -> None:
    Path(output_path).write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ============================================================
# CATÁLOGO
# ============================================================

def find_catalog_path() -> Path:
    for path in CATALOG_PATHS:
        if path.exists():
            return path

    raise FileNotFoundError(
        "No se encontró exercises_catalog.json. Colócalo en una de estas rutas:\n"
        + "\n".join(str(path) for path in CATALOG_PATHS)
    )


def load_catalog() -> list[dict[str, Any]]:
    path = find_catalog_path()
    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, list):
        raise ValueError("El catálogo debe ser una lista de ejercicios.")

    catalog = []
    seen = set()

    for item in data:
        if not isinstance(item, dict):
            continue

        exercise_id = str(item.get("exercise_id", "")).strip()
        name = str(item.get("name", "")).strip()

        if not exercise_id or not name or exercise_id in seen:
            continue

        seen.add(exercise_id)

        catalog.append({
            "exercise_id": exercise_id,
            "name": name,
            "description": str(item.get("description", "") or "").strip(),
            "type": str(item.get("type", "") or "").strip(),
            "body_part": str(item.get("body_part", "") or "").strip(),
            "equipment": str(item.get("equipment", "") or "").strip(),
            "level": str(item.get("level", "") or "").strip(),
            "rating": float(item.get("rating", 0.0) or 0.0),
        })

    return catalog


# ============================================================
# SELECCIÓN DE EJERCICIOS PARA EL PROMPT
# ============================================================

NOISY_TOKENS = [
    "fyr", "fyr2", "hm ", "holman", "tyler", "metaburn", "gethin",
    "30 ", "uns ", "jordan", "taylor", "partner"
]

RISKY_BEGINNER_TOKENS = [
    "snatch", "clean", "jerk", "muscle-up", "toes-to-bar",
    "one-arm", "single-arm push-up", "guillotine", "sissy",
    "depth", "pistol", "behind the neck"
]


def user_allowed_levels(user_level: str) -> set[str]:
    user_level = normalize_level(user_level)

    if user_level == "principiante":
        return {"Beginner", "Intermediate"}

    if user_level == "intermedio":
        return {"Intermediate", "Beginner"}

    if user_level == "avanzado":
        return {"Intermediate", "Expert", "Beginner"}

    return {"Beginner", "Intermediate"}


def has_noisy_name(exercise: dict[str, Any]) -> bool:
    name = exercise["name"].lower()
    return any(token in name for token in NOISY_TOKENS)


def seems_risky_for_user(exercise: dict[str, Any], user_data: dict[str, Any]) -> bool:
    user_level = user_data["training_context"]["experience_level"]
    notes = user_data["training_context"].get("free_text_notes", "").lower()

    name = exercise["name"].lower()
    body_part = exercise["body_part"]
    exercise_type = exercise["type"]

    if user_level == "principiante":
        if exercise["level"] == "Expert":
            return True
        if exercise_type in {"Olympic Weightlifting", "Strongman"}:
            return True
        if any(token in name for token in RISKY_BEGINNER_TOKENS):
            return True

    if "hombro" in notes or "shoulder" in notes:
        if body_part == "Shoulders" or "overhead" in name or "shoulder press" in name:
            return True

    if "rodilla" in notes or "knee" in notes:
        if any(token in name for token in ["jump", "lunge", "sissy", "pistol", "depth"]):
            return True

    if "espalda" in notes or "lumbar" in notes or "lower back" in notes:
        if body_part == "Lower Back" or any(token in name for token in ["deadlift", "good morning"]):
            return True

    return False


def score_exercise(exercise: dict[str, Any], user_data: dict[str, Any]) -> float:
    score = 0.0
    goal = user_data["goal"]["type"]
    user_level = user_data["training_context"]["experience_level"]

    score += float(exercise.get("rating", 0.0) or 0.0)

    if exercise["type"] == "Strength":
        score += 8
    elif exercise["type"] == "Powerlifting":
        score += 4 if user_level in {"intermedio", "avanzado"} else -3
    elif exercise["type"] == "Cardio":
        score += 4 if goal == "perder_grasa" else 0
    elif exercise["type"] == "Plyometrics":
        score += 2 if user_level != "principiante" else -4
    elif exercise["type"] == "Stretching":
        score -= 3
    elif exercise["type"] in {"Olympic Weightlifting", "Strongman"}:
        score -= 8

    if user_level == "principiante":
        if exercise["level"] == "Beginner":
            score += 8
        elif exercise["level"] == "Intermediate":
            score += 2
        elif exercise["level"] == "Expert":
            score -= 20

    elif user_level == "intermedio":
        if exercise["level"] == "Intermediate":
            score += 8
        elif exercise["level"] == "Beginner":
            score += 2

    elif user_level == "avanzado":
        if exercise["level"] in {"Intermediate", "Expert"}:
            score += 8

    equipment = exercise["equipment"]
    if equipment in {"Barbell", "Dumbbell", "Cable", "Machine", "Body Only", "E-Z Curl Bar"}:
        score += 4
    elif equipment in {"Other", "", "Exercise Ball", "Foam Roll"}:
        score -= 2

    body_part = exercise["body_part"]
    if body_part in {"Chest", "Lats", "Middle Back", "Quadriceps", "Hamstrings", "Glutes", "Shoulders"}:
        score += 5
    elif body_part in {"Biceps", "Triceps", "Calves", "Abdominals", "Lower Back"}:
        score += 3

    name = exercise["name"].lower()

    professional_keywords = [
        "bench press", "row", "squat", "press", "curl", "extension",
        "pulldown", "pull-up", "leg press", "calf raise", "fly",
        "deadlift", "lunge", "raise", "crunch", "plank"
    ]

    if any(keyword in name for keyword in professional_keywords):
        score += 4

    if has_noisy_name(exercise):
        score -= 14

    if not exercise["description"]:
        score -= 1

    if seems_risky_for_user(exercise, user_data):
        score -= 50

    return score


def select_prompt_exercises(catalog: list[dict[str, Any]], user_data: dict[str, Any]) -> list[dict[str, Any]]:
    allowed_levels = user_allowed_levels(user_data["training_context"]["experience_level"])

    filtered = [
        ex for ex in catalog
        if ex["level"] in allowed_levels
        and not seems_risky_for_user(ex, user_data)
        and ex["type"] in {"Strength", "Powerlifting", "Cardio", "Plyometrics", "Stretching"}
    ]

    ranked = sorted(filtered, key=lambda ex: score_exercise(ex, user_data), reverse=True)

    selected = []
    selected_ids = set()

    body_parts_priority = [
        "Chest", "Lats", "Middle Back", "Shoulders",
        "Quadriceps", "Hamstrings", "Glutes",
        "Biceps", "Triceps", "Calves", "Abdominals", "Lower Back"
    ]

    for body_part in body_parts_priority:
        count = 0
        for ex in ranked:
            if ex["exercise_id"] in selected_ids:
                continue
            if ex["body_part"] != body_part:
                continue

            selected.append(ex)
            selected_ids.add(ex["exercise_id"])
            count += 1

            if count >= MAX_EXERCISES_PER_BODY_PART:
                break

    for ex in ranked:
        if len(selected) >= MAX_TOTAL_EXERCISES_FOR_PROMPT:
            break

        if ex["exercise_id"] not in selected_ids:
            selected.append(ex)
            selected_ids.add(ex["exercise_id"])

    return selected[:MAX_TOTAL_EXERCISES_FOR_PROMPT]


# ============================================================
# SPLIT PROFESIONAL DE REFERENCIA
# ============================================================

def get_professional_split(days: int, goal: str, level: str) -> list[dict[str, Any]]:
    if days == 1:
        return [
            {
                "day": 1,
                "name": "Full Body",
                "focus": "Trabajo global de fuerza e hipertrofia",
                "muscle_groups": ["Chest", "Lats", "Quadriceps", "Hamstrings", "Shoulders", "Abdominals"],
            }
        ]

    if days == 2:
        return [
            {
                "day": 1,
                "name": "Torso",
                "focus": "Pecho, espalda, hombro y brazos",
                "muscle_groups": ["Chest", "Lats", "Middle Back", "Shoulders", "Biceps", "Triceps"],
            },
            {
                "day": 2,
                "name": "Pierna y core",
                "focus": "Cuádriceps, femoral, glúteo, gemelo y abdomen",
                "muscle_groups": ["Quadriceps", "Hamstrings", "Glutes", "Calves", "Abdominals"],
            },
        ]

    if days == 3:
        return [
            {
                "day": 1,
                "name": "Push",
                "focus": "Pecho, hombro y tríceps",
                "muscle_groups": ["Chest", "Shoulders", "Triceps"],
            },
            {
                "day": 2,
                "name": "Pull",
                "focus": "Espalda y bíceps",
                "muscle_groups": ["Lats", "Middle Back", "Biceps"],
            },
            {
                "day": 3,
                "name": "Pierna y core",
                "focus": "Pierna completa y abdomen",
                "muscle_groups": ["Quadriceps", "Hamstrings", "Glutes", "Calves", "Abdominals"],
            },
        ]

    if days == 4:
        return [
            {
                "day": 1,
                "name": "Torso A",
                "focus": "Pecho dominante + espalda + hombro",
                "muscle_groups": ["Chest", "Lats", "Shoulders", "Triceps"],
            },
            {
                "day": 2,
                "name": "Pierna A",
                "focus": "Cuádriceps dominante + glúteo + femoral",
                "muscle_groups": ["Quadriceps", "Glutes", "Hamstrings", "Calves"],
            },
            {
                "day": 3,
                "name": "Torso B",
                "focus": "Espalda dominante + pecho accesorio + brazos",
                "muscle_groups": ["Middle Back", "Lats", "Chest", "Biceps", "Shoulders"],
            },
            {
                "day": 4,
                "name": "Pierna B + core",
                "focus": "Femoral/glúteo dominante + abdomen",
                "muscle_groups": ["Hamstrings", "Glutes", "Quadriceps", "Abdominals"],
            },
        ]

    if days == 5:
        return [
            {
                "day": 1,
                "name": "Pecho y tríceps",
                "focus": "Empuje horizontal y accesorios de tríceps",
                "muscle_groups": ["Chest", "Triceps"],
            },
            {
                "day": 2,
                "name": "Espalda y bíceps",
                "focus": "Tracción vertical/horizontal y bíceps",
                "muscle_groups": ["Lats", "Middle Back", "Biceps"],
            },
            {
                "day": 3,
                "name": "Pierna completa",
                "focus": "Cuádriceps, femoral, glúteo y gemelo",
                "muscle_groups": ["Quadriceps", "Hamstrings", "Glutes", "Calves"],
            },
            {
                "day": 4,
                "name": "Hombro y core",
                "focus": "Deltoides, estabilidad escapular y abdomen",
                "muscle_groups": ["Shoulders", "Abdominals"],
            },
            {
                "day": 5,
                "name": "Full Body técnico",
                "focus": "Repaso global con volumen moderado",
                "muscle_groups": ["Chest", "Lats", "Quadriceps", "Glutes", "Abdominals"],
            },
        ]

    if days == 6:
        return [
            {"day": 1, "name": "Push A", "focus": "Pecho, hombro y tríceps", "muscle_groups": ["Chest", "Shoulders", "Triceps"]},
            {"day": 2, "name": "Pull A", "focus": "Espalda y bíceps", "muscle_groups": ["Lats", "Middle Back", "Biceps"]},
            {"day": 3, "name": "Pierna A", "focus": "Cuádriceps y glúteo", "muscle_groups": ["Quadriceps", "Glutes", "Calves"]},
            {"day": 4, "name": "Push B", "focus": "Empuje accesorio", "muscle_groups": ["Chest", "Shoulders", "Triceps"]},
            {"day": 5, "name": "Pull B", "focus": "Espalda dominante", "muscle_groups": ["Lats", "Middle Back", "Biceps"]},
            {"day": 6, "name": "Pierna B + core", "focus": "Femoral, glúteo y abdomen", "muscle_groups": ["Hamstrings", "Glutes", "Abdominals"]},
        ]

    return [
        {"day": 1, "name": "Push A", "focus": "Pecho, hombro y tríceps", "muscle_groups": ["Chest", "Shoulders", "Triceps"]},
        {"day": 2, "name": "Pull A", "focus": "Espalda y bíceps", "muscle_groups": ["Lats", "Middle Back", "Biceps"]},
        {"day": 3, "name": "Pierna A", "focus": "Cuádriceps y glúteo", "muscle_groups": ["Quadriceps", "Glutes", "Calves"]},
        {"day": 4, "name": "Core y movilidad", "focus": "Abdomen, lumbar y movilidad", "muscle_groups": ["Abdominals", "Lower Back"]},
        {"day": 5, "name": "Push B", "focus": "Empuje accesorio", "muscle_groups": ["Chest", "Shoulders", "Triceps"]},
        {"day": 6, "name": "Pull B", "focus": "Espalda dominante", "muscle_groups": ["Lats", "Middle Back", "Biceps"]},
        {"day": 7, "name": "Pierna B", "focus": "Femoral, glúteo y cuádriceps", "muscle_groups": ["Hamstrings", "Glutes", "Quadriceps"]},
    ]


# ============================================================
# PROMPT PROFESIONAL
# ============================================================

def build_professional_prompt(user_data: dict[str, Any], exercises: list[dict[str, Any]]) -> list[dict[str, str]]:
    days = user_data["training_context"]["days_per_week"]
    goal = user_data["goal"]["type"]
    level = user_data["training_context"]["experience_level"]
    split = get_professional_split(days, goal, level)

    compact_exercises = [
        {
            "id": ex["exercise_id"],
            "name": ex["name"],
            "type": ex["type"],
            "body_part": ex["body_part"],
            "equipment": ex["equipment"],
            "level": ex["level"],
            "rating": ex["rating"],
        }
        for ex in exercises
    ]

    system = """
Eres un entrenador personal profesional especializado en programación de fuerza, hipertrofia y recomposición corporal.

Tu respuesta debe parecer hecha por un entrenador real, no por un generador automático.

No hace falta que devuelvas JSON.
Devuelve una rutina profesional en Markdown claro y bien estructurado.

REGLAS IMPORTANTES:
1. Usa exclusivamente ejercicios incluidos en el catálogo proporcionado.
2. Copia los nombres de los ejercicios exactamente como aparecen en el catálogo.
3. No inventes ejercicios.
4. Puedes usar tu conocimiento de entrenamiento para decidir:
   - distribución semanal
   - orden de ejercicios
   - series
   - repeticiones
   - descansos
   - RIR/RPE
   - progresión semanal
   - recomendaciones técnicas
5. La rutina debe ser coherente, realista y aplicable en gimnasio.
6. Evita rutinas genéricas.
7. Ajusta la rutina al objetivo, experiencia y estado físico del usuario.
8. Si el usuario indica molestias o limitaciones, adapta la selección.
9. No metas ejercicios de músculos que no correspondan al día salvo que tenga sentido profesional.
10. No abuses de abdominales ni ejercicios raros del dataset.
11. Prioriza ejercicios básicos, máquinas, poleas y mancuernas cuando sean adecuados.
12. No incluyas advertencias médicas largas; solo una nota breve y profesional si aplica.

ESTRUCTURA DE RESPUESTA OBLIGATORIA:

# Rutina personalizada

## Perfil interpretado
Explica brevemente cómo interpretas el perfil del usuario.

## Objetivo de la planificación
Explica el enfoque de la rutina.

## Distribución semanal
Tabla con día, nombre de sesión, grupos principales y objetivo de la sesión.

## Rutina detallada
Para cada día:
- Objetivo del día.
- Calentamiento específico.
- Tabla con:
  Ejercicio | Series | Repeticiones | Descanso | Intensidad | Observaciones técnicas
- Nota breve sobre ejecución.

## Progresión recomendada
Explica cómo progresar durante 4-6 semanas.

## Recomendaciones finales
Consejos breves sobre descanso, técnica, cardio opcional y recuperación.
"""

    user_payload = {
        "user_data": user_data,
        "recommended_split": split,
        "exercise_catalog_subset": compact_exercises,
    }

    return [
        {"role": "system", "content": system.strip()},
        {"role": "user", "content": json.dumps(user_payload, indent=2, ensure_ascii=False)},
    ]


# ============================================================
# OLLAMA
# ============================================================

def call_ollama(messages: list[dict[str, str]]) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.35,
            "num_ctx": 16000,
        },
    }

    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        OLLAMA_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=360) as response:
            raw = response.read().decode("utf-8")
            obj = json.loads(raw)
            return obj["message"]["content"].strip()
    except urllib.error.URLError as exc:
        raise RuntimeError(
            "No se pudo conectar con Ollama. Comprueba que Ollama está abierto y funcionando."
        ) from exc


# ============================================================
# FALLBACK PROFESIONAL LOCAL
# ============================================================

def pick_first_by_body(
    exercises: list[dict[str, Any]],
    body_part: str,
    used: set[str],
    limit: int = 1
) -> list[dict[str, Any]]:
    result = []

    for ex in exercises:
        if ex["exercise_id"] in used:
            continue
        if ex["body_part"] != body_part:
            continue

        result.append(ex)
        used.add(ex["exercise_id"])

        if len(result) >= limit:
            break

    return result


def build_local_professional_routine(user_data: dict[str, Any], exercises: list[dict[str, Any]]) -> str:
    days = user_data["training_context"]["days_per_week"]
    goal = user_data["goal"]["type"]
    level = user_data["training_context"]["experience_level"]
    notes = user_data["training_context"].get("free_text_notes", "")

    split = get_professional_split(days, goal, level)
    used = set()

    lines = []
    lines.append("# Rutina personalizada")
    lines.append("")
    lines.append("## Perfil interpretado")
    lines.append(
        f"Usuario con nivel {level}, objetivo principal de {goal.replace('_', ' ')}, "
        f"disponibilidad de {days} días semanales y sin limitaciones relevantes indicadas."
        if not notes else
        f"Usuario con nivel {level}, objetivo principal de {goal.replace('_', ' ')}, "
        f"disponibilidad de {days} días semanales y las siguientes observaciones: {notes}."
    )
    lines.append("")
    lines.append("## Objetivo de la planificación")
    lines.append(
        "La rutina busca combinar estímulo de fuerza e hipertrofia con una distribución equilibrada, "
        "priorizando ejercicios controlables, progresión técnica y volumen asumible."
    )
    lines.append("")
    lines.append("## Distribución semanal")
    lines.append("")
    lines.append("| Día | Sesión | Grupos principales | Objetivo |")
    lines.append("|---|---|---|---|")
    for day in split:
        lines.append(f"| {day['day']} | {day['name']} | {', '.join(day['muscle_groups'])} | {day['focus']} |")

    lines.append("")
    lines.append("## Rutina detallada")

    for day in split:
        lines.append("")
        lines.append(f"### Día {day['day']} - {day['name']}")
        lines.append("")
        lines.append(f"**Objetivo del día:** {day['focus']}.")
        lines.append("")
        lines.append("**Calentamiento específico:** 5-8 minutos de movilidad articular, aproximaciones progresivas del primer ejercicio y activación ligera de la zona principal.")
        lines.append("")
        lines.append("| Ejercicio | Series | Repeticiones | Descanso | Intensidad | Observaciones técnicas |")
        lines.append("|---|---:|---:|---:|---|---|")

        day_exercises = []
        for body_part in day["muscle_groups"]:
            day_exercises.extend(pick_first_by_body(exercises, body_part, used, limit=1))

        for body_part in day["muscle_groups"]:
            if len(day_exercises) >= 5:
                break
            day_exercises.extend(pick_first_by_body(exercises, body_part, used, limit=1))

        for index, ex in enumerate(day_exercises[:6], start=1):
            if index <= 2:
                sets = 4 if level != "principiante" else 3
                reps = "6-10" if goal in {"ganar_musculo", "recomposicion"} else "8-12"
                rest = "120 s"
                intensity = "RIR 2"
            else:
                sets = 3
                reps = "10-15"
                rest = "60-90 s"
                intensity = "RIR 2-3"

            lines.append(
                f"| {ex['name']} | {sets} | {reps} | {rest} | {intensity} | "
                f"Controla la técnica y evita llegar al fallo en las primeras semanas. |"
            )

        lines.append("")
        lines.append("**Nota de ejecución:** prioriza recorrido controlado, postura estable y progresión de cargas solo cuando completes todas las repeticiones con buena técnica.")

    lines.append("")
    lines.append("## Progresión recomendada")
    lines.append("")
    lines.append(
        "Durante las primeras 4-6 semanas, mantén 1-3 repeticiones en recámara. "
        "Cuando completes el rango alto de repeticiones en todas las series con buena técnica, aumenta ligeramente la carga en la siguiente sesión. "
        "Si la fatiga se acumula demasiado, mantén la carga y reduce una serie en los accesorios."
    )

    lines.append("")
    lines.append("## Recomendaciones finales")
    lines.append("")
    lines.append("- Descansa al menos 24-48 horas entre sesiones exigentes del mismo grupo muscular.")
    lines.append("- Mantén una técnica consistente antes de subir peso.")
    lines.append("- Para recomposición, combina esta rutina con una ingesta alta en proteína y control moderado de calorías.")
    lines.append("- El cardio puede añadirse 2-3 días por semana en intensidad suave o moderada, sin interferir con la recuperación de piernas.")

    return "\n".join(lines)


# ============================================================
# VALIDACIÓN SIMPLE DE CALIDAD PARA PRUEBAS
# ============================================================

def evaluate_routine_quality(routine_text: str, selected_exercises: list[dict[str, Any]], user_data: dict[str, Any]) -> dict[str, Any]:
    """
    Evaluación automática simple. No sustituye la revisión humana,
    pero ayuda a detectar rutinas claramente malas.
    """
    text_lower = routine_text.lower()
    catalog_names = {ex["name"] for ex in selected_exercises}
    catalog_names_lower = {name.lower() for name in catalog_names}

    used_exercises = sorted([
        name for name in catalog_names
        if name.lower() in text_lower
    ])

    days_expected = user_data["training_context"]["days_per_week"]
    day_markers = 0
    for i in range(1, days_expected + 1):
        possible = [
            f"día {i}",
            f"dia {i}",
            f"day {i}",
            f"### día {i}",
            f"### dia {i}",
        ]
        if any(marker in text_lower for marker in possible):
            day_markers += 1

    required_sections = [
        "perfil interpretado",
        "objetivo de la planificación",
        "distribución semanal",
        "rutina detallada",
        "progresión recomendada",
        "recomendaciones finales",
    ]

    present_sections = [section for section in required_sections if section in text_lower]

    likely_invented_warning = False
    if len(used_exercises) < max(8, days_expected * 3):
        likely_invented_warning = True

    score = 0
    score += min(30, len(used_exercises) * 2)
    score += int((len(present_sections) / len(required_sections)) * 30)
    score += int((day_markers / max(days_expected, 1)) * 25)
    score += 15 if len(routine_text) > 2500 else 5 if len(routine_text) > 1200 else 0
    score = min(100, score)

    return {
        "quality_score_0_100": score,
        "expected_days": days_expected,
        "detected_day_markers": day_markers,
        "catalog_exercises_detected": len(used_exercises),
        "used_exercises_detected": used_exercises,
        "present_sections": present_sections,
        "missing_sections": [s for s in required_sections if s not in present_sections],
        "possible_issue": "Pocos ejercicios del catálogo detectados; revisar si la IA inventó ejercicios." if likely_invented_warning else "",
    }


# ============================================================
# GENERACIÓN
# ============================================================

def generate_professional_routine(catalog: list[dict[str, Any]], user_data: dict[str, Any]) -> tuple[str, list[dict[str, Any]], bool, str]:
    selected_exercises = select_prompt_exercises(catalog, user_data)

    try:
        messages = build_professional_prompt(user_data, selected_exercises)
        routine_text = call_ollama(messages)

        if len(routine_text.strip()) < 500:
            raise RuntimeError("La respuesta de la IA fue demasiado corta o incompleta.")

        return routine_text, selected_exercises, True, ""

    except Exception as exc:
        routine_text = build_local_professional_routine(user_data, selected_exercises)
        return routine_text, selected_exercises, False, str(exc)


def save_single_routine(text: str) -> None:
    Path(OUTPUT_ROUTINE_MD).write_text(text, encoding="utf-8")
    Path(OUTPUT_ROUTINE_TXT).write_text(text, encoding="utf-8")


# ============================================================
# MODO 10 PRUEBAS
# ============================================================

def build_test_profiles() -> list[dict[str, Any]]:
    return [
        make_user_data("Prueba_01_Principiante_Recomposicion", 22, "hombre", 185, 82, 30, 50, "recomposicion", 4, "principiante", ""),
        make_user_data("Prueba_02_Intermedio_Hipertrofia", 28, "hombre", 178, 76, 18, 43, "ganar_musculo", 5, "intermedio", ""),
        make_user_data("Prueba_03_Per pérdida grasa", 35, "mujer", 165, 72, 34, 34, "perder_grasa", 3, "principiante", ""),
        make_user_data("Prueba_04_Avanzado_6dias", 30, "hombre", 180, 88, 16, 55, "ganar_musculo", 6, "avanzado", ""),
        make_user_data("Prueba_05_Rodilla", 41, "hombre", 176, 90, 28, 48, "perder_grasa", 4, "intermedio", "Molestia de rodilla. Evitar saltos y ejercicios explosivos."),
        make_user_data("Prueba_06_Hombro", 26, "mujer", 170, 64, 24, 36, "recomposicion", 4, "intermedio", "Molestia de hombro. Evitar press militar pesado y movimientos overhead exigentes."),
        make_user_data("Prueba_07_Lumbar", 33, "hombre", 182, 84, 22, 50, "ganar_musculo", 3, "intermedio", "Molestias lumbares. Evitar peso muerto pesado y buenos días."),
        make_user_data("Prueba_08_Poco_tiempo", 24, "mujer", 160, 58, 27, 30, "recomposicion", 2, "principiante", "Quiere sesiones sencillas y no demasiado largas."),
        make_user_data("Prueba_09_7dias_suave", 45, "hombre", 174, 80, 25, 44, "perder_grasa", 7, "intermedio", "Prefiere entrenar muchos días pero con sesiones moderadas."),
        make_user_data("Prueba_10_1dia_fullbody", 21, "hombre", 188, 79, 20, 48, "ganar_musculo", 1, "principiante", ""),
    ]


def run_10_tests(catalog: list[dict[str, Any]]) -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = TEST_OUTPUT_DIR / f"run_{timestamp}"
    base_dir.mkdir(parents=True, exist_ok=True)

    profiles = build_test_profiles()
    summary_rows = []

    print(f"\nSe van a generar {len(profiles)} pruebas.")
    print(f"Carpeta de salida: {base_dir}\n")

    for idx, user_data in enumerate(profiles, start=1):
        test_name = user_data["user_profile"]["personal_data"]["name"]
        safe_name = f"{idx:02d}_{test_name}".replace(" ", "_").replace("/", "_")
        test_dir = base_dir / safe_name
        test_dir.mkdir(parents=True, exist_ok=True)

        print(f"[{idx}/10] Generando rutina para {test_name}...")

        routine_text, selected_exercises, used_ai, error_message = generate_professional_routine(catalog, user_data)
        quality = evaluate_routine_quality(routine_text, selected_exercises, user_data)

        (test_dir / "perfil_usuario.json").write_text(
            json.dumps(user_data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        (test_dir / "rutina_generada.md").write_text(routine_text, encoding="utf-8")
        (test_dir / "rutina_generada.txt").write_text(routine_text, encoding="utf-8")
        (test_dir / "ejercicios_enviados_a_ia.json").write_text(
            json.dumps(selected_exercises, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        (test_dir / "evaluacion_automatica.json").write_text(
            json.dumps(quality, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        summary_rows.append({
            "test": idx,
            "profile": test_name,
            "goal": user_data["goal"]["type"],
            "level": user_data["training_context"]["experience_level"],
            "days": user_data["training_context"]["days_per_week"],
            "used_ai": used_ai,
            "quality_score_0_100": quality["quality_score_0_100"],
            "detected_day_markers": quality["detected_day_markers"],
            "catalog_exercises_detected": quality["catalog_exercises_detected"],
            "possible_issue": quality["possible_issue"],
            "error_message": error_message,
            "folder": str(test_dir),
        })

        print(
            f"    Score: {quality['quality_score_0_100']}/100 | "
            f"Ejercicios detectados: {quality['catalog_exercises_detected']} | "
            f"IA: {'sí' if used_ai else 'fallback'}"
        )

    summary_json = base_dir / "resumen_pruebas.json"
    summary_json.write_text(json.dumps(summary_rows, indent=2, ensure_ascii=False), encoding="utf-8")

    summary_md = base_dir / "resumen_pruebas.md"
    lines = []
    lines.append("# Resumen de pruebas de generación de rutinas")
    lines.append("")
    lines.append("| Test | Perfil | Objetivo | Nivel | Días | IA | Score | Ejercicios detectados | Posible problema |")
    lines.append("|---:|---|---|---|---:|---|---:|---:|---|")
    for row in summary_rows:
        lines.append(
            f"| {row['test']} | {row['profile']} | {row['goal']} | {row['level']} | "
            f"{row['days']} | {'sí' if row['used_ai'] else 'fallback'} | "
            f"{row['quality_score_0_100']} | {row['catalog_exercises_detected']} | "
            f"{row['possible_issue']} |"
        )

    lines.append("")
    lines.append("## Cómo revisar")
    lines.append("")
    lines.append("Abre cada carpeta de prueba y revisa `rutina_generada.md`.")
    lines.append("La evaluación automática es solo orientativa; la revisión real debe comprobar coherencia profesional, selección de ejercicios, volumen, descansos y adaptación al perfil.")

    summary_md.write_text("\n".join(lines), encoding="utf-8")

    print("\nPruebas terminadas.")
    print(f"- Resumen JSON: {summary_json}")
    print(f"- Resumen Markdown: {summary_md}")


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    catalog = load_catalog()
    print(f"Catálogo cargado correctamente: {len(catalog)} ejercicios.\n")

    print("=== Generador inteligente de rutinas de entrenamiento ===\n")
    print("Selecciona modo:")
    print("1. Generar una rutina manual")
    print("2. Generar 10 pruebas automáticas")
    mode = ask_text("Modo (1/2): ", default="1")

    if mode == "2":
        run_10_tests(catalog)
        return

    user_data = build_manual_user_data()
    save_user_json(user_data)

    selected_exercises = select_prompt_exercises(catalog, user_data)

    print()
    print(
        f"Ejercicios enviados como base a la IA: {len(selected_exercises)} "
        f"(seleccionados desde {len(catalog)} ejercicios del catálogo completo)."
    )
    print("Generando rutina profesional con IA...\n")

    routine_text, selected_exercises, used_ai, error_message = generate_professional_routine(catalog, user_data)

    if not used_ai:
        print("La generación con IA falló o fue incompleta:")
        print(error_message)
        print("\nUsando generación local profesional basada en el catálogo.\n")

    Path(OUTPUT_RAW_AI).write_text(routine_text, encoding="utf-8")
    save_single_routine(routine_text)

    quality = evaluate_routine_quality(routine_text, selected_exercises, user_data)
    Path("evaluacion_automatica.json").write_text(
        json.dumps(quality, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("Rutina generada correctamente.")
    print(f"- {OUTPUT_ROUTINE_MD}")
    print(f"- {OUTPUT_ROUTINE_TXT}")
    print(f"- {OUTPUT_RAW_AI}")
    print(f"- evaluacion_automatica.json")
    print(f"\nEvaluación automática orientativa: {quality['quality_score_0_100']}/100")
    if quality["possible_issue"]:
        print(f"Aviso: {quality['possible_issue']}")

    print("\nVista previa:\n")
    print(routine_text)


if __name__ == "__main__":
    main()
