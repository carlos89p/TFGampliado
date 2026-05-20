"""
Generador profesional de rutinas de gimnasio con IA.

Características:
- Usa el formulario existente de procesamiento_manual.py.
- Permite crear un formulario nuevo o reutilizar manual_input_ai_ready.json si existe.
- Carga el catálogo cerrado de ejercicios desde processed_context/exercises_catalog.json.
- La IA analiza el perfil, estructura la rutina y selecciona ejercicios del catálogo.
- Valida que todos los ejercicios existan realmente en el catálogo.
- Exporta la rutina final en JSON y Markdown.

Requisitos:
- Python 3.10+
- Ollama instalado y ejecutándose.
- Un modelo local disponible, por ejemplo: qwen2.5:14b.

Ejecución:
    python main.py
    python main.py --model qwen2.5:14b
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from procesamiento_manual import build_manual_user_data, save_json as save_user_json


# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
USER_JSON_PATH = BASE_DIR / "manual_input_ai_ready.json"

CATALOG_PATHS = [
    BASE_DIR / "processed_context" / "exercises_catalog.json",
    BASE_DIR / "context" / "exercises_catalog.json",
    BASE_DIR / "exercises_catalog.json",
]

OUTPUT_DIR = BASE_DIR / "rutinas_generadas"
OLLAMA_URL = "http://localhost:11434/api/chat"
DEFAULT_MODEL = "qwen2.5:14b"

MAX_EXERCISES_FOR_PROMPT = 260
MIN_EXERCISES_PER_DAY = 5
MAX_EXERCISES_PER_DAY = 8

MAIN_BODY_PARTS = [
    "Chest", "Lats", "Middle Back", "Shoulders", "Quadriceps", "Hamstrings",
    "Glutes", "Biceps", "Triceps", "Calves", "Abdominals", "Lower Back",
]

NOISY_NAME_PATTERNS = [
    "partner", "fyr", "metaburn", "tyler", "holman", "30 ", "360 ",
]


# ============================================================
# UTILIDADES BÁSICAS
# ============================================================

def normalize_text(text: Any) -> str:
    return str(text or "").strip().lower()


def slugify(text: str) -> str:
    text = normalize_text(text)
    text = re.sub(r"[^a-z0-9áéíóúüñ]+", "_", text, flags=re.IGNORECASE)
    text = text.strip("_")
    return text or "rutina"


def ask_yes_no(question: str, default: str = "s") -> bool:
    default = default.lower().strip()
    suffix = "[s/n]" if default not in {"s", "n"} else f"[{'S' if default == 's' else 's'}/{'N' if default == 'n' else 'n'}]"

    while True:
        answer = input(f"{question} {suffix}: ").strip().lower()
        if not answer:
            answer = default
        if answer in {"s", "si", "sí", "y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Responde 's' o 'n'.")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ============================================================
# DATOS DEL USUARIO
# ============================================================

def get_user_data() -> dict[str, Any]:
    print("\n=== Datos del usuario ===")

    if USER_JSON_PATH.exists():
        print(f"Se ha encontrado un formulario existente: {USER_JSON_PATH.name}")
        use_existing = ask_yes_no("¿Quieres usar ese JSON existente?", default="s")
        if use_existing:
            data = read_json(USER_JSON_PATH)
            print("Datos cargados correctamente.\n")
            return data

        print("Se abrirá el formulario manual para crear nuevos datos.\n")
    else:
        print("No existe manual_input_ai_ready.json. Se abrirá el formulario manual.\n")

    data = build_manual_user_data()
    save_user_json(data, str(USER_JSON_PATH))
    print(f"\nFormulario guardado en: {USER_JSON_PATH.name}\n")
    return data


# ============================================================
# CATÁLOGO
# ============================================================

def find_catalog_path() -> Path:
    for path in CATALOG_PATHS:
        if path.exists():
            return path
    raise FileNotFoundError(
        "No se encontró el catálogo de ejercicios. Debe existir en processed_context/exercises_catalog.json."
    )


def load_catalog() -> list[dict[str, Any]]:
    path = find_catalog_path()
    raw = read_json(path)
    if not isinstance(raw, list):
        raise ValueError("El catálogo debe ser una lista de ejercicios.")

    catalog: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for item in raw:
        if not isinstance(item, dict):
            continue

        exercise_id = str(item.get("exercise_id", "")).strip()
        name = str(item.get("name", "")).strip()
        if not exercise_id or not name or exercise_id in seen_ids:
            continue

        seen_ids.add(exercise_id)
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

    if not catalog:
        raise ValueError("El catálogo existe, pero no contiene ejercicios válidos.")

    return catalog


def build_catalog_indexes(catalog: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_id = {ex["exercise_id"]: ex for ex in catalog}
    by_name = {normalize_text(ex["name"]): ex for ex in catalog}
    return {"by_id": by_id, "by_name": by_name}


# ============================================================
# PERFIL Y SELECCIÓN DE CANDIDATOS PARA LA IA
# ============================================================

def get_nested(data: dict[str, Any], path: list[str], default: Any = None) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def user_level(user_data: dict[str, Any]) -> str:
    return normalize_text(get_nested(user_data, ["training_context", "experience_level"], "principiante"))


def user_goal(user_data: dict[str, Any]) -> str:
    return normalize_text(get_nested(user_data, ["goal", "type"], "recomposicion"))


def user_notes(user_data: dict[str, Any]) -> str:
    return normalize_text(get_nested(user_data, ["training_context", "free_text_notes"], ""))


def user_days(user_data: dict[str, Any]) -> int:
    value = get_nested(user_data, ["training_context", "days_per_week"], 3)
    try:
        return max(1, min(7, int(value)))
    except (TypeError, ValueError):
        return 3


def allowed_catalog_levels(level: str) -> set[str]:
    if level == "principiante":
        return {"Beginner", "Intermediate"}
    if level == "intermedio":
        return {"Beginner", "Intermediate"}
    if level == "avanzado":
        return {"Beginner", "Intermediate", "Expert"}
    return {"Beginner", "Intermediate"}


def exercise_penalty_from_notes(ex: dict[str, Any], notes: str) -> int:
    name = normalize_text(ex["name"])
    body = ex["body_part"]
    penalty = 0

    if any(word in notes for word in ["hombro", "shoulder", "manguito", "rotador"]):
        if body == "Shoulders" or any(word in name for word in ["overhead", "shoulder press", "upright row", "behind the neck"]):
            penalty += 35

    if any(word in notes for word in ["rodilla", "knee", "menisco", "rotula", "rótula"]):
        if any(word in name for word in ["jump", "lunge", "pistol", "sissy", "plyo"]):
            penalty += 35
        if body == "Quadriceps" and any(word in name for word in ["squat", "step-up"]):
            penalty += 15

    if any(word in notes for word in ["lumbar", "espalda baja", "lower back", "hernia", "ciatica", "ciática"]):
        if body == "Lower Back" or any(word in name for word in ["deadlift", "good morning", "hyperextension"]):
            penalty += 35

    if any(word in notes for word in ["codo", "elbow"]):
        if any(word in name for word in ["skullcrusher", "extension", "curl"]):
            penalty += 15

    return penalty


def score_exercise(ex: dict[str, Any], user_data: dict[str, Any]) -> float:
    level = user_level(user_data)
    goal = user_goal(user_data)
    notes = user_notes(user_data)

    score = 0.0
    score += ex.get("rating", 0.0) * 1.5

    if ex["level"] in allowed_catalog_levels(level):
        score += 12
    if level == "principiante" and ex["level"] == "Beginner":
        score += 10
    if level == "principiante" and ex["level"] == "Expert":
        score -= 50

    if ex["type"] == "Strength":
        score += 18
    elif goal == "perder_grasa" and ex["type"] in {"Cardio", "Plyometrics"}:
        score += 8
    elif ex["type"] in {"Olympic Weightlifting", "Strongman"}:
        score -= 15

    if ex["body_part"] in MAIN_BODY_PARTS:
        score += 8

    equipment = ex["equipment"]
    if equipment in {"Machine", "Cable", "Dumbbell", "Body Only"}:
        score += 6
    if level == "principiante" and equipment in {"Barbell", "Kettlebells"}:
        score -= 2

    name = normalize_text(ex["name"])
    if any(name.startswith(pattern) or pattern in name for pattern in NOISY_NAME_PATTERNS):
        score -= 14

    if not ex["description"]:
        score -= 3

    score -= exercise_penalty_from_notes(ex, notes)
    return score


def select_exercises_for_prompt(catalog: list[dict[str, Any]], user_data: dict[str, Any]) -> list[dict[str, Any]]:
    allowed_levels = allowed_catalog_levels(user_level(user_data))

    filtered = [
        ex for ex in catalog
        if ex["level"] in allowed_levels
        and ex["type"] in {"Strength", "Cardio", "Plyometrics", "Powerlifting", "Stretching"}
        and ex["body_part"] in MAIN_BODY_PARTS
    ]

    ranked = sorted(filtered, key=lambda ex: score_exercise(ex, user_data), reverse=True)

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    per_body_part = max(12, MAX_EXERCISES_FOR_PROMPT // len(MAIN_BODY_PARTS))

    for body_part in MAIN_BODY_PARTS:
        count = 0
        for ex in ranked:
            if ex["exercise_id"] in selected_ids:
                continue
            if ex["body_part"] != body_part:
                continue
            selected.append(ex)
            selected_ids.add(ex["exercise_id"])
            count += 1
            if count >= per_body_part:
                break

    for ex in ranked:
        if len(selected) >= MAX_EXERCISES_FOR_PROMPT:
            break
        if ex["exercise_id"] not in selected_ids:
            selected.append(ex)
            selected_ids.add(ex["exercise_id"])

    return selected[:MAX_EXERCISES_FOR_PROMPT]


def professional_split(days: int) -> list[dict[str, Any]]:
    splits = {
        1: [
            ("Full Body", ["Chest", "Lats", "Quadriceps", "Hamstrings", "Shoulders", "Abdominals"]),
        ],
        2: [
            ("Torso", ["Chest", "Lats", "Middle Back", "Shoulders", "Biceps", "Triceps"]),
            ("Pierna y core", ["Quadriceps", "Hamstrings", "Glutes", "Calves", "Abdominals"]),
        ],
        3: [
            ("Push", ["Chest", "Shoulders", "Triceps"]),
            ("Pull", ["Lats", "Middle Back", "Biceps"]),
            ("Pierna y core", ["Quadriceps", "Hamstrings", "Glutes", "Calves", "Abdominals"]),
        ],
        4: [
            ("Torso A", ["Chest", "Lats", "Shoulders", "Triceps"]),
            ("Pierna A", ["Quadriceps", "Glutes", "Hamstrings", "Calves"]),
            ("Torso B", ["Middle Back", "Lats", "Chest", "Biceps", "Shoulders"]),
            ("Pierna B + core", ["Hamstrings", "Glutes", "Quadriceps", "Abdominals"]),
        ],
        5: [
            ("Pecho y tríceps", ["Chest", "Triceps"]),
            ("Espalda y bíceps", ["Lats", "Middle Back", "Biceps"]),
            ("Pierna completa", ["Quadriceps", "Hamstrings", "Glutes", "Calves"]),
            ("Hombro y core", ["Shoulders", "Abdominals"]),
            ("Full Body técnico", ["Chest", "Lats", "Quadriceps", "Glutes", "Abdominals"]),
        ],
        6: [
            ("Push A", ["Chest", "Shoulders", "Triceps"]),
            ("Pull A", ["Lats", "Middle Back", "Biceps"]),
            ("Pierna A", ["Quadriceps", "Glutes", "Calves"]),
            ("Push B", ["Chest", "Shoulders", "Triceps"]),
            ("Pull B", ["Lats", "Middle Back", "Biceps"]),
            ("Pierna B + core", ["Hamstrings", "Glutes", "Abdominals"]),
        ],
        7: [
            ("Push A", ["Chest", "Shoulders", "Triceps"]),
            ("Pull A", ["Lats", "Middle Back", "Biceps"]),
            ("Pierna A", ["Quadriceps", "Glutes", "Calves"]),
            ("Core y movilidad", ["Abdominals", "Lower Back"]),
            ("Push B", ["Chest", "Shoulders", "Triceps"]),
            ("Pull B", ["Lats", "Middle Back", "Biceps"]),
            ("Pierna B", ["Hamstrings", "Glutes", "Quadriceps"]),
        ],
    }

    return [
        {"day": i + 1, "name": name, "target_body_parts": parts}
        for i, (name, parts) in enumerate(splits.get(days, splits[3]))
    ]


# ============================================================
# OLLAMA
# ============================================================

def call_ollama(messages: list[dict[str, str]], model: str, temperature: float = 0.15) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": temperature,
            "num_ctx": 24000,
            "num_predict": 7000,
        },
    }

    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=360) as response:
            raw = response.read().decode("utf-8")
            data = json.loads(raw)
            return data["message"]["content"]
    except urllib.error.URLError as exc:
        raise RuntimeError(
            "No se pudo conectar con Ollama. Abre Ollama y comprueba que el modelo está instalado."
        ) from exc
    except KeyError as exc:
        raise RuntimeError("Ollama respondió con un formato inesperado.") from exc


def extract_json(text: str) -> Any:
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    starts = [i for i, char in enumerate(text) if char in "{["]
    for start in starts:
        opening = text[start]
        closing = "}" if opening == "{" else "]"
        depth = 0
        in_string = False
        escape = False
        for end in range(start, len(text)):
            char = text[end]
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == opening:
                depth += 1
            elif char == closing:
                depth -= 1
                if depth == 0:
                    candidate = text[start:end + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break

    raise ValueError("La IA no devolvió un JSON válido.")


# ============================================================
# PROMPT
# ============================================================

def build_prompt(user_data: dict[str, Any], selected_exercises: list[dict[str, Any]]) -> list[dict[str, str]]:
    days = user_days(user_data)
    split = professional_split(days)

    compact_catalog = [
        {
            "exercise_id": ex["exercise_id"],
            "name": ex["name"],
            "type": ex["type"],
            "body_part": ex["body_part"],
            "equipment": ex["equipment"],
            "level": ex["level"],
            "rating": ex["rating"],
        }
        for ex in selected_exercises
    ]

    system = """
Eres un entrenador personal profesional y un generador estricto de JSON.
Tu tarea es crear una rutina de gimnasio completa, coherente y aplicable en la vida real.

La IA debe tomar las decisiones principales: analizar el perfil, elegir estructura semanal, escoger ejercicios del catálogo, ajustar volumen, intensidad, descansos y progresión.

REGLAS OBLIGATORIAS:
1. Responde SOLO con JSON válido. Sin Markdown, sin comentarios externos.
2. Usa exclusivamente ejercicios presentes en el catálogo recibido.
3. Cada ejercicio debe incluir un exercise_id real del catálogo y el name exacto del catálogo.
4. No inventes ejercicios, máquinas, nombres ni IDs.
5. La rutina debe tener exactamente los días de entrenamiento indicados por el usuario.
6. Cada día debe tener entre 5 y 8 ejercicios.
7. Ordena los ejercicios como lo haría un entrenador: básicos/compuestos primero, accesorios después, core o aislamiento al final.
8. Ajusta series, repeticiones, descanso y RIR según objetivo y nivel.
9. Si el usuario indica lesiones, molestias o restricciones, evita ejercicios incompatibles.
10. La rutina debe ser profesional, no una lista genérica.

ESQUEMA EXACTO DE SALIDA:
{
  "routine_name": "string",
  "created_at": "YYYY-MM-DDTHH:MM:SS",
  "user_summary": {
    "goal": "string",
    "level": "string",
    "days_per_week": 0,
    "important_notes": "string"
  },
  "professional_assessment": "string",
  "weekly_structure": "string",
  "days": [
    {
      "day": 1,
      "name": "string",
      "focus": "string",
      "exercises": [
        {
          "exercise_id": "string",
          "name": "string",
          "body_part": "string",
          "equipment": "string",
          "sets": 0,
          "reps": "string",
          "rest_seconds": 0,
          "rir": "string",
          "tempo": "string",
          "notes": "string"
        }
      ]
    }
  ],
  "weekly_progression": ["string"],
  "warmup": ["string"],
  "cooldown": ["string"],
  "safety_notes": ["string"],
  "trainer_notes": ["string"]
}
""".strip()

    user = {
        "profile": user_data,
        "required_training_days": days,
        "recommended_split_reference": split,
    }

    prompt = {
        "user_data": user,
        "closed_exercise_catalog": compact_catalog,
        "instruction": "Genera la rutina profesional final usando solo ejercicios del catálogo cerrado.",
    }

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
    ]


# ============================================================
# VALIDACIÓN Y REPARACIÓN CONTROLADA
# ============================================================

def normalize_routine(raw: Any, user_data: dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw, dict) and isinstance(raw.get("days"), list):
        routine = raw
    elif isinstance(raw, dict) and isinstance(raw.get("routine"), dict):
        routine = raw["routine"]
    elif isinstance(raw, list):
        routine = {"days": raw}
    else:
        raise ValueError("La IA generó una estructura que no contiene una lista válida de días.")

    routine.setdefault("routine_name", "Rutina profesional generada con IA")
    routine.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
    routine.setdefault("user_summary", {})
    routine.setdefault("professional_assessment", "")
    routine.setdefault("weekly_structure", "")
    routine.setdefault("weekly_progression", [])
    routine.setdefault("warmup", [])
    routine.setdefault("cooldown", [])
    routine.setdefault("safety_notes", [])
    routine.setdefault("trainer_notes", [])

    expected_days = user_days(user_data)
    routine["days"] = routine["days"][:expected_days]

    while len(routine["days"]) < expected_days:
        day_number = len(routine["days"]) + 1
        routine["days"].append({
            "day": day_number,
            "name": f"Día {day_number}",
            "focus": "Trabajo general",
            "exercises": [],
        })

    for i, day in enumerate(routine["days"], start=1):
        if not isinstance(day, dict):
            routine["days"][i - 1] = {"day": i, "name": f"Día {i}", "focus": "", "exercises": []}
            continue
        day["day"] = i
        day.setdefault("name", f"Día {i}")
        day.setdefault("focus", "")
        if not isinstance(day.get("exercises"), list):
            day["exercises"] = []

    return routine


def canonicalize_exercise(item: dict[str, Any], indexes: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    by_id = indexes["by_id"]
    by_name = indexes["by_name"]

    exercise_id = str(item.get("exercise_id", "")).strip()
    name = normalize_text(item.get("name", ""))

    catalog_ex = None
    if exercise_id in by_id:
        catalog_ex = by_id[exercise_id]
    elif name in by_name:
        catalog_ex = by_name[name]

    if catalog_ex is None:
        return None

    def as_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    fixed = {
        "exercise_id": catalog_ex["exercise_id"],
        "name": catalog_ex["name"],
        "body_part": catalog_ex["body_part"],
        "equipment": catalog_ex["equipment"],
        "sets": max(1, min(6, as_int(item.get("sets"), 3))),
        "reps": str(item.get("reps", "8-12")).strip() or "8-12",
        "rest_seconds": max(30, min(240, as_int(item.get("rest_seconds"), 90))),
        "rir": str(item.get("rir", "1-3")).strip() or "1-3",
        "tempo": str(item.get("tempo", "controlado")).strip() or "controlado",
        "notes": str(item.get("notes", "")).strip(),
    }
    return fixed


def fallback_exercises_for_day(
    day: dict[str, Any],
    selected_exercises: list[dict[str, Any]],
    used_ids: set[str],
    user_data: dict[str, Any],
) -> list[dict[str, Any]]:
    split = professional_split(user_days(user_data))
    target_parts = split[day["day"] - 1].get("target_body_parts", MAIN_BODY_PARTS)

    candidates = [
        ex for ex in selected_exercises
        if ex["exercise_id"] not in used_ids and ex["body_part"] in target_parts
    ]
    if not candidates:
        candidates = [ex for ex in selected_exercises if ex["exercise_id"] not in used_ids]

    result = []
    for ex in candidates:
        if len(result) >= MIN_EXERCISES_PER_DAY:
            break
        used_ids.add(ex["exercise_id"])
        result.append({
            "exercise_id": ex["exercise_id"],
            "name": ex["name"],
            "body_part": ex["body_part"],
            "equipment": ex["equipment"],
            "sets": 3,
            "reps": "8-12" if ex["body_part"] != "Abdominals" else "12-20",
            "rest_seconds": 90,
            "rir": "2-3",
            "tempo": "2-0-2",
            "notes": "Ejercicio añadido por validación para completar el volumen mínimo del día.",
        })
    return result


def validate_and_repair_routine(
    routine: dict[str, Any],
    catalog: list[dict[str, Any]],
    selected_exercises: list[dict[str, Any]],
    user_data: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    indexes = build_catalog_indexes(catalog)
    warnings: list[str] = []
    used_ids: set[str] = set()

    for day in routine["days"]:
        fixed_exercises: list[dict[str, Any]] = []
        seen_day: set[str] = set()

        for item in day.get("exercises", []):
            if not isinstance(item, dict):
                warnings.append(f"Día {day['day']}: se eliminó un ejercicio con formato inválido.")
                continue

            fixed = canonicalize_exercise(item, indexes)
            if fixed is None:
                warnings.append(
                    f"Día {day['day']}: se eliminó un ejercicio inexistente en catálogo: "
                    f"{item.get('exercise_id') or item.get('name')}"
                )
                continue

            if fixed["exercise_id"] in seen_day:
                warnings.append(f"Día {day['day']}: se eliminó duplicado del mismo día: {fixed['name']}")
                continue

            seen_day.add(fixed["exercise_id"])
            used_ids.add(fixed["exercise_id"])
            fixed_exercises.append(fixed)

            if len(fixed_exercises) >= MAX_EXERCISES_PER_DAY:
                break

        if len(fixed_exercises) < MIN_EXERCISES_PER_DAY:
            missing = MIN_EXERCISES_PER_DAY - len(fixed_exercises)
            additions = fallback_exercises_for_day(day, selected_exercises, used_ids, user_data)
            fixed_exercises.extend(additions[:missing])
            if additions:
                warnings.append(f"Día {day['day']}: se añadieron {min(missing, len(additions))} ejercicios válidos del catálogo para completar la sesión.")

        day["exercises"] = fixed_exercises

    routine["validation"] = {
        "catalog_checked": True,
        "all_final_exercises_exist_in_catalog": True,
        "warnings": warnings,
    }
    return routine, warnings


# ============================================================
# EXPORTACIÓN MARKDOWN
# ============================================================

def list_to_md(items: Any) -> str:
    if not isinstance(items, list) or not items:
        return "- No especificado."
    return "\n".join(f"- {item}" for item in items)


def routine_to_markdown(routine: dict[str, Any]) -> str:
    lines: list[str] = []

    lines.append(f"# {routine.get('routine_name', 'Rutina generada')}\n")
    lines.append(f"**Fecha de generación:** {routine.get('created_at', '')}\n")

    summary = routine.get("user_summary", {}) if isinstance(routine.get("user_summary"), dict) else {}
    lines.append("## Resumen del perfil\n")
    lines.append(f"- **Objetivo:** {summary.get('goal', 'No especificado')}")
    lines.append(f"- **Nivel:** {summary.get('level', 'No especificado')}")
    lines.append(f"- **Días por semana:** {summary.get('days_per_week', 'No especificado')}")
    lines.append(f"- **Notas importantes:** {summary.get('important_notes', 'No especificado')}\n")

    if routine.get("professional_assessment"):
        lines.append("## Valoración profesional\n")
        lines.append(str(routine["professional_assessment"]) + "\n")

    if routine.get("weekly_structure"):
        lines.append("## Estructura semanal\n")
        lines.append(str(routine["weekly_structure"]) + "\n")

    lines.append("## Calentamiento general\n")
    lines.append(list_to_md(routine.get("warmup")) + "\n")

    lines.append("## Rutina\n")
    for day in routine.get("days", []):
        lines.append(f"### Día {day.get('day')}: {day.get('name', '')}")
        if day.get("focus"):
            lines.append(f"**Enfoque:** {day.get('focus')}\n")

        lines.append("| # | Ejercicio | Grupo | Equipo | Series | Reps | Descanso | RIR | Tempo | Notas |")
        lines.append("|---:|---|---|---|---:|---|---:|---|---|---|")
        for i, ex in enumerate(day.get("exercises", []), start=1):
            lines.append(
                f"| {i} | {ex.get('name', '')} | {ex.get('body_part', '')} | {ex.get('equipment', '')} | "
                f"{ex.get('sets', '')} | {ex.get('reps', '')} | {ex.get('rest_seconds', '')}s | "
                f"{ex.get('rir', '')} | {ex.get('tempo', '')} | {str(ex.get('notes', '')).replace('|', '/')} |"
            )
        lines.append("")

    lines.append("## Progresión semanal\n")
    lines.append(list_to_md(routine.get("weekly_progression")) + "\n")

    lines.append("## Vuelta a la calma\n")
    lines.append(list_to_md(routine.get("cooldown")) + "\n")

    lines.append("## Notas de seguridad\n")
    lines.append(list_to_md(routine.get("safety_notes")) + "\n")

    lines.append("## Notas del entrenador\n")
    lines.append(list_to_md(routine.get("trainer_notes")) + "\n")

    validation = routine.get("validation", {})
    warnings = validation.get("warnings", []) if isinstance(validation, dict) else []
    if warnings:
        lines.append("## Validación automática\n")
        lines.append(list_to_md(warnings) + "\n")

    return "\n".join(lines)


def save_outputs(routine: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{timestamp}_{slugify(routine.get('routine_name', 'rutina'))}"

    json_path = OUTPUT_DIR / f"{base_name}.json"
    md_path = OUTPUT_DIR / f"{base_name}.md"

    write_json(json_path, routine)
    md_path.write_text(routine_to_markdown(routine), encoding="utf-8")

    return json_path, md_path


# ============================================================
# FLUJO PRINCIPAL
# ============================================================

def generate_routine(model: str) -> dict[str, Any]:
    print("=== Generador inteligente de rutinas de entrenamiento basado en IA ===")
    print("La IA analiza el perfil, estructura la rutina y selecciona ejercicios del catálogo.\n")

    user_data = get_user_data()

    print("Cargando catálogo completo...")
    catalog = load_catalog()
    print(f"Catálogo cargado: {len(catalog)} ejercicios.\n")

    print("Preparando catálogo compacto para la IA...")
    selected_exercises = select_exercises_for_prompt(catalog, user_data)
    print(f"Ejercicios candidatos enviados a la IA: {len(selected_exercises)}.\n")

    print(f"Generando rutina con Ollama: {model}")
    messages = build_prompt(user_data, selected_exercises)
    raw_response = call_ollama(messages, model=model)

    raw_path = OUTPUT_DIR / "ultima_respuesta_ia_raw.txt"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(raw_response, encoding="utf-8")

    print("Validando respuesta de la IA...")
    raw_json = extract_json(raw_response)
    routine = normalize_routine(raw_json, user_data)
    routine, warnings = validate_and_repair_routine(routine, catalog, selected_exercises, user_data)

    json_path, md_path = save_outputs(routine)

    print("\nRutina generada correctamente.")
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")

    if warnings:
        print("\nAvisos de validación:")
        for warning in warnings:
            print(f"- {warning}")

    return routine


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generador profesional de rutinas de gimnasio con IA.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Modelo de Ollama a usar. Por defecto: {DEFAULT_MODEL}")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started = time.time()
    try:
        generate_routine(model=args.model)
    except KeyboardInterrupt:
        print("\nEjecución cancelada por el usuario.")
        sys.exit(130)
    except Exception as exc:
        print(f"\nError: {exc}")
        sys.exit(1)
    finally:
        elapsed = time.time() - started
        print(f"\nTiempo total: {elapsed:.1f} segundos")


if __name__ == "__main__":
    main()
