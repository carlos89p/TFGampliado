from __future__ import annotations


def choose_split(days_per_week: int, experience_level: str) -> dict:
    days = max(1, min(int(days_per_week), 7))
    level = (experience_level or "principiante").lower()

    if days <= 2:
        return {
            "split_name": "full_body",
            "days": [
                {"day": 1, "name": "Full Body A", "focus": ["full_body"]},
                {"day": 2, "name": "Full Body B", "focus": ["full_body"]},
            ][:days],
        }

    if days == 3:
        return {
            "split_name": "full_body",
            "days": [
                {"day": 1, "name": "Full Body A", "focus": ["full_body"]},
                {"day": 2, "name": "Full Body B", "focus": ["full_body"]},
                {"day": 3, "name": "Full Body C", "focus": ["full_body"]},
            ],
        }

    if days == 4:
        return {
            "split_name": "upper_lower",
            "days": [
                {"day": 1, "name": "Torso A", "focus": ["upper"]},
                {"day": 2, "name": "Pierna A", "focus": ["lower"]},
                {"day": 3, "name": "Torso B", "focus": ["upper"]},
                {"day": 4, "name": "Pierna B", "focus": ["lower"]},
            ],
        }

    if days == 5:
        if level == "principiante":
            return {
                "split_name": "upper_lower_plus_full_body",
                "days": [
                    {"day": 1, "name": "Torso A", "focus": ["upper"]},
                    {"day": 2, "name": "Pierna A", "focus": ["lower"]},
                    {"day": 3, "name": "Full Body", "focus": ["full_body"]},
                    {"day": 4, "name": "Torso B", "focus": ["upper"]},
                    {"day": 5, "name": "Pierna B", "focus": ["lower"]},
                ],
            }

        return {
            "split_name": "push_pull_legs_upper_lower",
            "days": [
                {"day": 1, "name": "Push", "focus": ["push"]},
                {"day": 2, "name": "Pull", "focus": ["pull"]},
                {"day": 3, "name": "Pierna", "focus": ["lower"]},
                {"day": 4, "name": "Torso", "focus": ["upper"]},
                {"day": 5, "name": "Pierna + Core", "focus": ["lower", "core"]},
            ],
        }

    return {
        "split_name": "push_pull_legs",
        "days": [
            {"day": 1, "name": "Push A", "focus": ["push"]},
            {"day": 2, "name": "Pull A", "focus": ["pull"]},
            {"day": 3, "name": "Pierna A", "focus": ["lower"]},
            {"day": 4, "name": "Push B", "focus": ["push"]},
            {"day": 5, "name": "Pull B", "focus": ["pull"]},
            {"day": 6, "name": "Pierna B", "focus": ["lower"]},
            {"day": 7, "name": "Core / movilidad", "focus": ["core"]},
        ][:days],
    }
