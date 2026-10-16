"""
Simple retrain script to (re)create a DecisionTreeRegressor compatible with
your currently installed scikit-learn. It reads `Battery_RUL.csv`, trains a
DecisionTreeRegressor on all columns except `RUL` and saves `battery_rul_model.pkl`.

Usage (Windows cmd.exe):
  python backend\retrain_model.py

Requirements:
  pip install -r requirements.txt
  or at least: pip install pandas scikit-learn joblib

Notes:
  - This trains a simple DecisionTreeRegressor. If your original model used a
    preprocessing pipeline or different algorithm, update this script to match.
"""

import sys
import os

try:
    import pandas as pd
    from sklearn.tree import DecisionTreeRegressor
    import joblib
except Exception as e:
    print("Missing required packages:", e)
    print("Install with: python -m pip install pandas scikit-learn joblib")
    sys.exit(1)

DATA_PATH = os.path.join(os.path.dirname(__file__), "Battery_RUL.csv")
MODEL_OUT = os.path.join(os.path.dirname(__file__), "battery_rul_model.pkl")


def main(argv=None):
  import argparse
  import platform

  parser = argparse.ArgumentParser(description="Retrain and save a DecisionTreeRegressor from Battery_RUL.csv")
  parser.add_argument("--data", default=DATA_PATH, help="Path to CSV data file")
  parser.add_argument("--out", default=MODEL_OUT, help="Output model path")
  parser.add_argument("--target", default="RUL", help="Name of the target column in CSV")
  args = parser.parse_args(argv)

  print(f"Python: {platform.python_version()}, pandas: {pd.__version__}")
  try:
    import sklearn
    print(f"scikit-learn: {sklearn.__version__}")
  except Exception:
    print("scikit-learn: not installed or import failed")

  if not os.path.exists(args.data):
    print(f"Data file not found: {args.data}")
    sys.exit(1)

  print("Loading data from", args.data)
  df = pd.read_csv(args.data)

  if args.target not in df.columns:
    print(f"Expected target column '{args.target}' not found in CSV.")
    print("Columns:", df.columns.tolist())
    sys.exit(1)

  # Prepare features and target
  X = df.drop(columns=[args.target]).copy()
  y = df[args.target].copy()

  # Coerce all feature columns to numeric where possible and fill missing values
  for c in X.columns:
    X[c] = pd.to_numeric(X[c], errors='coerce')
  # Fill numeric NaNs with median per column
  for c in X.columns:
    if X[c].isnull().any():
      med = X[c].median()
      X[c].fillna(med, inplace=True)

  # Ensure y is numeric
  y = pd.to_numeric(y, errors='coerce')
  if y.isnull().any():
    print(f"Warning: target column '{args.target}' contains NaNs after coercion; dropping those rows.")
    mask = ~y.isnull()
    X = X.loc[mask]
    y = y.loc[mask]

  print("Training DecisionTreeRegressor on", X.shape[0], "rows and", X.shape[1], "features")
  model = DecisionTreeRegressor(random_state=42)
  model.fit(X, y)

  print("Saving model to", args.out)
  # compress the joblib dump slightly to reduce file size
  joblib.dump(model, args.out, compress=3)
  print("Done. Now run your app (it will load the recreated model).")


if __name__ == '__main__':
  main()
