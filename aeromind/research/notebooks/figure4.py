import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

df = pd.read_csv("your_labeled_file.csv")

# clean
df["gesture_true"] = df["gesture_true"].astype(str).str.strip()
df["stable_gesture"] = df["stable_gesture"].astype(str).str.strip()

# filter valid rows
valid = {"", "nan", "-", "none"}
df = df[
    (df["event_type"] == "gesture_eval") &
    (~df["gesture_true"].isin(valid)) &
    (~df["stable_gesture"].isin(valid))
]

# build matrix
cm = pd.crosstab(df["gesture_true"], df["stable_gesture"])

# normalize
cm = cm.div(cm.sum(axis=1), axis=0)

# plot
plt.figure(figsize=(8,6))
sns.heatmap(cm, annot=True, fmt=".2f", cmap="Blues")

plt.title("Confusion Matrix - Stabilized Gestures")
plt.xlabel("Predicted")
plt.ylabel("Actual")

plt.xticks(rotation=45)
plt.yticks(rotation=0)

plt.tight_layout()
plt.savefig("confusion_matrix.png", dpi=300)
plt.show()