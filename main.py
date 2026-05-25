import json
from pathlib import Path

from procesamiento_manual import build_manual_user_data
from rules.routine_builder import build_routine
from ai.routine_corrector import correct_routine_with_ai


BASE_DIR = Path(__file__).parent

USER_JSON = BASE_DIR / "manual_input_ai_ready.json"
CATALOG_JSON = BASE_DIR / "processed_context" / "catalogo_procesado.json"
OUTPUT_DIR = BASE_DIR / "generated_routines"

# Salida generada únicamente por reglas.
OUTPUT_RULES_JSON = OUTPUT_DIR / "rutina_generada.json"

# Salida corregida por IA usando candidatos reales del catálogo.
OUTPUT_VALIDATED_JSON = OUTPUT_DIR / "rutina_generada_validada.json"


def load_json(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(data: dict, path: Path) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def ask_yes_no(question: str, default: str = "s") -> bool:
    """
    Pregunta sí/no por consola.

    default:
        "s" -> si el usuario pulsa Enter, responde sí.
        "n" -> si el usuario pulsa Enter, responde no.
    """
    default = default.lower().strip()
    if default not in {"s", "n"}:
        default = "s"

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


def get_user_data() -> dict:
    """
    Obtiene los datos del usuario.

    Si existe manual_input_ai_ready.json, pregunta si se quiere reutilizar.
    Si no existe, o si el usuario elige crear uno nuevo, ejecuta el cuestionario
    definido en procesamiento_manual.py y guarda el nuevo JSON.
    """
    if USER_JSON.exists():
        print(f"Se ha encontrado un archivo de usuario existente: {USER_JSON.name}")
        use_existing = ask_yes_no("¿Quieres usar este archivo?", default="s")

        if use_existing:
            print("Usando datos existentes del usuario.\n")
            return load_json(USER_JSON)

        print("\nSe creará un nuevo perfil de usuario.\n")
    else:
        print(f"No se encontró {USER_JSON.name}.")
        print("Se iniciará el cuestionario para crear uno nuevo.\n")

    user_data = build_manual_user_data()
    save_json(user_data, USER_JSON)

    print(f"\nNuevo JSON de usuario guardado correctamente en: {USER_JSON}\n")
    return user_data


def main() -> None:
    print("=== Generador de rutinas basado en reglas ===\n")

    user_data = get_user_data()
    catalog = load_json(CATALOG_JSON)

    routine = build_routine(user_data=user_data, catalog=catalog)

    # 1. Guardamos la rutina pura de reglas sin tocar.
    save_json(routine, OUTPUT_RULES_JSON)
    print(f"Rutina generada por reglas guardada en: {OUTPUT_RULES_JSON}")

    # 2. Creamos una segunda versión corregida por IA.
    print("\nValidando y corrigiendo rutina con IA local...\n")
    correction_result = correct_routine_with_ai(
        routine=routine,
        catalog=catalog,
        enabled=True,
    )

    corrected_routine = correction_result["corrected_routine"]
    save_json(corrected_routine, OUTPUT_VALIDATED_JSON)

    print(f"Rutina validada/corregida guardada en: {OUTPUT_VALIDATED_JSON}")

    changes = corrected_routine.get("ai_correction", {}).get("changes_applied", [])
    if changes:
        print(f"Cambios aplicados por la capa IA: {len(changes)}")
        for change in changes:
            old_name = change.get("old_exercise", {}).get("name")
            new_name = change.get("new_exercise", {}).get("name")
            print(f"- {old_name}  ->  {new_name}")
    else:
        print("La capa IA no aplicó cambios automáticos.")

    print("\n=== Rutina final validada ===")
    print(json.dumps(corrected_routine, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
