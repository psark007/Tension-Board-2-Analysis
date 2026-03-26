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
HOLD_DIFFICULTY_PATH = ROOT / "data" / "03_hold_difficulty" / "hold_difficulty_scores.csv"
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

df_hold_difficulty = pd.read_csv(HOLD_DIFFICULTY_PATH, index_col="placement_id")
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


def lookup_hold_difficulty(placement_id, angle, role_type, is_hand, is_foot):
    """
    Preference order:
    1. role-specific per-angle
    2. aggregate hand/foot per-angle
    3. overall_difficulty fallback
    """
    if placement_id not in df_hold_difficulty.index:
        return np.nan

    row = df_hold_difficulty.loc[placement_id]

    diff_key = f"{role_type}_diff_{int(angle)}deg"
    hand_diff_key = f"hand_diff_{int(angle)}deg"
    foot_diff_key = f"foot_diff_{int(angle)}deg"

    difficulty = np.nan

    if diff_key in row.index:
        difficulty = row[diff_key]

    if pd.isna(difficulty):
        if is_hand and hand_diff_key in row.index:
            difficulty = row[hand_diff_key]
        elif is_foot and foot_diff_key in row.index:
            difficulty = row[foot_diff_key]

    if pd.isna(difficulty) and "overall_difficulty" in row.index:
        difficulty = row["overall_difficulty"]

    return difficulty


# ============================================================
# Feature extraction
# ============================================================

def extract_features_from_raw(angle, frames, is_nomatch=0, description=""):
    features = {}

    holds = parse_frames(frames)
    if not holds:
        raise ValueError("Could not parse any holds from frames.")

    hold_data = []
    for placement_id, role_id in holds:
        coords = placement_coords.get(placement_id, (None, None))
        if coords[0] is None:
            continue

        role_type = get_role_type(role_id)
        is_hand = role_id in HAND_ROLE_IDS
        is_foot = role_id in FOOT_ROLE_IDS

        difficulty = lookup_hold_difficulty(
            placement_id=placement_id,
            angle=angle,
            role_type=role_type,
            is_hand=is_hand,
            is_foot=is_foot,
        )

        hold_data.append({
            "placement_id": placement_id,
            "x": coords[0],
            "y": coords[1],
            "role_id": role_id,
            "role_type": role_type,
            "is_hand": is_hand,
            "is_foot": is_foot,
            "difficulty": difficulty,
        })

    if not hold_data:
        raise ValueError("No valid holds found after parsing frames.")

    df_holds = pd.DataFrame(hold_data)

    hand_holds = df_holds[df_holds["is_hand"]]
    foot_holds = df_holds[df_holds["is_foot"]]
    start_holds = df_holds[df_holds["role_type"] == "start"]
    finish_holds = df_holds[df_holds["role_type"] == "finish"]
    middle_holds = df_holds[df_holds["role_type"] == "middle"]

    xs = df_holds["x"].values
    ys = df_holds["y"].values

    features["angle"] = angle

    features["total_holds"] = len(df_holds)
    features["hand_holds"] = len(hand_holds)
    features["foot_holds"] = len(foot_holds)
    features["start_holds"] = len(start_holds)
    features["finish_holds"] = len(finish_holds)
    features["middle_holds"] = len(middle_holds)

    desc = str(description) if description is not None else ""
    features["is_nomatch"] = int(
        (is_nomatch == 1) or
        bool(re.search(r"\bno\s*match(ing)?\b", desc, flags=re.IGNORECASE))
    )

    features["mean_x"] = np.mean(xs)
    features["mean_y"] = np.mean(ys)
    features["std_x"] = np.std(xs) if len(xs) > 1 else 0
    features["std_y"] = np.std(ys) if len(ys) > 1 else 0
    features["range_x"] = np.max(xs) - np.min(xs)
    features["range_y"] = np.max(ys) - np.min(ys)
    features["min_y"] = np.min(ys)
    features["max_y"] = np.max(ys)

    if len(start_holds) > 0:
        features["start_height"] = start_holds["y"].mean()
        features["start_height_min"] = start_holds["y"].min()
        features["start_height_max"] = start_holds["y"].max()
    else:
        features["start_height"] = np.nan
        features["start_height_min"] = np.nan
        features["start_height_max"] = np.nan

    if len(finish_holds) > 0:
        features["finish_height"] = finish_holds["y"].mean()
        features["finish_height_min"] = finish_holds["y"].min()
        features["finish_height_max"] = finish_holds["y"].max()
    else:
        features["finish_height"] = np.nan
        features["finish_height_min"] = np.nan
        features["finish_height_max"] = np.nan

    features["height_gained"] = features["max_y"] - features["min_y"]

    if pd.notna(features["finish_height"]) and pd.notna(features["start_height"]):
        features["height_gained_start_finish"] = features["finish_height"] - features["start_height"]
    else:
        features["height_gained_start_finish"] = np.nan

    bbox_width = features["range_x"]
    bbox_height = features["range_y"]
    features["bbox_area"] = bbox_width * bbox_height
    features["bbox_aspect_ratio"] = bbox_width / bbox_height if bbox_height > 0 else 0
    features["bbox_normalized_area"] = features["bbox_area"] / (board_width * board_height)

    features["hold_density"] = features["total_holds"] / features["bbox_area"] if features["bbox_area"] > 0 else 0
    features["holds_per_vertical_foot"] = features["total_holds"] / max(features["range_y"], 1)

    center_x = (x_min + x_max) / 2
    features["left_holds"] = (df_holds["x"] < center_x).sum()
    features["right_holds"] = (df_holds["x"] >= center_x).sum()
    features["left_ratio"] = features["left_holds"] / features["total_holds"] if features["total_holds"] > 0 else 0.5
    features["symmetry_score"] = 1 - abs(features["left_ratio"] - 0.5) * 2

    if len(hand_holds) > 0:
        hand_left = (hand_holds["x"] < center_x).sum()
        features["hand_left_ratio"] = hand_left / len(hand_holds)
        features["hand_symmetry"] = 1 - abs(features["hand_left_ratio"] - 0.5) * 2
    else:
        features["hand_left_ratio"] = np.nan
        features["hand_symmetry"] = np.nan

    y_median = np.median(ys)
    features["upper_holds"] = (df_holds["y"] > y_median).sum()
    features["lower_holds"] = (df_holds["y"] <= y_median).sum()
    features["upper_ratio"] = features["upper_holds"] / features["total_holds"]

    if len(hand_holds) >= 2:
        hand_xs = hand_holds["x"].values
        hand_ys = hand_holds["y"].values

        hand_distances = []
        for i in range(len(hand_holds)):
            for j in range(i + 1, len(hand_holds)):
                dx = hand_xs[i] - hand_xs[j]
                dy = hand_ys[i] - hand_ys[j]
                hand_distances.append(np.sqrt(dx**2 + dy**2))

        features["max_hand_reach"] = max(hand_distances)
        features["min_hand_reach"] = min(hand_distances)
        features["mean_hand_reach"] = np.mean(hand_distances)
        features["std_hand_reach"] = np.std(hand_distances)
        features["hand_spread_x"] = hand_xs.max() - hand_xs.min()
        features["hand_spread_y"] = hand_ys.max() - hand_ys.min()
    else:
        features["max_hand_reach"] = 0
        features["min_hand_reach"] = 0
        features["mean_hand_reach"] = 0
        features["std_hand_reach"] = 0
        features["hand_spread_x"] = 0
        features["hand_spread_y"] = 0

    if len(foot_holds) >= 2:
        foot_xs = foot_holds["x"].values
        foot_ys = foot_holds["y"].values

        foot_distances = []
        for i in range(len(foot_holds)):
            for j in range(i + 1, len(foot_holds)):
                dx = foot_xs[i] - foot_xs[j]
                dy = foot_ys[i] - foot_ys[j]
                foot_distances.append(np.sqrt(dx**2 + dy**2))

        features["max_foot_spread"] = max(foot_distances)
        features["mean_foot_spread"] = np.mean(foot_distances)
        features["foot_spread_x"] = foot_xs.max() - foot_xs.min()
        features["foot_spread_y"] = foot_ys.max() - foot_ys.min()
    else:
        features["max_foot_spread"] = 0
        features["mean_foot_spread"] = 0
        features["foot_spread_x"] = 0
        features["foot_spread_y"] = 0

    if len(hand_holds) > 0 and len(foot_holds) > 0:
        h2f_distances = []
        for _, h in hand_holds.iterrows():
            for _, f in foot_holds.iterrows():
                dx = h["x"] - f["x"]
                dy = h["y"] - f["y"]
                h2f_distances.append(np.sqrt(dx**2 + dy**2))

        features["max_hand_to_foot"] = max(h2f_distances)
        features["min_hand_to_foot"] = min(h2f_distances)
        features["mean_hand_to_foot"] = np.mean(h2f_distances)
        features["std_hand_to_foot"] = np.std(h2f_distances)
    else:
        features["max_hand_to_foot"] = 0
        features["min_hand_to_foot"] = 0
        features["mean_hand_to_foot"] = 0
        features["std_hand_to_foot"] = 0

    difficulties = df_holds["difficulty"].dropna().values

    if len(difficulties) > 0:
        features["mean_hold_difficulty"] = np.mean(difficulties)
        features["max_hold_difficulty"] = np.max(difficulties)
        features["min_hold_difficulty"] = np.min(difficulties)
        features["std_hold_difficulty"] = np.std(difficulties)
        features["median_hold_difficulty"] = np.median(difficulties)
        features["difficulty_range"] = features["max_hold_difficulty"] - features["min_hold_difficulty"]
    else:
        features["mean_hold_difficulty"] = np.nan
        features["max_hold_difficulty"] = np.nan
        features["min_hold_difficulty"] = np.nan
        features["std_hold_difficulty"] = np.nan
        features["median_hold_difficulty"] = np.nan
        features["difficulty_range"] = np.nan

    hand_diffs = hand_holds["difficulty"].dropna().values if len(hand_holds) > 0 else np.array([])
    if len(hand_diffs) > 0:
        features["mean_hand_difficulty"] = np.mean(hand_diffs)
        features["max_hand_difficulty"] = np.max(hand_diffs)
        features["std_hand_difficulty"] = np.std(hand_diffs)
    else:
        features["mean_hand_difficulty"] = np.nan
        features["max_hand_difficulty"] = np.nan
        features["std_hand_difficulty"] = np.nan

    foot_diffs = foot_holds["difficulty"].dropna().values if len(foot_holds) > 0 else np.array([])
    if len(foot_diffs) > 0:
        features["mean_foot_difficulty"] = np.mean(foot_diffs)
        features["max_foot_difficulty"] = np.max(foot_diffs)
        features["std_foot_difficulty"] = np.std(foot_diffs)
    else:
        features["mean_foot_difficulty"] = np.nan
        features["max_foot_difficulty"] = np.nan
        features["std_foot_difficulty"] = np.nan

    start_diffs = start_holds["difficulty"].dropna().values if len(start_holds) > 0 else np.array([])
    finish_diffs = finish_holds["difficulty"].dropna().values if len(finish_holds) > 0 else np.array([])
    features["start_difficulty"] = np.mean(start_diffs) if len(start_diffs) > 0 else np.nan
    features["finish_difficulty"] = np.mean(finish_diffs) if len(finish_diffs) > 0 else np.nan

    features["hand_foot_ratio"] = features["hand_holds"] / max(features["foot_holds"], 1)
    features["movement_density"] = features["total_holds"] / max(features["height_gained"], 1)
    features["hold_com_x"] = np.average(xs)
    features["hold_com_y"] = np.average(ys)

    if len(difficulties) > 0 and len(ys) >= len(difficulties):
        weights = (ys[:len(difficulties)] - ys.min()) / max(ys.max() - ys.min(), 1) + 0.5
        features["weighted_difficulty"] = np.average(difficulties, weights=weights)
    else:
        features["weighted_difficulty"] = features["mean_hold_difficulty"]

    if len(df_holds) >= 3:
        try:
            points = np.column_stack([xs, ys])
            hull = ConvexHull(points)
            features["convex_hull_area"] = hull.volume
            features["convex_hull_perimeter"] = hull.area
            features["hull_area_to_bbox_ratio"] = features["convex_hull_area"] / max(features["bbox_area"], 1)
        except Exception:
            features["convex_hull_area"] = np.nan
            features["convex_hull_perimeter"] = np.nan
            features["hull_area_to_bbox_ratio"] = np.nan
    else:
        features["convex_hull_area"] = 0
        features["convex_hull_perimeter"] = 0
        features["hull_area_to_bbox_ratio"] = 0

    if len(df_holds) >= 2:
        points = np.column_stack([xs, ys])
        distances = pdist(points)
        features["min_nn_distance"] = np.min(distances)
        features["mean_nn_distance"] = np.mean(distances)
        features["max_nn_distance"] = np.max(distances)
        features["std_nn_distance"] = np.std(distances)
    else:
        features["min_nn_distance"] = 0
        features["mean_nn_distance"] = 0
        features["max_nn_distance"] = 0
        features["std_nn_distance"] = 0

    if len(df_holds) >= 3:
        points = np.column_stack([xs, ys])
        dist_matrix = squareform(pdist(points))
        threshold = 12.0
        neighbors_count = (dist_matrix < threshold).sum(axis=1) - 1
        features["mean_neighbors_12in"] = np.mean(neighbors_count)
        features["max_neighbors_12in"] = np.max(neighbors_count)
        avg_neighbors = np.mean(neighbors_count)
        max_possible = len(df_holds) - 1
        features["clustering_ratio"] = avg_neighbors / max_possible if max_possible > 0 else 0
    else:
        features["mean_neighbors_12in"] = 0
        features["max_neighbors_12in"] = 0
        features["clustering_ratio"] = 0

    if len(df_holds) >= 2:
        sorted_indices = np.argsort(ys)
        sorted_points = np.column_stack([xs[sorted_indices], ys[sorted_indices]])

        path_length = 0
        for i in range(len(sorted_points) - 1):
            dx = sorted_points[i + 1, 0] - sorted_points[i, 0]
            dy = sorted_points[i + 1, 1] - sorted_points[i, 1]
            path_length += np.sqrt(dx**2 + dy**2)

        features["path_length_vertical"] = path_length
        features["path_efficiency"] = features["height_gained"] / max(path_length, 1)
    else:
        features["path_length_vertical"] = 0
        features["path_efficiency"] = 0

    if pd.notna(features["finish_difficulty"]) and pd.notna(features["start_difficulty"]):
        features["difficulty_gradient"] = features["finish_difficulty"] - features["start_difficulty"]
    else:
        features["difficulty_gradient"] = np.nan

    if len(difficulties) > 0:
        y_min_val, y_max_val = ys.min(), ys.max()
        y_range = y_max_val - y_min_val

        if y_range > 0:
            lower_mask = ys <= (y_min_val + y_range / 3)
            middle_mask = (ys > y_min_val + y_range / 3) & (ys <= y_min_val + 2 * y_range / 3)
            upper_mask = ys > (y_min_val + 2 * y_range / 3)

            df_with_diff = df_holds.copy()
            df_with_diff["lower"] = lower_mask
            df_with_diff["middle"] = middle_mask
            df_with_diff["upper"] = upper_mask

            lower_diffs = df_with_diff[df_with_diff["lower"] & df_with_diff["difficulty"].notna()]["difficulty"]
            middle_diffs = df_with_diff[df_with_diff["middle"] & df_with_diff["difficulty"].notna()]["difficulty"]
            upper_diffs = df_with_diff[df_with_diff["upper"] & df_with_diff["difficulty"].notna()]["difficulty"]

            features["lower_region_difficulty"] = lower_diffs.mean() if len(lower_diffs) > 0 else np.nan
            features["middle_region_difficulty"] = middle_diffs.mean() if len(middle_diffs) > 0 else np.nan
            features["upper_region_difficulty"] = upper_diffs.mean() if len(upper_diffs) > 0 else np.nan

            if pd.notna(features["lower_region_difficulty"]) and pd.notna(features["upper_region_difficulty"]):
                features["difficulty_progression"] = features["upper_region_difficulty"] - features["lower_region_difficulty"]
            else:
                features["difficulty_progression"] = np.nan
        else:
            features["lower_region_difficulty"] = features["mean_hold_difficulty"]
            features["middle_region_difficulty"] = features["mean_hold_difficulty"]
            features["upper_region_difficulty"] = features["mean_hold_difficulty"]
            features["difficulty_progression"] = 0
    else:
        features["lower_region_difficulty"] = np.nan
        features["middle_region_difficulty"] = np.nan
        features["upper_region_difficulty"] = np.nan
        features["difficulty_progression"] = np.nan

    if len(hand_holds) >= 2 and len(hand_diffs) >= 2:
        hand_sorted = hand_holds.sort_values("y")
        hand_diff_sorted = hand_sorted["difficulty"].dropna().values

        if len(hand_diff_sorted) >= 2:
            difficulty_jumps = np.abs(np.diff(hand_diff_sorted))
            features["max_difficulty_jump"] = np.max(difficulty_jumps) if len(difficulty_jumps) > 0 else 0
            features["mean_difficulty_jump"] = np.mean(difficulty_jumps) if len(difficulty_jumps) > 0 else 0
        else:
            features["max_difficulty_jump"] = 0
            features["mean_difficulty_jump"] = 0
    else:
        features["max_difficulty_jump"] = 0
        features["mean_difficulty_jump"] = 0

    if len(hand_holds) >= 2 and len(hand_diffs) >= 2:
        hand_sorted = hand_holds.sort_values("y")
        xs_sorted = hand_sorted["x"].values
        ys_sorted = hand_sorted["y"].values
        diffs_sorted = hand_sorted["difficulty"].fillna(np.mean(hand_diffs)).values

        weighted_reach = []
        for i in range(len(hand_sorted) - 1):
            dx = xs_sorted[i + 1] - xs_sorted[i]
            dy = ys_sorted[i + 1] - ys_sorted[i]
            dist = np.sqrt(dx**2 + dy**2)
            avg_diff = (diffs_sorted[i] + diffs_sorted[i + 1]) / 2
            weighted_reach.append(dist * avg_diff)

        features["difficulty_weighted_reach"] = np.mean(weighted_reach) if weighted_reach else 0
        features["max_weighted_reach"] = np.max(weighted_reach) if weighted_reach else 0
    else:
        features["difficulty_weighted_reach"] = 0
        features["max_weighted_reach"] = 0

    features["mean_x_normalized"] = (features["mean_x"] - x_min) / board_width
    features["mean_y_normalized"] = (features["mean_y"] - y_min) / board_height
    features["std_x_normalized"] = features["std_x"] / board_width
    features["std_y_normalized"] = features["std_y"] / board_height

    if pd.notna(features["start_height"]):
        features["start_height_normalized"] = (features["start_height"] - y_min) / board_height
    else:
        features["start_height_normalized"] = np.nan

    if pd.notna(features["finish_height"]):
        features["finish_height_normalized"] = (features["finish_height"] - y_min) / board_height
    else:
        features["finish_height_normalized"] = np.nan

    typical_start_y = y_min + board_height * 0.15
    typical_finish_y = y_min + board_height * 0.85

    if pd.notna(features["start_height"]):
        features["start_offset_from_typical"] = abs(features["start_height"] - typical_start_y)
    else:
        features["start_offset_from_typical"] = np.nan

    if pd.notna(features["finish_height"]):
        features["finish_offset_from_typical"] = abs(features["finish_height"] - typical_finish_y)
    else:
        features["finish_offset_from_typical"] = np.nan

    if len(start_holds) > 0:
        start_y = start_holds["y"].mean()
        features["mean_y_relative_to_start"] = features["mean_y"] - start_y
        features["max_y_relative_to_start"] = features["max_y"] - start_y
    else:
        features["mean_y_relative_to_start"] = np.nan
        features["max_y_relative_to_start"] = np.nan

    features["spread_x_normalized"] = features["range_x"] / board_width
    features["spread_y_normalized"] = features["range_y"] / board_height
    features["bbox_coverage_x"] = features["range_x"] / board_width
    features["bbox_coverage_y"] = features["range_y"] / board_height

    y_quartiles = np.percentile(ys, [25, 50, 75])
    features["y_q25"] = y_quartiles[0]
    features["y_q50"] = y_quartiles[1]
    features["y_q75"] = y_quartiles[2]
    features["y_iqr"] = y_quartiles[2] - y_quartiles[0]

    features["holds_bottom_quartile"] = (ys < y_quartiles[0]).sum()
    features["holds_top_quartile"] = (ys >= y_quartiles[2]).sum()

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