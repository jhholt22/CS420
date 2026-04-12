import pandas as pd
import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt

CSV_PATH = "data/logs/gesture_research_logs.csv"
OUTPUT_IMAGE = "drone_mode_gesture_distribution.png"

df = pd.read_csv(CSV_PATH)

for col in ["event_type", "stable_gesture"]:
    if col not in df.columns:
        raise ValueError(f"Missing required column: {col}")
    df[col] = df[col].fillna("").astype(str).str.strip()

valid_labels = {"", "nan", "none", "-", "no_label"}

filtered_df = df[
    (df["event_type"].str.lower() == "gesture_eval") &
    (~df["stable_gesture"].str.lower().isin(valid_labels))
].copy()

if filtered_df.empty:
    raise ValueError("No valid stabilized gesture rows found.")

counts = filtered_df["stable_gesture"].value_counts().sort_values(ascending=False)
proportions = counts / counts.sum()

plt.close("all")
plt.style.use("default")

fig, ax = plt.subplots(figsize=(10, 6), facecolor="white")
bars = ax.bar(proportions.index, proportions.values)

ax.set_title("Stabilized Gesture Distribution in Drone Mode", fontsize=14, pad=12)
ax.set_xlabel("Predicted Stabilized Gesture", fontsize=12)
ax.set_ylabel("Proportion", fontsize=12)

ax.set_ylim(0, max(proportions.values) * 1.15)
plt.xticks(rotation=35, ha="right")

for i, v in enumerate(proportions.values):
    ax.text(i, v + 0.01, f"{v:.2f}", ha="center", va="bottom", fontsize=10)

fig.patch.set_facecolor("white")
ax.set_facecolor("white")

plt.tight_layout()
plt.savefig(OUTPUT_IMAGE, dpi=300, bbox_inches="tight", facecolor="white")
print(f"Saved figure to: {OUTPUT_IMAGE}")