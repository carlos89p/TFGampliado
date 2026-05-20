import json
import re
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

OUTPUT_JSON = "manual_input_ai_ready.json"
OUTPUT_ROUTINE_JSON = "rutina_generada.json"
OUTPUT_ROUTINE_TXT = "rutina_generada.txt"

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen2.5:7b"

# No son los únicos ejercicios disponibles.
# El catálogo completo se carga, pero se preselecciona una parte manejable
# para no meter 2900 ejercicios completos en el prompt.
MAX_CANDIDATES_FOR_AI = 220




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


def save_json(data: dict, output_path: str = OUTPUT_JSON) -> None:
    Path(output_path).write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


# ============================================================
# CARGA Y FILTRADO DEL CATÁLOGO
# ============================================================

def find_catalog_path() -> Path:
    for path in CATALOG_PATHS:
        if path.exists():
            return path
    raise FileNotFoundError(
        "No se encontró exercises_catalog.json. Colócalo en una de estas rutas:\n"
        + "\n".join(str(p) for p in CATALOG_PATHS)
    )


def load_catalog() -> list[dict[str, Any]]:
    path = find_catalog_path()
    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, list):
        raise ValueError("El catálogo debe ser una lista de ejercicios JSON.")

    cleaned = []
    for item in data:
        if not isinstance(item, dict):
            continue

        name = str(item.get("name", "")).strip()
        exercise_id = str(item.get("exercise_id", "")).strip()

        if not name or not exercise_id:
            continue

        cleaned.append({
            "exercise_id": exercise_id,
            "name": name,
            "description": str(item.get("description", "") or "").strip(),
            "type": str(item.get("type", "") or "").strip(),
            "body_part": str(item.get("body_part", "") or "").strip(),
            "equipment": str(item.get("equipment", "") or "").strip(),
            "level": str(item.get("level", "") or "").strip(),
            "rating": float(item.get("rating", 0.0) or 0.0),
        })

    return cleaned


def map_user_level_to_catalog(level: str) -> list[str]:
    level = normalize_level(level)

    if level == "principiante":
        # El dataset tiene pocos Beginner. Dejamos entrar Intermediate para no quedarnos sin catálogo,
        # pero se priorizan Beginner en el ranking.
        return ["Beginner", "Intermediate"]

    if level == "intermedio":
        return ["Intermediate", "Beginner"]

    if level == "avanzado":
        return ["Intermediate", "Expert", "Beginner"]

    return ["Beginner", "Intermediate"]


def score_exercise(ex: dict[str, Any], user_data: dict[str, Any]) -> float:
    goal = user_data["goal"]["type"]
    level = user_data["training_context"]["experience_level"]
    notes = user_data["training_context"].get("free_text_notes", "").lower()

    score = 0.0

    # Valoración real del dataset
    score += float(ex.get("rating", 0.0) or 0.0)

    ex_type = ex.get("type", "")
    body_part = ex.get("body_part", "")
    equipment = ex.get("equipment", "")
    ex_level = ex.get("level", "")
    name = ex.get("name", "").lower()
    desc = ex.get("description", "").lower()

    allowed_levels = map_user_level_to_catalog(level)
    if ex_level in allowed_levels:
        score += 4

    if level == "principiante" and ex_level == "Beginner":
        score += 5
    elif level == "principiante" and ex_level == "Expert":
        score -= 20

    if ex_type == "Strength":
        score += 5
    elif ex_type in {"Cardio", "Plyometrics"} and goal == "perder_grasa":
        score += 3
    elif ex_type in {"Olympic Weightlifting", "Strongman"} and level == "principiante":
        score -= 15

    # Priorización general de músculos útiles para una rutina de gimnasio.
    if body_part in {"Chest", "Lats", "Middle Back", "Quadriceps", "Hamstrings", "Glutes", "Shoulders"}:
        score += 5
    elif body_part in {"Biceps", "Triceps", "Calves", "Abdominals", "Lower Back"}:
        score += 2

    # Evitar demasiado ruido del dataset para usuarios normales.
    noisy_prefixes = ("fyr", "fyr2", "hm ", "holman", "tyler", "metaburn", "30 ")
    if name.startswith(noisy_prefixes):
        score -= 8

    if "partner" in name or "partner" in desc:
        score -= 10

    # Restricciones simples por texto libre.
    if "hombro" in notes or "shoulder" in notes:
        if body_part == "Shoulders" or "overhead" in name or "shoulder press" in name:
            score -= 20

    if "rodilla" in notes or "knee" in notes:
        if body_part == "Quadriceps" and any(w in name for w in ["jump", "lunge", "squat", "plyo"]):
            score -= 15

    if "espalda" in notes or "lumbar" in notes or "lower back" in notes:
        if body_part == "Lower Back" or "deadlift" in name or "good morning" in name:
            score -= 15

    if not ex.get("description"):
        score -= 1

    if not equipment:
        score -= 1

    return score


def select_candidates(catalog: list[dict[str, Any]], user_data: dict[str, Any]) -> list[dict[str, Any]]:
    allowed_levels = map_user_level_to_catalog(user_data["training_context"]["experience_level"])

    filtered = [
        ex for ex in catalog
        if ex.get("level") in allowed_levels
        and ex.get("type") in {
            "Strength",
            "Cardio",
            "Plyometrics",
            "Powerlifting",
            "Stretching",
            "Olympic Weightlifting",
            "Strongman",
        }
    ]

    ranked = sorted(
        filtered,
        key=lambda ex: score_exercise(ex, user_data),
        reverse=True
    )

    # Garantizamos variedad por grupo muscular para que no salgan 200 abdominales.
    target_body_parts = [
        "Chest", "Lats", "Middle Back", "Shoulders",
        "Quadriceps", "Hamstrings", "Glutes",
        "Biceps", "Triceps", "Calves", "Abdominals", "Lower Back"
    ]

    selected = []
    used_ids = set()

    per_body_part_limit = max(8, MAX_CANDIDATES_FOR_AI // max(len(target_body_parts), 1))

    for body_part in target_body_parts:
        count = 0
        for ex in ranked:
            if ex["exercise_id"] in used_ids:
                continue
            if ex.get("body_part") != body_part:
                continue
            selected.append(ex)
            used_ids.add(ex["exercise_id"])
            count += 1
            if count >= per_body_part_limit:
                break

    # Relleno con los mejores restantes.
    for ex in ranked:
        if len(selected) >= MAX_CANDIDATES_FOR_AI:
            break
        if ex["exercise_id"] not in used_ids:
            selected.append(ex)
            used_ids.add(ex["exercise_id"])

    return selected[:MAX_CANDIDATES_FOR_AI]


# ============================================================
# OLLAMA
# ============================================================

def call_ollama(messages: list[dict[str, str]], model: str = OLLAMA_MODEL) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.2,
            "num_ctx": 12000,
        }
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=240) as response:
            raw = response.read().decode("utf-8")
            obj = json.loads(raw)
            return obj["message"]["content"]
    except urllib.error.URLError as exc:
        raise RuntimeError(
            "No se pudo conectar con Ollama. Comprueba que Ollama está abierto y funcionando."
        ) from exc


# ============================================================
# EXTRACCIÓN Y NORMALIZACIÓN JSON
# ============================================================

def try_json_loads(text: str) -> Any:
    text = text.strip()

    # Intento directo
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Quitar fences si el modelo los mete
    text = re.sub(r"^```(?:json)?", "", text.strip(), flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text.strip()).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Buscar todos los bloques JSON posibles y devolver el primero válido.
    candidates = []

    for start_char, end_char in [("{", "}"), ("[", "]")]:
        starts = [i for i, ch in enumerate(text) if ch == start_char]
        for start in starts:
            depth = 0
            in_string = False
            escape = False
            for i in range(start, len(text)):
                ch = text[i]

                if escape:
                    escape = False
                    continue

                if ch == "\\":
                    escape = True
                    continue

                if ch == '"':
                    in_string = not in_string
                    continue

                if in_string:
                    continue

                if ch == start_char:
                    depth += 1
                elif ch == end_char:
                    depth -= 1
                    if depth == 0:
                        candidates.append(text[start:i + 1])
                        break

    for candidate in sorted(candidates, key=len, reverse=True):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    raise ValueError("No se pudo extraer un JSON válido de la respuesta del modelo.")


def normalize_routine_object(obj: Any) -> dict[str, Any]:
    """
    Evita el error:
    AttributeError: 'list' object has no attribute 'get'

    Algunos modelos devuelven directamente una lista de días.
    Este método la convierte a la estructura esperada.
    """
    if isinstance(obj, dict):
        if "days" in obj and isinstance(obj["days"], list):
            return obj

        # Posibles nombres alternativos
        for key in ["routine", "rutina", "workout_plan", "plan"]:
            if key in obj:
                return normalize_routine_object(obj[key])

        # Si el objeto ya parece un día único
        if "exercises" in obj:
            return {
                "routine_name": "Rutina generada",
                "objective": "",
                "days": [obj],
                "general_notes": []
            }

        return obj

    if isinstance(obj, list):
        return {
            "routine_name": "Rutina generada",
            "objective": "",
            "days": obj,
            "general_notes": []
        }

    raise ValueError("La rutina generada no tiene formato JSON válido.")


# ============================================================
# PROMPTS
# ============================================================

def build_generation_prompt(user_data: dict[str, Any], candidates: list[dict[str, Any]]) -> list[dict[str, str]]:
    days_per_week = user_data["training_context"]["days_per_week"]
    candidate_min = [
        {
            "exercise_id": ex["exercise_id"],
            "name": ex["name"],
            "type": ex["type"],
            "body_part": ex["body_part"],
            "equipment": ex["equipment"],
            "level": ex["level"],
            "rating": ex["rating"],
        }
        for ex in candidates
    ]

    system = f"""
Eres un asistente experto en entrenamiento de gimnasio.

Tu tarea es generar una rutina personalizada y coherente usando conocimiento general de entrenamiento,
pero con una restricción obligatoria:

SOLO puedes usar ejercicios que estén en la lista de ejercicios candidatos.
No puedes inventar ejercicios.
No puedes cambiar el nombre de los ejercicios.
Cada ejercicio debe incluir exactamente el exercise_id de la lista.

Devuelve únicamente JSON válido.
No incluyas explicaciones fuera del JSON.
No devuelvas Markdown.
No devuelvas una lista suelta; devuelve un objeto JSON con la clave "days".

Estructura obligatoria:

{{
  "routine_name": "string",
  "objective": "string",
  "days": [
    {{
      "day": 1,
      "name": "string",
      "focus": "string",
      "exercises": [
        {{
          "exercise_id": "string",
          "name": "string",
          "sets": 3,
          "reps": "8-12",
          "rest_seconds": 90,
          "notes": "string"
        }}
      ]
    }}
  ],
  "general_notes": ["string"]
}}

Reglas:
- Debe haber exactamente {days_per_week} días.
- Para principiantes: usa volumen moderado, técnica sencilla y evita rutinas extremas.
- Para recomposición: combina fuerza/hipertrofia con distribución equilibrada.
- Para perder grasa: la rutina sigue siendo de fuerza, puede añadir trabajo metabólico moderado.
- Para ganar músculo: prioriza hipertrofia, 3-4 series, 8-15 repeticiones.
- Para ganar fuerza: más básicos, descansos más altos y repeticiones más bajas.
- No uses más de 7 ejercicios por día.
- No uses menos de 4 ejercicios por día salvo que solo haya 1-2 días.
- Evita repetir el mismo ejercicio en varios días salvo abdominales o casos justificados.
- Respeta lesiones, molestias o ejercicios a evitar indicados por el usuario.
"""

    user = {
        "user_data": user_data,
        "available_exercises": candidate_min,
    }

    return [
        {"role": "system", "content": system.strip()},
        {"role": "user", "content": json.dumps(user, indent=2, ensure_ascii=False)},
    ]


def build_repair_prompt(
    bad_routine: dict[str, Any],
    errors: list[str],
    user_data: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> list[dict[str, str]]:
    candidate_min = [
        {
            "exercise_id": ex["exercise_id"],
            "name": ex["name"],
            "type": ex["type"],
            "body_part": ex["body_part"],
            "equipment": ex["equipment"],
            "level": ex["level"],
            "rating": ex["rating"],
        }
        for ex in candidates
    ]

    system = """
Corrige una rutina de entrenamiento JSON.

Devuelve únicamente JSON válido.
No incluyas texto fuera del JSON.
No devuelvas una lista suelta; devuelve un objeto con la clave "days".

Restricciones:
- Usa solo exercise_id existentes en available_exercises.
- Mantén exactamente el número de días solicitado por el usuario.
- Corrige todos los errores indicados.
"""

    user = {
        "user_data": user_data,
        "available_exercises": candidate_min,
        "bad_routine": bad_routine,
        "errors_to_fix": errors,
    }

    return [
        {"role": "system", "content": system.strip()},
        {"role": "user", "content": json.dumps(user, indent=2, ensure_ascii=False)},
    ]


# ============================================================
# VALIDACIÓN
# ============================================================

def validate_routine(
    routine: Any,
    candidates: list[dict[str, Any]],
    user_data: dict[str, Any],
) -> tuple[bool, list[str]]:
    errors = []

    try:
        routine = normalize_routine_object(routine)
    except Exception as exc:
        return False, [str(exc)]

    if not isinstance(routine, dict):
        return False, ["La rutina debe ser un objeto JSON."]

    days = routine.get("days")
    if not isinstance(days, list):
        return False, ["La rutina debe tener una clave 'days' con una lista de días."]

    expected_days = user_data["training_context"]["days_per_week"]
    if len(days) != expected_days:
        errors.append(f"La rutina debe tener exactamente {expected_days} días, pero tiene {len(days)}.")

    valid_by_id = {ex["exercise_id"]: ex for ex in candidates}
    valid_by_name = {ex["name"].strip().lower(): ex for ex in candidates}

    used_ids = set()

    for day_index, day in enumerate(days, start=1):
        if not isinstance(day, dict):
            errors.append(f"El día {day_index} no es un objeto JSON.")
            continue

        exercises = day.get("exercises")
        if not isinstance(exercises, list):
            errors.append(f"El día {day_index} no tiene una lista válida de ejercicios.")
            continue

        if len(exercises) < 3:
            errors.append(f"El día {day_index} tiene muy pocos ejercicios.")
        if len(exercises) > 8:
            errors.append(f"El día {day_index} tiene demasiados ejercicios.")

        for ex_index, item in enumerate(exercises, start=1):
            if not isinstance(item, dict):
                errors.append(f"Ejercicio {ex_index} del día {day_index} no es objeto JSON.")
                continue

            exercise_id = str(item.get("exercise_id", "")).strip()
            name = str(item.get("name", "")).strip()

            if exercise_id not in valid_by_id:
                # Intento de corrección por nombre exacto
                found = valid_by_name.get(name.lower())
                if found:
                    item["exercise_id"] = found["exercise_id"]
                    item["name"] = found["name"]
                    exercise_id = found["exercise_id"]
                else:
                    errors.append(
                        f"Ejercicio no válido en día {day_index}: "
                        f"exercise_id='{exercise_id}', name='{name}'."
                    )
                    continue

            catalog_ex = valid_by_id[exercise_id]

            if name and name.strip().lower() != catalog_ex["name"].strip().lower():
                item["name"] = catalog_ex["name"]

            if exercise_id in used_ids:
                # Repetir alguno no es fatal, pero lo marcamos para reparación.
                errors.append(f"Ejercicio repetido: {catalog_ex['name']} ({exercise_id}).")
            used_ids.add(exercise_id)

            # Campos mínimos
            item.setdefault("sets", 3)
            item.setdefault("reps", "8-12")
            item.setdefault("rest_seconds", 90)
            item.setdefault("notes", "")

    return len(errors) == 0, errors


def fallback_routine(user_data: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Rutina de emergencia si el modelo falla dos veces.
    No es tan creativa como la IA, pero garantiza una salida válida con ejercicios del catálogo.
    """
    days = user_data["training_context"]["days_per_week"]

    split_templates = {
        1: [["Chest", "Lats", "Quadriceps", "Hamstrings", "Shoulders", "Abdominals"]],
        2: [
            ["Chest", "Shoulders", "Triceps", "Abdominals"],
            ["Quadriceps", "Hamstrings", "Glutes", "Lats", "Middle Back"],
        ],
        3: [
            ["Chest", "Shoulders", "Triceps"],
            ["Lats", "Middle Back", "Biceps"],
            ["Quadriceps", "Hamstrings", "Glutes", "Abdominals"],
        ],
        4: [
            ["Chest", "Shoulders", "Triceps"],
            ["Lats", "Middle Back", "Biceps"],
            ["Quadriceps", "Glutes", "Calves"],
            ["Hamstrings", "Lower Back", "Abdominals"],
        ],
        5: [
            ["Chest", "Triceps"],
            ["Lats", "Middle Back", "Biceps"],
            ["Quadriceps", "Glutes"],
            ["Shoulders", "Abdominals"],
            ["Hamstrings", "Calves", "Lower Back"],
        ],
        6: [
            ["Chest", "Triceps"],
            ["Lats", "Biceps"],
            ["Quadriceps", "Glutes"],
            ["Shoulders", "Abdominals"],
            ["Hamstrings", "Calves"],
            ["Middle Back", "Lower Back", "Abdominals"],
        ],
        7: [
            ["Chest", "Triceps"],
            ["Lats", "Biceps"],
            ["Quadriceps", "Glutes"],
            ["Shoulders"],
            ["Hamstrings", "Calves"],
            ["Middle Back", "Lower Back"],
            ["Abdominals", "Glutes"],
        ],
    }

    templates = split_templates.get(days, split_templates[3])
    by_body = {}
    for ex in candidates:
        by_body.setdefault(ex["body_part"], []).append(ex)

    used = set()
    routine_days = []

    for i, focus_parts in enumerate(templates, start=1):
        exercises = []
        for part in focus_parts:
            for ex in by_body.get(part, []):
                if ex["exercise_id"] in used:
                    continue
                exercises.append({
                    "exercise_id": ex["exercise_id"],
                    "name": ex["name"],
                    "sets": 3,
                    "reps": "8-12",
                    "rest_seconds": 90,
                    "notes": f"Ejercicio seleccionado del catálogo para trabajar {part}."
                })
                used.add(ex["exercise_id"])
                break

        # Rellenar si faltan ejercicios
        for ex in candidates:
            if len(exercises) >= 5:
                break
            if ex["exercise_id"] not in used:
                exercises.append({
                    "exercise_id": ex["exercise_id"],
                    "name": ex["name"],
                    "sets": 3,
                    "reps": "10-12",
                    "rest_seconds": 90,
                    "notes": "Ejercicio complementario seleccionado del catálogo."
                })
                used.add(ex["exercise_id"])

        routine_days.append({
            "day": i,
            "name": f"Día {i}",
            "focus": ", ".join(focus_parts),
            "exercises": exercises,
        })

    return {
        "routine_name": "Rutina generada con selección validada",
        "objective": user_data["goal"]["type"],
        "days": routine_days,
        "general_notes": [
            "Rutina creada usando únicamente ejercicios existentes en el catálogo.",
            "Ajusta cargas según técnica, fatiga y nivel real del usuario.",
        ],
    }


# ============================================================
# SALIDA
# ============================================================

def format_routine_text(routine: dict[str, Any]) -> str:
    lines = []
    lines.append(f"# {routine.get('routine_name', 'Rutina generada')}")
    lines.append("")
    lines.append(f"Objetivo: {routine.get('objective', '')}")
    lines.append("")

    for day in routine.get("days", []):
        lines.append(f"## Día {day.get('day', '')}: {day.get('name', '')}")
        lines.append(f"Enfoque: {day.get('focus', '')}")
        lines.append("")

        for ex in day.get("exercises", []):
            lines.append(
                f"- {ex.get('name')} "
                f"({ex.get('sets')} series x {ex.get('reps')} reps, "
                f"descanso {ex.get('rest_seconds')}s)"
            )
            if ex.get("notes"):
                lines.append(f"  - Nota: {ex.get('notes')}")

        lines.append("")

    notes = routine.get("general_notes", [])
    if notes:
        lines.append("## Notas generales")
        for note in notes:
            lines.append(f"- {note}")

    return "\n".join(lines)


def save_routine_outputs(routine: dict[str, Any]) -> None:
    Path(OUTPUT_ROUTINE_JSON).write_text(
        json.dumps(routine, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    Path(OUTPUT_ROUTINE_TXT).write_text(
        format_routine_text(routine),
        encoding="utf-8"
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    catalog = load_catalog()
    print(f"Catálogo cargado correctamente: {len(catalog)} ejercicios.\n")

    print("=== Generador inteligente de rutinas de entrenamiento ===\n")

    user_data = build_manual_user_data()
    save_json(user_data)

    candidates = select_candidates(catalog, user_data)

    print()
    print(
        f"Ejercicios candidatos preseleccionados para la IA: {len(candidates)} "
        f"(de {len(catalog)} ejercicios del catálogo completo)."
    )
    print("Nota: no son los únicos ejercicios disponibles; es una preselección para que el modelo trabaje mejor.")
    print("Generando rutina con IA...\n")

    routine = None
    errors = []

    try:
        response = call_ollama(build_generation_prompt(user_data, candidates))
        routine = normalize_routine_object(try_json_loads(response))
        valid, errors = validate_routine(routine, candidates, user_data)

        if not valid:
            print("La primera rutina tenía errores. Intentando corregir una vez...")
            repair_response = call_ollama(build_repair_prompt(routine, errors, user_data, candidates))
            routine = normalize_routine_object(try_json_loads(repair_response))
            valid, errors = validate_routine(routine, candidates, user_data)

        if not valid:
            print("\nLa IA no devolvió una rutina totalmente válida.")
            print("Errores detectados:")
            for err in errors[:10]:
                print(f"- {err}")
            print("\nUsando rutina fallback validada con el catálogo.")
            routine = fallback_routine(user_data, candidates)

    except Exception as exc:
        print("\nError durante la generación con IA:")
        print(str(exc))
        print("\nUsando rutina fallback validada con el catálogo.")
        routine = fallback_routine(user_data, candidates)

    routine = normalize_routine_object(routine)
    save_routine_outputs(routine)

    print("\nRutina generada correctamente.")
    print(f"- {OUTPUT_ROUTINE_JSON}")
    print(f"- {OUTPUT_ROUTINE_TXT}")
    print("\nVista previa:\n")
    print(format_routine_text(routine))


if __name__ == "__main__":
    main()
