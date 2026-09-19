import pandas as pd
import pickle
from sklearn.ensemble import RandomForestClassifier

data = pd.read_csv("heart.csv")

X = data[["age", "sex", "cp", "trestbps", "chol"]]
y = data["target"]

model = RandomForestClassifier(
    n_estimators=100,
    random_state=42
)

model.fit(X, y)

with open("heart_model.pkl", "wb") as f:
    pickle.dump(model, f)

print("Model trained successfully!")