import os
import random
import joblib
import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error, r2_score


DATASET_PATH = r"context\megaGymDataset.csv"
MODEL_DIR = "model"
MODEL_PATH = os.path.join(MODEL_DIR, "exercise_recommender_model.joblib")


def load_dataset(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    df = df.drop(columns=["Unnamed: 0"], errors="ignore")

    required_columns = ["Title", "Desc", "Type", "BodyPart", "Equipment", "Level", "Rating"]

    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Falta la columna obligatoria: {col}")

    df["Title"] = df["Title"].fillna("").astype(str)
    df["Desc"] = df["Desc"].fillna("").astype(str)
    df["Type"] = df["Type"].fillna("Unknown").astype(str)
    df["BodyPart"] = df["BodyPart"].fillna("Unknown").astype(str)
    df["Equipment"] = df["Equipment"].fillna("Unknown").astype(str)
    df["Level"] = df["Level"].fillna("Intermediate").astype(str)
    df["Rating"] = df["Rating"].fillna(df["Rating"].median())

    df = df[df["Title"].str.strip() != ""]
    df = df.drop_duplicates(subset=["Title", "BodyPart", "Equipment"])

    return df.reset_index(drop=True)


def generate_random_user() -> dict:
    return {
        "age": random.randint(18, 65),
        "weight": random.randint(50, 120),
        "height": random.randint(150, 200),
        "fitness_level": random.choice(["Beginner", "Intermediate", "Expert"]),
        "goal": random.choice(["muscle_gain", "fat_loss", "strength", "general_fitness"]),
        "training_days": random.randint(2, 6),
        "has_lumbar_pain": random.choice([0, 0, 0, 1]),
        "has_shoulder_pain": random.choice([0, 0, 0, 1]),
        "has_knee_pain": random.choice([0, 0, 0, 1]),
    }


def calculate_suitability(user: dict, exercise: pd.Series) -> float:
    score = 0.5

    exercise_level = str(exercise["Level"]).lower()
    user_level = user["fitness_level"].lower()
    body_part = str(exercise["BodyPart"]).lower()
    equipment = str(exercise["Equipment"]).lower()
    exercise_type = str(exercise["Type"]).lower()
    rating = float(exercise["Rating"]) if not pd.isna(exercise["Rating"]) else 0

    if user_level == "beginner":
        if exercise_level == "beginner":
            score += 0.25
        elif exercise_level == "intermediate":
            score += 0.05
        elif exercise_level == "expert":
            score -= 0.35

    elif user_level == "intermediate":
        if exercise_level == "intermediate":
            score += 0.25
        elif exercise_level == "beginner":
            score += 0.10
        elif exercise_level == "expert":
            score -= 0.15

    elif user_level == "expert":
        if exercise_level == "expert":
            score += 0.25
        elif exercise_level == "intermediate":
            score += 0.15

    if user["goal"] == "muscle_gain":
        if exercise_type == "strength":
            score += 0.20

    elif user["goal"] == "strength":
        if equipment in ["barbell", "dumbbell", "machine", "cable"]:
            score += 0.15
        if exercise_type == "strength":
            score += 0.15

    elif user["goal"] == "fat_loss":
        if equipment in ["body only", "bands", "kettlebells"]:
            score += 0.15
        if body_part in ["quadriceps", "glutes", "hamstrings", "abdominals"]:
            score += 0.10

    elif user["goal"] == "general_fitness":
        if exercise_level in ["beginner", "intermediate"]:
            score += 0.15

    if user["training_days"] <= 3:
        if body_part in ["quadriceps", "chest", "back", "shoulders", "glutes"]:
            score += 0.10

    if user["has_lumbar_pain"]:
        if body_part in ["lower back", "hamstrings"]:
            score -= 0.35
        if "deadlift" in exercise["Title"].lower() or "good morning" in exercise["Title"].lower():
            score -= 0.45

    if user["has_shoulder_pain"]:
        if body_part in ["shoulders"]:
            score -= 0.35
        if "press" in exercise["Title"].lower() or "upright row" in exercise["Title"].lower():
            score -= 0.25

    if user["has_knee_pain"]:
        if body_part in ["quadriceps"]:
            score -= 0.25
        if "squat" in exercise["Title"].lower() or "lunge" in exercise["Title"].lower():
            score -= 0.30

    if rating > 0:
        score += min(rating / 10, 1) * 0.10

    return float(np.clip(score, 0, 1))


def create_training_data(df: pd.DataFrame, users_count: int = 1500, exercises_per_user: int = 40) -> pd.DataFrame:
    rows = []

    for _ in range(users_count):
        user = generate_random_user()
        sampled_exercises = df.sample(n=min(exercises_per_user, len(df)), random_state=None)

        for _, exercise in sampled_exercises.iterrows():
            rows.append({
                "age": user["age"],
                "weight": user["weight"],
                "height": user["height"],
                "fitness_level": user["fitness_level"],
                "goal": user["goal"],
                "training_days": user["training_days"],
                "has_lumbar_pain": user["has_lumbar_pain"],
                "has_shoulder_pain": user["has_shoulder_pain"],
                "has_knee_pain": user["has_knee_pain"],

                "exercise_title": exercise["Title"],
                "exercise_type": exercise["Type"],
                "body_part": exercise["BodyPart"],
                "equipment": exercise["Equipment"],
                "exercise_level": exercise["Level"],
                "rating": exercise["Rating"],

                "suitability_score": calculate_suitability(user, exercise)
            })

    return pd.DataFrame(rows)


def train_model(training_df: pd.DataFrame):
    target = "suitability_score"

    X = training_df.drop(columns=[target])
    y = training_df[target]

    numeric_features = [
        "age",
        "weight",
        "height",
        "training_days",
        "has_lumbar_pain",
        "has_shoulder_pain",
        "has_knee_pain",
        "rating",
    ]

    categorical_features = [
        "fitness_level",
        "goal",
        "exercise_title",
        "exercise_type",
        "body_part",
        "equipment",
        "exercise_level",
    ]

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), numeric_features),
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_features),
        ]
    )

    model = RandomForestRegressor(
        n_estimators=200,
        random_state=42,
        max_depth=18,
        n_jobs=-1
    )

    pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", model),
        ]
    )

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    pipeline.fit(X_train, y_train)

    predictions = pipeline.predict(X_test)

    mae = mean_absolute_error(y_test, predictions)
    r2 = r2_score(y_test, predictions)

    print("Entrenamiento completado.")
    print(f"MAE: {mae:.4f}")
    print(f"R2: {r2:.4f}")

    return pipeline


def main():
    os.makedirs(MODEL_DIR, exist_ok=True)

    print("Cargando dataset...")
    exercises_df = load_dataset(DATASET_PATH)

    print(f"Ejercicios cargados: {len(exercises_df)}")

    print("Generando datos sintéticos de entrenamiento...")
    training_df = create_training_data(
        exercises_df,
        users_count=1500,
        exercises_per_user=40
    )

    print(f"Filas de entrenamiento generadas: {len(training_df)}")

    training_df.to_csv(os.path.join(MODEL_DIR, "training_data.csv"), index=False)
    exercises_df.to_csv(os.path.join(MODEL_DIR, "clean_exercises.csv"), index=False)

    print("Entrenando modelo...")
    model = train_model(training_df)

    joblib.dump(model, MODEL_PATH)

    print(f"Modelo guardado en: {MODEL_PATH}")


if __name__ == "__main__":
    main()