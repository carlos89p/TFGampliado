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

    if any(word in text for word in ["espalda", "lumbar", "lumbalgia", "ciatica", "ciática"]):
        injuries.extend(["espalda", "lumbar"])
        avoid_keywords.extend([
            "deadlift",
            "romanian deadlift",
            "stiff-legged deadlift",
            "good morning",
            "back extension",
            "hyperextension",
            "bent-over row",
            "bent over row",
            "barbell row",
            "back squat",
            "front squat",
            "overhead squat",
            "power clean",
            "clean",
            "snatch",
            "swing",
            "jump",
            "burpee",
            "twist",
            "rollout",
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
