from __future__ import annotations


def extract_restrictions(free_text_notes: str) -> dict:
    text = (free_text_notes or "").lower()

    injuries = []
    avoid_keywords = []

    if "hombro" in text:
        injuries.append("hombro")
        avoid_keywords.extend([
            "overhead",
            "behind the neck",
            "upright row",
            "shoulder press",
            "military press",
        ])

    if "rodilla" in text:
        injuries.append("rodilla")
        avoid_keywords.extend([
            "jump",
            "lunge",
            "deep squat",
            "pistol",
            "box jump",
        ])

    if "espalda" in text or "lumbar" in text:
        injuries.append("espalda")
        avoid_keywords.extend([
            "deadlift",
            "good morning",
            "back extension",
            "hyperextension",
        ])

    if "muñeca" in text or "muneca" in text:
        injuries.append("muñeca")
        avoid_keywords.extend([
            "push-up",
            "handstand",
            "wrist",
        ])

    return {
        "injuries": sorted(set(injuries)),
        "avoid_keywords": sorted(set(avoid_keywords)),
    }
