import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).parent

INPUT_CSV = "context/megaGymDataset.csv"

OUTPUT_DIR = BASE_DIR / "processed_context"
OUTPUT_DIR.mkdir(exist_ok=True)

OUTPUT_JSON = OUTPUT_DIR / "catalogo_procesado.json"
REPORT_JSON = OUTPUT_DIR / "catalogo_preprocesado_reporte.json"


LEVEL_MAP = {
    "Beginner": "principiante",
    "Intermediate": "intermedio",
    "Expert": "avanzado",
}


EQUIPMENT_MAP = {
    "Bands": "bandas",
    "Barbell": "barra",
    "Body Only": "peso_corporal",
    "Cable": "polea",
    "Dumbbell": "mancuernas",
    "E-Z Curl Bar": "barra_z",
    "Exercise Ball": "pelota_ejercicio",
    "Foam Roll": "foam_roller",
    "Kettlebells": "kettlebell",
    "Machine": "maquina",
    "Medicine Ball": "balon_medicinal",
    "Other": "otro",
}


MUSCLE_MAP = {
    "Abdominals": "abdomen",
    "Abductors": "abductores",
    "Adductors": "aductores",
    "Biceps": "biceps",
    "Calves": "gemelos",
    "Chest": "pecho",
    "Forearms": "antebrazos",
    "Glutes": "gluteos",
    "Hamstrings": "isquiosurales",
    "Lats": "espalda",
    "Lower Back": "espalda_baja",
    "Middle Back": "espalda",
    "Neck": "cuello",
    "Quadriceps": "cuadriceps",
    "Shoulders": "hombros",
    "Traps": "trapecio",
    "Triceps": "triceps",
}


TYPE_MAP = {
    "Cardio": "cardio",
    "Olympic Weightlifting": "halterofilia",
    "Plyometrics": "pliometria",
    "Powerlifting": "powerlifting",
    "Strength": "fuerza",
    "Stretching": "estiramiento",
    "Strongman": "strongman",
}


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def normalize_value(value: object, mapping: dict[str, str], default: str = "sin_especificar") -> str:
    text = clean_text(value)
    if not text:
        return default
    return mapping.get(text, f"unknown:{text}")


def build_catalog(input_csv: str = INPUT_CSV) -> tuple[list[dict], dict]:
    df = pd.read_csv(input_csv)

    required_columns = ["Title", "Type", "BodyPart", "Equipment", "Level"]
    missing_columns = [column for column in required_columns if column not in df.columns]
    if missing_columns:
        raise ValueError(f"Faltan columnas obligatorias en el CSV: {missing_columns}")

    original_rows = len(df)

    df["Title"] = df["Title"].apply(clean_text)
    df = df[df["Title"] != ""].copy()

    # Evita ejercicios duplicados por nombre, conservando la primera aparición.
    duplicated_titles = int(df["Title"].duplicated().sum())
    df = df.drop_duplicates(subset=["Title"], keep="first").copy()

    catalog = []
    unknown_values = {
        "type": {},
        "muscle_group": {},
        "equipment": {},
        "level": {},
    }

    for new_id, (_, row) in enumerate(df.iterrows(), start=1):
        original_type = clean_text(row.get("Type"))
        original_bodypart = clean_text(row.get("BodyPart"))
        original_equipment = clean_text(row.get("Equipment"))
        original_level = clean_text(row.get("Level"))

        normalized_type = normalize_value(original_type, TYPE_MAP)
        normalized_muscle = normalize_value(original_bodypart, MUSCLE_MAP)
        normalized_equipment = normalize_value(original_equipment, EQUIPMENT_MAP, default="sin_equipamiento")
        normalized_level = normalize_value(original_level, LEVEL_MAP)

        values_to_check = {
            "type": normalized_type,
            "muscle_group": normalized_muscle,
            "equipment": normalized_equipment,
            "level": normalized_level,
        }

        originals = {
            "type": original_type,
            "muscle_group": original_bodypart,
            "equipment": original_equipment,
            "level": original_level,
        }

        for field, normalized in values_to_check.items():
            if normalized.startswith("unknown:"):
                raw = originals[field]
                unknown_values[field][raw] = unknown_values[field].get(raw, 0) + 1

        catalog.append(
            {
                "id": new_id,
                "name": clean_text(row["Title"]),
                "level": normalized_level,
                "equipment": normalized_equipment,
                "muscle_group": normalized_muscle,
                "type": normalized_type,
                "source": {
                    "original_id": int(row["Unnamed: 0"]) if "Unnamed: 0" in row and pd.notna(row["Unnamed: 0"]) else None,
                    "original_title": clean_text(row["Title"]),
                    "original_level": original_level,
                    "original_equipment": original_equipment,
                    "original_bodypart": original_bodypart,
                    "original_type": original_type,
                },
            }
        )

    invalid_items = [
        item for item in catalog
        if not item["name"]
        or item["level"].startswith("unknown:")
        or item["muscle_group"].startswith("unknown:")
        or item["equipment"].startswith("unknown:")
        or item["type"].startswith("unknown:")
    ]

    report = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "input_csv": input_csv,
        "original_rows": original_rows,
        "processed_rows": len(catalog),
        "removed_empty_titles": original_rows - len(df) - duplicated_titles,
        "removed_duplicated_titles": duplicated_titles,
        "invalid_items_count": len(invalid_items),
        "unknown_values": unknown_values,
        "counts": {
            "by_level": count_by(catalog, "level"),
            "by_equipment": count_by(catalog, "equipment"),
            "by_muscle_group": count_by(catalog, "muscle_group"),
            "by_type": count_by(catalog, "type"),
        },
        "validation": {
            "ok": len(invalid_items) == 0,
            "message": "Catálogo procesado correctamente." if len(invalid_items) == 0 else "Hay valores no reconocidos. Revisa unknown_values.",
        },
    }

    return catalog, report


def count_by(catalog: list[dict], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in catalog:
        key = item[field]
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: x[0]))


def save_json(data: object, output_path: str) -> None:
    Path(output_path).write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main() -> None:
    catalog, report = build_catalog(INPUT_CSV)
    save_json(catalog, OUTPUT_JSON)
    save_json(report, REPORT_JSON)

    print("=== Preprocesado del catálogo completado ===")
    print(f"Filas originales: {report['original_rows']}")
    print(f"Ejercicios procesados: {report['processed_rows']}")
    print(f"Duplicados eliminados: {report['removed_duplicated_titles']}")
    print(f"Elementos inválidos: {report['invalid_items_count']}")
    print(f"Catálogo generado: {OUTPUT_JSON}")
    print(f"Reporte generado: {REPORT_JSON}")

    if report["validation"]["ok"]:
        print("Validación: OK")
    else:
        print("Validación: revisar valores no reconocidos en el reporte.")


if __name__ == "__main__":
    main()
