import re
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.spatial import ConvexHull
from scipy.spatial.distance import pdist, squareform

try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


# ============================================================
# Paths
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

SCALER_PATH = ROOT / "models" / "feature_scaler.pkl"
FEATURE_NAMES_PATH = ROOT / "models" / "feature_names.txt"
PLACEMENTS_PATH = ROOT / "data" / "placements.csv"  # adjust if needed


# ============================================================
# Model registry
# ============================================================

MODEL_REGISTRY = {
    "linear": {
        "path": ROOT / "models" / "linear_regression.pkl",
        "kind": "sklearn",
        "needs_scaling": True,
    },
    "ridge": {
        "path": ROOT / "models" / "ridge_regression.pkl",
        "kind": "sklearn",
        "needs_scaling": True,
    },
    "lasso": {
        "path": ROOT / "models" / "lasso_regression.pkl",
        "kind": "sklearn",
        "needs_scaling": True,
    },
    "random_forest": {
        "path": ROOT / "models" / "random_forest_tuned.pkl",
        "kind": "sklearn",
        "needs_scaling": False,
    },
    "nn_best": {
        "path": ROOT / "models" / "neural_network_best.pth",
        "kind": "torch_checkpoint",
        "needs_scaling": True,
    },
}

DEFAULT_MODEL = "random_forest"


# ============================================================
# Board constants
# Adjust if your board coordinate system differs
# ============================================================

x_min, x_max = 0.0, 144.0
y_min, y_max = 0.0, 144.0
board_width = x_max - x_min
board_height = y_max - y_min


# ============================================================
# Role mappings
# ============================================================

HAND_ROLE_IDS = {5, 6, 7}
FOOT_ROLE_IDS = {8}


def get_role_type(role_id: int) -> str:
    mapping = {
        5: "start",
        6: "middle",
        7: "finish",
        8: "foot",
    }
    return mapping.get(role_id, "middle")


# ============================================================
# Grade map
# ============================================================

grade_map = {
    10: '4a/V0',
    11: '4b/V0',
    12: '4c/V0',
    13: '5a/V1',
    14: '5b/V1',
    15: '5c/V2',
    16: '6a/V3',
    17: '6a+/V3',
    18: '6b/V4',
    19: '6b+/V4',
    20: '6c/V5',
    21: '6c+/V5',
    22: '7a/V6',
    23: '7a+/V7',
    24: '7b/V8',
    25: '7b+/V8',
    26: '7c/V9',
    27: '7c+/V10',
    28: '8a/V11',
    29: '8a+/V12',
    30: '8b/V13',
    31: '8b+/V14',
    32: '8c/V15',
    33: '8c+/V16'
}

MIN_GRADE = min(grade_map)
MAX_GRADE = max(grade_map)


# ============================================================
# Neural network architecture from Notebook 06
# ============================================================

if TORCH_AVAILABLE:
    class ClimbGradePredictor(nn.Module):
        def __init__(self, input_dim, hidden_layers=None, dropout_rate=0.2):
            super().__init__()

            if hidden_layers is None:
                hidden_layers = [256, 128, 64]

            layers = []
            prev_dim = input_dim

            for hidden_dim in hidden_layers:
                layers.append(nn.Linear(prev_dim, hidden_dim))
                layers.append(nn.BatchNorm1d(hidden_dim))
                layers.append(nn.ReLU())
                layers.append(nn.Dropout(dropout_rate))
                prev_dim = hidden_dim

            layers.append(nn.Linear(prev_dim, 1))
            self.network = nn.Sequential(*layers)

        def forward(self, x):
            return self.network(x)


# ============================================================
# Load shared artifacts
# ============================================================

scaler = joblib.load(SCALER_PATH)

with open(FEATURE_NAMES_PATH, "r") as f:
    FEATURE_NAMES = [line.strip() for line in f if line.strip()]

df_placements = pd.read_csv(PLACEMENTS_PATH)

placement_coords = {
    int(row["placement_id"]): (row["x"], row["y"])
    for _, row in df_placements.iterrows()
}


# ============================================================
# Model loading
# ============================================================

_MODEL_CACHE = {}


def normalize_model_name(model_name: str) -> str:
    if model_name == "nn":
        return "nn_best"
    return model_name


def load_model(model_name=DEFAULT_MODEL):
    model_name = normalize_model_name(model_name)

    if model_name not in MODEL_REGISTRY:
        raise ValueError(
            f"Unknown model '{model_name}'. Choose from: {list(MODEL_REGISTRY.keys()) + ['nn']}"
        )

    if model_name in _MODEL_CACHE:
        return _MODEL_CACHE[model_name]

    info = MODEL_REGISTRY[model_name]
    path = info["path"]

    if info["kind"] == "sklearn":
        model = joblib.load(path)

    elif info["kind"] == "torch_checkpoint":
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch is not installed, so the neural network model cannot be used.")

        checkpoint = torch.load(path, map_location="cpu")

        if hasattr(checkpoint, "eval"):
            model = checkpoint
            model.eval()

        elif isinstance(checkpoint, dict):
            input_dim = checkpoint.get("input_dim", len(FEATURE_NAMES))
            hidden_layers = checkpoint.get("hidden_layers", [256, 128, 64])
            dropout_rate = checkpoint.get("dropout_rate", 0.2)

            model = ClimbGradePredictor(
                input_dim=input_dim,
                hidden_layers=hidden_layers,
                dropout_rate=dropout_rate,
            )

            if "model_state_dict" in checkpoint:
                model.load_state_dict(checkpoint["model_state_dict"])
            else:
                model.load_state_dict(checkpoint)

            model.eval()

        else:
            raise RuntimeError(
                f"Unsupported checkpoint type for {model_name}: {type(checkpoint)}"
            )

    else:
        raise ValueError(f"Unsupported model kind: {info['kind']}")

    _MODEL_CACHE[model_name] = model
    return model


# ============================================================
# Helpers
# ============================================================

def parse_frames(frames: str):
    """
    Parse strings like:
        p304r8p378r6p552r6
    into:
        [(304, 8), (378, 6), (552, 6)]
    """
    if not isinstance(frames, str) or not frames.strip():
        return []
    matches = re.findall(r"p(\d+)r(\d+)", frames)
    return [(int(p), int(r)) for p, r in matches]


# ============================================================
# Feature extraction
# ============================================================

def extract_features_from_raw(angle, frames, is_nomatch=0, description=""):
    """
    Extract the clean, leakage-free feature set used by the updated models.
    """
    holds = parse_frames(frames)
    if not holds:
        raise ValueError("Could not parse any holds from frames.")

    hold_data = []
    for placement_id, role_id in holds:
        coords = placement_coords.get(placement_id, (None, None))
        if coords[0] is None:
            continue

        role_type = get_role_type(role_id)
        is_hand_role = role_id in HAND_ROLE_IDS
        is_foot_role = role_id in FOOT_ROLE_IDS

        hold_data.append({
            "placement_id": placement_id,
            "x": coords[0],
            "y": coords[1],
            "role_type": role_type,
            "is_hand": is_hand_role,
            "is_foot": is_foot_role,
        })

    if not hold_data:
        raise ValueError("No valid holds found after parsing frames.")

    df_holds = pd.DataFrame(hold_data)

    hand_holds = df_holds[df_holds["is_hand"]]
    foot_holds = df_holds[df_holds["is_foot"]]
    start_holds = df_holds[df_holds["role_type"] == "start"]
    finish_holds = df_holds[df_holds["role_type"] == "finish"]
    middle_holds = df_holds[df_holds["role_type"] == "middle"]

    xs = df_holds["x"].to_numpy()
    ys = df_holds["y"].to_numpy()

    desc = str(description) if description is not None else ""
    if pd.isna(desc):
        desc = ""

    center_x = (x_min + x_max) / 2
    features = {}

    # Core / counts
    features["angle"] = float(angle)
    features["angle_squared"] = float(angle) ** 2
    features["total_holds"] = int(len(df_holds))
    features["hand_holds"] = int(len(hand_holds))
    features["foot_holds"] = int(len(foot_holds))
    features["start_holds"] = int(len(start_holds))
    features["finish_holds"] = int(len(finish_holds))
    features["middle_holds"] = int(len(middle_holds))
    features["is_nomatch"] = int(
        (is_nomatch == 1) or
        bool(re.search(r"\bno\s*match(ing)?\b", desc, flags=re.IGNORECASE))
    )

    # Spatial
    features["mean_y"] = float(np.mean(ys))
    features["std_x"] = float(np.std(xs)) if len(xs) > 1 else 0.0
    features["std_y"] = float(np.std(ys)) if len(ys) > 1 else 0.0
    features["range_x"] = float(np.max(xs) - np.min(xs))
    features["range_y"] = float(np.max(ys) - np.min(ys))
    features["min_y"] = float(np.min(ys))
    features["max_y"] = float(np.max(ys))
    features["height_gained"] = features["max_y"] - features["min_y"]

    start_height = float(start_holds["y"].mean()) if len(start_holds) > 0 else np.nan
    finish_height = float(finish_holds["y"].mean()) if len(finish_holds) > 0 else np.nan
    features["height_gained_start_finish"] = (
        finish_height - start_height
        if pd.notna(start_height) and pd.notna(finish_height)
        else np.nan
    )

    # Density / symmetry
    bbox_area = features["range_x"] * features["range_y"]
    features["bbox_area"] = float(bbox_area)
    features["hold_density"] = float(features["total_holds"] / bbox_area) if bbox_area > 0 else 0.0
    features["holds_per_vertical_foot"] = float(features["total_holds"] / max(features["range_y"], 1))

    left_holds = int((df_holds["x"] < center_x).sum())
    features["left_ratio"] = left_holds / features["total_holds"] if features["total_holds"] > 0 else 0.5
    features["symmetry_score"] = 1 - abs(features["left_ratio"] - 0.5) * 2

    y_median = np.median(ys)
    upper_holds = int((df_holds["y"] > y_median).sum())
    features["upper_ratio"] = upper_holds / features["total_holds"]

    # Hand reach
    if len(hand_holds) >= 2:
        hand_points = hand_holds[["x", "y"]].to_numpy()
        hand_distances = pdist(hand_points)
        hand_xs = hand_holds["x"].to_numpy()
        hand_ys = hand_holds["y"].to_numpy()

        features["mean_hand_reach"] = float(np.mean(hand_distances))
        features["max_hand_reach"] = float(np.max(hand_distances))
        features["std_hand_reach"] = float(np.std(hand_distances))
        features["hand_spread_x"] = float(hand_xs.max() - hand_xs.min())
        features["hand_spread_y"] = float(hand_ys.max() - hand_ys.min())
    else:
        features["mean_hand_reach"] = 0.0
        features["max_hand_reach"] = 0.0
        features["std_hand_reach"] = 0.0
        features["hand_spread_x"] = 0.0
        features["hand_spread_y"] = 0.0

    # Hand-foot distances
    if len(hand_holds) > 0 and len(foot_holds) > 0:
        hand_points = hand_holds[["x", "y"]].to_numpy()
        foot_points = foot_holds[["x", "y"]].to_numpy()
        dists = []
        for hx, hy in hand_points:
            for fx, fy in foot_points:
                dists.append(np.sqrt((hx - fx) ** 2 + (hy - fy) ** 2))
        dists = np.asarray(dists, dtype=float)

        features["min_hand_to_foot"] = float(np.min(dists))
        features["mean_hand_to_foot"] = float(np.mean(dists))
        features["std_hand_to_foot"] = float(np.std(dists))
    else:
        features["min_hand_to_foot"] = 0.0
        features["mean_hand_to_foot"] = 0.0
        features["std_hand_to_foot"] = 0.0

    # Global geometry
    points = np.column_stack([xs, ys])

    if len(df_holds) >= 3:
        try:
            hull = ConvexHull(points)
            features["convex_hull_area"] = float(hull.volume)
            features["hull_area_to_bbox_ratio"] = float(features["convex_hull_area"] / max(bbox_area, 1))
        except Exception:
            features["convex_hull_area"] = np.nan
            features["hull_area_to_bbox_ratio"] = np.nan
    else:
        features["convex_hull_area"] = 0.0
        features["hull_area_to_bbox_ratio"] = 0.0

    if len(df_holds) >= 2:
        pairwise = pdist(points)
        features["mean_pairwise_distance"] = float(np.mean(pairwise))
        features["std_pairwise_distance"] = float(np.std(pairwise))
    else:
        features["mean_pairwise_distance"] = 0.0
        features["std_pairwise_distance"] = 0.0

    if len(df_holds) >= 2:
        sorted_idx = np.argsort(ys)
        sorted_points = points[sorted_idx]
        path_length = 0.0
        for i in range(len(sorted_points) - 1):
            dx = sorted_points[i + 1, 0] - sorted_points[i, 0]
            dy = sorted_points[i + 1, 1] - sorted_points[i, 1]
            path_length += np.sqrt(dx ** 2 + dy ** 2)

        features["path_length_vertical"] = float(path_length)
        features["path_efficiency"] = float(features["height_gained"] / max(path_length, 1))
    else:
        features["path_length_vertical"] = 0.0
        features["path_efficiency"] = 0.0

    # Normalized / relative
    features["mean_y_normalized"] = float((features["mean_y"] - y_min) / board_height)
    features["start_height_normalized"] = float((start_height - y_min) / board_height) if pd.notna(start_height) else np.nan
    features["finish_height_normalized"] = float((finish_height - y_min) / board_height) if pd.notna(finish_height) else np.nan
    features["mean_y_relative_to_start"] = float(features["mean_y"] - start_height) if pd.notna(start_height) else np.nan
    features["spread_x_normalized"] = float(features["range_x"] / board_width)
    features["spread_y_normalized"] = float(features["range_y"] / board_height)

    y_q75 = np.percentile(ys, 75)
    y_q25 = np.percentile(ys, 25)
    features["y_q75"] = float(y_q75)
    features["y_iqr"] = float(y_q75 - y_q25)

    # Engineered clean features
    features["complexity_score"] = float(
        features["mean_hand_reach"]
        * np.log1p(features["total_holds"])
        * (1 + features["hold_density"])
    )
    features["angle_x_holds"] = float(features["angle"] * features["total_holds"])

    return features


# ============================================================
# Model input preparation
# ============================================================

def prepare_feature_vector(features: dict) -> pd.DataFrame:
    row = {}
    for col in FEATURE_NAMES:
        value = features.get(col, 0.0)
        row[col] = 0.0 if pd.isna(value) else value
    return pd.DataFrame([row], columns=FEATURE_NAMES)


# ============================================================
# Prediction helpers
# ============================================================

def format_prediction(pred: float):
    rounded = int(round(pred))
    rounded = max(min(rounded, MAX_GRADE), MIN_GRADE)

    return {
        "predicted_numeric": float(pred),
        "predicted_display_difficulty": rounded,
        "predicted_boulder_grade": grade_map[rounded],
    }


def predict_with_model(model, X: pd.DataFrame, model_name: str):
    model_name = normalize_model_name(model_name)
    info = MODEL_REGISTRY[model_name]

    if info["kind"] == "sklearn":
        X_input = scaler.transform(X) if info["needs_scaling"] else X
        pred = model.predict(X_input)[0]
        return float(pred)

    if info["kind"] == "torch_checkpoint":
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch is not installed.")

        X_input = scaler.transform(X) if info["needs_scaling"] else X
        X_tensor = torch.tensor(np.asarray(X_input), dtype=torch.float32)

        with torch.no_grad():
            out = model(X_tensor)

        if isinstance(out, tuple):
            out = out[0]

        pred = np.asarray(out).reshape(-1)[0]
        return float(pred)

    raise ValueError(f"Unsupported model kind: {info['kind']}")


# ============================================================
# Public API
# ============================================================

def predict(
    angle,
    frames,
    is_nomatch=0,
    description="",
    model_name=DEFAULT_MODEL,
    return_numeric=False,
    debug=False,
):
    model_name = normalize_model_name(model_name)
    model = load_model(model_name)

    features = extract_features_from_raw(
        angle=angle,
        frames=frames,
        is_nomatch=is_nomatch,
        description=description,
    )

    X = prepare_feature_vector(features)

    if debug:
        print("\nNonzero / non-null feature values:")
        for col, val in X.iloc[0].items():
            if pd.notna(val) and val != 0:
                print(f"{col}: {val}")

    pred = predict_with_model(model, X, model_name=model_name)

    if return_numeric:
        return float(pred)

    result = format_prediction(pred)
    result["model"] = model_name
    return result


def predict_csv(
    input_csv,
    output_csv=None,
    model_name=DEFAULT_MODEL,
    angle_col="angle",
    frames_col="frames",
    is_nomatch_col="is_nomatch",
    description_col="description",
):
    """
    Batch prediction over a CSV file.

    Required columns:
        - angle
        - frames

    Optional columns:
        - is_nomatch
        - description
    """
    model_name = normalize_model_name(model_name)

    df = pd.read_csv(input_csv)

    if angle_col not in df.columns:
        raise ValueError(f"Missing required column: '{angle_col}'")
    if frames_col not in df.columns:
        raise ValueError(f"Missing required column: '{frames_col}'")

    results = []

    for _, row in df.iterrows():
        angle = row[angle_col]
        frames = row[frames_col]
        is_nomatch = row[is_nomatch_col] if is_nomatch_col in df.columns and pd.notna(row[is_nomatch_col]) else 0
        description = row[description_col] if description_col in df.columns and pd.notna(row[description_col]) else ""

        pred = predict(
            angle=angle,
            frames=frames,
            is_nomatch=is_nomatch,
            description=description,
            model_name=model_name,
            return_numeric=False,
            debug=False,
        )

        results.append(pred)

    pred_df = pd.DataFrame(results)
    out = pd.concat([df.reset_index(drop=True), pred_df.reset_index(drop=True)], axis=1)

    if output_csv is not None:
        out.to_csv(output_csv, index=False)

    return out


def evaluate_predictions(df, true_col="display_difficulty", pred_col="predicted_numeric"):
    """
    Simple evaluation summary for labeled batch predictions.
    """
    if true_col not in df.columns:
        raise ValueError(f"Missing true target column: '{true_col}'")
    if pred_col not in df.columns:
        raise ValueError(f"Missing prediction column: '{pred_col}'")

    y_true = df[true_col].astype(float)
    y_pred = df[pred_col].astype(float)

    mae = np.mean(np.abs(y_true - y_pred))
    rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))
    within_1 = np.mean(np.abs(y_true - y_pred) <= 1)
    within_2 = np.mean(np.abs(y_true - y_pred) <= 2)

    return {
        "mae": float(mae),
        "rmse": float(rmse),
        "within_1": float(within_1),
        "within_2": float(within_2),
    }


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()

    # Single prediction mode
    parser.add_argument("--angle", type=int)
    parser.add_argument("--frames", type=str)
    parser.add_argument("--is_nomatch", type=int, default=0)
    parser.add_argument("--description", type=str, default="")

    # Batch mode
    parser.add_argument("--input_csv", type=str)
    parser.add_argument("--output_csv", type=str)

    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        choices=list(MODEL_REGISTRY.keys()) + ["nn"],
        help="Which trained model to use",
    )
    parser.add_argument("--numeric", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--evaluate", action="store_true")

    args = parser.parse_args()

    if args.input_csv:
        df_out = predict_csv(
            input_csv=args.input_csv,
            output_csv=args.output_csv,
            model_name=args.model,
        )

        print(df_out.head())

        if args.evaluate:
            try:
                metrics = evaluate_predictions(df_out)
                print("\nEvaluation:")
                for k, v in metrics.items():
                    print(f"{k}: {v:.4f}")
            except Exception as e:
                print(f"\nCould not evaluate predictions: {e}")

    else:
        if args.angle is None or args.frames is None:
            raise ValueError("For single prediction, you must provide --angle and --frames")

        pred = predict(
            angle=args.angle,
            frames=args.frames,
            is_nomatch=args.is_nomatch,
            description=args.description,
            model_name=args.model,
            return_numeric=args.numeric,
            debug=args.debug,
        )
        print(pred)