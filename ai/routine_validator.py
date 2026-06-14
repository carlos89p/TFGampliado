from __future__ import annotations

import json
import re
from datetime import datetime

from .ollama_client import OllamaError, call_ollama_chat, DEFAULT_MODEL


VALIDATION_SYSTEM_PROMPT = """
Eres un entrenador personal y auditor técnico de rutinas de gimnasio.
Tu tarea NO es generar una rutina nueva desde cero.
Tu tarea es revisar una rutina ya generada por un sistema basado en reglas.

Reglas obligatorias:
- No inventes ejercicios nuevos.
- No reescribas toda la rutina.
- No cambies el formato de la rutina original.
- Evalúa seguridad, coherencia, volumen, nivel, objetivo y equilibrio muscular.
- Si hay ejercicios problemáticos, menciónalos por nombre exacto.
- Devuelve SIEMPRE un JSON válido, sin Markdown y sin texto adicional.
""".strip()


def _compact_routine_for_ai(routine: dict) -> dict:
    """
    Reduce la rutina a lo necesario para que la IA valide sin enviar ruido excesivo.
    """
    return {
        "user_summary": routine.get("user_summary", {}),
        "detected_restrictions": routine.get("detected_restrictions", {}),
        "split": routine.get("split", {}),
        "routine": routine.get("routine", []),
        "progression_notes": routine.get("progression_notes", []),
    }


def _extract_json_object(text: str) -> dict:
    """
    Extrae un objeto JSON aunque el modelo añada texto alrededor por error.
    """
    text = (text or "").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("La IA no devolvió un objeto JSON reconocible.")

    return json.loads(match.group(0))


def build_validation_prompt(routine: dict) -> str:
    compact = _compact_routine_for_ai(routine)

    expected_schema = {
        "status": "aprobada | aprobada_con_observaciones | requiere_revision",
        "score_0_10": 0,
        "summary": "Resumen breve de la calidad de la rutina.",
        "critical_issues": [
            "Errores graves que impiden recomendar la rutina. Vacío si no hay."
        ],
        "warnings": [
            "Observaciones importantes pero no críticas. Vacío si no hay."
        ],
        "exercise_specific_feedback": [
            {
                "exercise_name": "Nombre exacto del ejercicio",
                "issue": "Problema detectado",
                "suggestion": "Sugerencia sin inventar ejercicios fuera de la rutina",
            }
        ],
        "final_recommendation": "Recomendación final breve.",
    }

    return f"""
Valida la siguiente rutina de gimnasio.

Criterios:
1. Debe ser coherente con el objetivo del usuario.
2. Debe ser adecuada para el nivel del usuario.
3. Debe tener un reparto muscular equilibrado.
4. Debe evitar ejercicios demasiado técnicos o explosivos para principiantes.
5. Debe detectar huecos como ejercicios no encontrados, grupos musculares omitidos o exceso de volumen.
6. Debe considerar lesiones o restricciones si aparecen.
7. Si aparece molestia lumbar/espalda, debe comprobar que la rutina mantenga ejercicio progresivo y priorice core/estabilidad, fortalecimiento controlado, movilidad y cardio suave, evitando cargas axiales pesadas, bisagras pesadas y movimientos explosivos que puedan agravar síntomas.

Devuelve exclusivamente un JSON con este esquema:
{json.dumps(expected_schema, ensure_ascii=False, indent=2)}

Rutina a validar:
{json.dumps(compact, ensure_ascii=False, indent=2)}
""".strip()


def validate_routine_with_ai(
    routine: dict,
    model: str | None = None,
    enabled: bool = True,
) -> dict:
    """
    Ejecuta una validación final con IA y devuelve un bloque ai_validation.

    Si Ollama no está disponible, no rompe el programa: devuelve un bloque de error
    controlado para que la generación por reglas siga funcionando.
    """
    validation = {
        "enabled": enabled,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "model": model or DEFAULT_MODEL,
        "status": "not_run",
        "score_0_10": None,
        "summary": "",
        "critical_issues": [],
        "warnings": [],
        "exercise_specific_feedback": [],
        "final_recommendation": "",
        "raw_response": None,
        "error": None,
    }

    if not enabled:
        validation["summary"] = "Validación IA desactivada."
        return validation

    messages = [
        {"role": "system", "content": VALIDATION_SYSTEM_PROMPT},
        {"role": "user", "content": build_validation_prompt(routine)},
    ]

    try:
        raw_response = call_ollama_chat(messages=messages, model=model)
        parsed = _extract_json_object(raw_response)

        validation.update({
            "status": parsed.get("status", "aprobada_con_observaciones"),
            "score_0_10": parsed.get("score_0_10"),
            "summary": parsed.get("summary", ""),
            "critical_issues": parsed.get("critical_issues", []),
            "warnings": parsed.get("warnings", []),
            "exercise_specific_feedback": parsed.get("exercise_specific_feedback", []),
            "final_recommendation": parsed.get("final_recommendation", ""),
            "raw_response": raw_response,
        })

    except (OllamaError, ValueError, json.JSONDecodeError) as exc:
        validation.update({
            "status": "validation_failed",
            "summary": "La rutina se generó por reglas, pero no se pudo completar la validación IA.",
            "warnings": [
                "Comprueba que Ollama esté abierto y que el modelo configurado esté descargado."
            ],
            "error": str(exc),
        })

    return validation
