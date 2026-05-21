import json
from pathlib import Path

from procesamiento_manual import build_manual_user_data
from rules.routine_builder import build_routine


BASE_DIR = Path(__file__).parent

USER_JSON = BASE_DIR / "manual_input_ai_ready.json"
CATALOG_JSON = BASE_DIR / "processed_context" / "catalogo_procesado.json"
OUTPUT_DIR = BASE_DIR / "generated_routines"
OUTPUT_JSON = OUTPUT_DIR / "rutina_generada.json"


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

    save_json(routine, OUTPUT_JSON)

    print(f"Rutina generada correctamente: {OUTPUT_JSON}")
    print(json.dumps(routine, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
