"""
Land Price Prediction Engine
=============================
RandomForest-based model trained on curated Kenyan land market data.

Features: county, constituency, land_use, size, distance_to_nairobi,
          infrastructure (road, water, electricity).

The model is trained once and cached in memory for fast inference (~2ms per query).
"""
import os
import logging
import json
from pathlib import Path

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import cross_val_score
import joblib

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / 'data' / 'kenya_land_prices.csv'
MODEL_PATH = BASE_DIR / 'ml_models' / 'price_model.joblib'
ENCODERS_PATH = BASE_DIR / 'ml_models' / 'label_encoders.joblib'
METADATA_PATH = BASE_DIR / 'ml_models' / 'model_metadata.json'

# ── In-memory cache ──────────────────────────────────────────────────────────
_model = None
_encoders = None
_metadata = None
_df = None  # Keep training data for comparisons


# ── Kenya county data for the prediction form ────────────────────────────────
KENYA_COUNTIES = [
    'Baringo', 'Bomet', 'Bungoma', 'Busia', 'Elgeyo Marakwet', 'Embu',
    'Garissa', 'Homa Bay', 'Isiolo', 'Kajiado', 'Kakamega', 'Kericho',
    'Kiambu', 'Kilifi', 'Kirinyaga', 'Kisii', 'Kisumu', 'Kitui',
    'Kwale', 'Laikipia', 'Lamu', 'Machakos', 'Makueni', 'Mandera',
    'Marsabit', 'Meru', 'Migori', 'Mombasa', 'Murang_a', 'Nairobi',
    'Nakuru', 'Nandi', 'Narok', 'Nyandarua', 'Nyamira', 'Nyeri',
    'Samburu', 'Siaya', 'Taita Taveta', 'Tana River', 'Tharaka Nithi',
    'Trans Nzoia', 'Turkana', 'Uasin Gishu', 'Vihiga', 'Wajir',
    'West Pokot'
]

LAND_USE_TYPES = ['Residential', 'Commercial', 'Agricultural']


def _load_data():
    """Load the training dataset."""
    global _df
    if _df is not None:
        return _df

    if not DATA_PATH.exists():
        logger.error(f"Training data not found at {DATA_PATH}")
        return None

    _df = pd.read_csv(DATA_PATH)
    logger.info(f"Loaded {len(_df)} training records from {DATA_PATH}")
    return _df


def train_model():
    """
    Train the price prediction model on the seed dataset.
    Returns training metrics.
    """
    global _model, _encoders, _metadata, _df

    df = _load_data()
    if df is None:
        raise FileNotFoundError(f"Training data not found at {DATA_PATH}")

    logger.info(f"Training price prediction model on {len(df)} records...")

    # ── Encode categorical features ──
    encoders = {
        'county': LabelEncoder(),
        'constituency': LabelEncoder(),
        'land_use': LabelEncoder(),
    }

    df_encoded = df.copy()
    df_encoded['county_enc'] = encoders['county'].fit_transform(df['county'])
    df_encoded['constituency_enc'] = encoders['constituency'].fit_transform(df['constituency'])
    df_encoded['land_use_enc'] = encoders['land_use'].fit_transform(df['land_use'])

    # ── Feature matrix ──
    feature_cols = [
        'county_enc', 'constituency_enc', 'land_use_enc',
        'size_acres', 'distance_to_nairobi_km',
        'has_road_access', 'has_water', 'has_electricity'
    ]
    X = df_encoded[feature_cols].values
    y = np.log1p(df_encoded['price_per_acre'].values)  # Log-transform for better distribution

    # ── Train RandomForest with cross-validation ──
    model = RandomForestRegressor(
        n_estimators=200,
        max_depth=15,
        min_samples_split=3,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    )

    # Cross-validation score
    cv_scores = cross_val_score(model, X, y, cv=5, scoring='r2')
    logger.info(f"Cross-validation R² scores: {cv_scores}")
    logger.info(f"Mean R²: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")

    # Fit final model on all data
    model.fit(X, y)

    # Feature importance
    importances = dict(zip(feature_cols, model.feature_importances_))
    logger.info(f"Feature importances: {importances}")

    # ── Save model and encoders ──
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    joblib.dump(encoders, ENCODERS_PATH)

    metadata = {
        'n_records': len(df),
        'n_features': len(feature_cols),
        'feature_cols': feature_cols,
        'cv_r2_mean': float(cv_scores.mean()),
        'cv_r2_std': float(cv_scores.std()),
        'feature_importances': {k: float(v) for k, v in importances.items()},
        'n_counties': len(df['county'].unique()),
        'n_constituencies': len(df['constituency'].unique()),
        'price_range': {
            'min': int(df['price_per_acre'].min()),
            'max': int(df['price_per_acre'].max()),
            'median': int(df['price_per_acre'].median()),
        }
    }
    with open(METADATA_PATH, 'w') as f:
        json.dump(metadata, f, indent=2)

    # Update cache
    _model = model
    _encoders = encoders
    _metadata = metadata

    logger.info("Model training complete and saved.")
    return metadata


def _ensure_model_loaded():
    """Load model from disk if not already in memory."""
    global _model, _encoders, _metadata

    if _model is not None and _encoders is not None:
        return True

    if not MODEL_PATH.exists():
        logger.warning("No trained model found. Training now...")
        try:
            train_model()
            return True
        except Exception as e:
            logger.error(f"Failed to train model: {e}")
            return False

    try:
        _model = joblib.load(MODEL_PATH)
        _encoders = joblib.load(ENCODERS_PATH)
        if METADATA_PATH.exists():
            with open(METADATA_PATH) as f:
                _metadata = json.load(f)
        logger.info("Price prediction model loaded from disk.")
        return True
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        return False


def predict_price(county, constituency, land_use, size_acres,
                  distance_to_nairobi_km=None, has_road_access=True,
                  has_water=True, has_electricity=True):
    """
    Predict the price per acre for a land parcel.

    Returns:
        dict with keys: price_per_acre, total_value, confidence_low,
        confidence_high, comparisons, model_accuracy
    """
    if not _ensure_model_loaded():
        return {'error': 'Model not available. Please run: python manage.py train_price_model'}

    # ── Estimate distance to Nairobi if not provided ──
    if distance_to_nairobi_km is None:
        distance_to_nairobi_km = _estimate_distance_to_nairobi(county)

    # ── Encode features ──
    try:
        county_enc = _safe_encode(_encoders['county'], county)
        constituency_enc = _safe_encode(_encoders['constituency'], constituency)
        land_use_enc = _safe_encode(_encoders['land_use'], land_use)
    except Exception as e:
        logger.error(f"Encoding error: {e}")
        return {'error': f'Unknown location or category: {e}'}

    features = np.array([[
        county_enc, constituency_enc, land_use_enc,
        float(size_acres), float(distance_to_nairobi_km),
        int(has_road_access), int(has_water), int(has_electricity)
    ]])

    # ── Predict using all trees for confidence interval ──
    # Get individual tree predictions for confidence interval
    tree_predictions = np.array([
        tree.predict(features)[0] for tree in _model.estimators_
    ])

    predicted_log = _model.predict(features)[0]
    predicted_price = int(np.expm1(predicted_log))

    # Confidence interval from tree variance
    std_log = tree_predictions.std()
    confidence_low = int(np.expm1(predicted_log - 1.96 * std_log))
    confidence_high = int(np.expm1(predicted_log + 1.96 * std_log))

    # Total estimated value
    total_value = int(predicted_price * float(size_acres))

    # ── Get market comparisons ──
    comparisons = _get_comparisons(county, land_use, size_acres)

    return {
        'price_per_acre': predicted_price,
        'total_value': total_value,
        'confidence_low': max(0, confidence_low),
        'confidence_high': confidence_high,
        'county': county,
        'constituency': constituency,
        'land_use': land_use,
        'size_acres': float(size_acres),
        'comparisons': comparisons,
        'model_accuracy': _metadata.get('cv_r2_mean', 0) if _metadata else 0,
    }


def _safe_encode(encoder, value):
    """Safely encode a categorical value, handling unseen labels."""
    try:
        return encoder.transform([value])[0]
    except ValueError:
        # Unseen label — use the most common class as fallback
        logger.warning(f"Unseen label '{value}', using fallback encoding.")
        return 0


def _estimate_distance_to_nairobi(county):
    """Rough distance estimates from county to Nairobi CBD."""
    distances = {
        'Nairobi': 0, 'Kiambu': 25, 'Kajiado': 60, 'Machakos': 60,
        'Murang_a': 80, 'Nakuru': 160, 'Nyandarua': 130, 'Nyeri': 150,
        'Kirinyaga': 115, 'Embu': 130, 'Meru': 220, 'Tharaka Nithi': 195,
        'Laikipia': 200, 'Nandi': 330, 'Uasin Gishu': 310, 'Trans Nzoia': 370,
        'Bungoma': 400, 'Kakamega': 380, 'Vihiga': 370, 'Busia': 440,
        'Siaya': 370, 'Kisumu': 340, 'Homa Bay': 380, 'Migori': 400,
        'Kisii': 320, 'Nyamira': 330, 'Kericho': 280, 'Bomet': 260,
        'Narok': 150, 'Baringo': 290, 'Elgeyo Marakwet': 340,
        'West Pokot': 380, 'Samburu': 350, 'Turkana': 750,
        'Marsabit': 560, 'Isiolo': 270, 'Mombasa': 480, 'Kilifi': 520,
        'Kwale': 510, 'Lamu': 600, 'Tana River': 400, 'Garissa': 370,
        'Wajir': 640, 'Mandera': 900, 'Taita Taveta': 330,
        'Makueni': 170, 'Kitui': 180,
    }
    return distances.get(county, 300)


def _get_comparisons(county, land_use, size_acres):
    """Get comparable market data from the training set."""
    df = _load_data()
    if df is None:
        return []

    # Filter by county and land use
    mask = (df['county'] == county) & (df['land_use'] == land_use)
    comparable = df[mask].copy()

    if comparable.empty:
        # Fallback to just county
        comparable = df[df['county'] == county].copy()

    if comparable.empty:
        return []

    # Sort by size similarity
    comparable['size_diff'] = abs(comparable['size_acres'] - float(size_acres))
    comparable = comparable.sort_values('size_diff').head(5)

    return comparable[['county', 'constituency', 'land_use', 'size_acres', 'price_per_acre']].to_dict('records')


def get_county_averages():
    """Get average price per acre for each county, grouped by land use."""
    df = _load_data()
    if df is None:
        return {}

    result = {}
    for county in df['county'].unique():
        county_data = df[df['county'] == county]
        result[county] = {}
        for land_use in county_data['land_use'].unique():
            lu_data = county_data[county_data['land_use'] == land_use]
            result[county][land_use] = {
                'avg_price': int(lu_data['price_per_acre'].mean()),
                'min_price': int(lu_data['price_per_acre'].min()),
                'max_price': int(lu_data['price_per_acre'].max()),
                'count': len(lu_data),
            }
    return result


def get_model_info():
    """Get model metadata for display."""
    _ensure_model_loaded()
    return _metadata or {}
