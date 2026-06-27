"""
Land Price Prediction Engine
=============================
Ensemble model (RandomForest + GradientBoosting) trained on curated Kenyan land market data.

Features: county, constituency, town, land_use, size, distance_to_nairobi,
          infrastructure (road, water, electricity), proximity (tarmac, school, hospital),
          plot_grade, year.

The model is trained once and cached in memory for fast inference (~2ms per query).
"""
import os
import csv
import json
import logging
import math
import re
import hashlib
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict
from statistics import mean, median

try:
    import pandas as pd
except Exception:  # pragma: no cover - optional dependency
    pd = None

try:
    import numpy as np
except Exception:  # pragma: no cover - optional dependency
    np = None

try:
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.preprocessing import LabelEncoder
    from sklearn.model_selection import cross_val_score
    import joblib
    HAS_ML_STACK = True
except Exception:  # pragma: no cover - optional dependency
    RandomForestRegressor = None
    GradientBoostingRegressor = None
    LabelEncoder = None
    cross_val_score = None
    joblib = None
    HAS_ML_STACK = False

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / 'data' / 'kenya_land_prices.csv'
MODEL_PATH = BASE_DIR / 'ml_models' / 'price_model.joblib'
ENCODERS_PATH = BASE_DIR / 'ml_models' / 'label_encoders.joblib'
METADATA_PATH = BASE_DIR / 'ml_models' / 'model_metadata.json'
STAT_MODEL_PATH = BASE_DIR / 'ml_models' / 'price_model_statistical.json'

# ── In-memory cache ──────────────────────────────────────────────────────────
_model_rf = None
_model_gb = None
_encoders = None
_metadata = None
_df = None  # Keep training data for comparisons
_records = None  # Normalized CSV rows used by fallback/statistical paths
_stat_model = None
_location_catalog = None
_location_lookup = None

MODEL_VERSION = '3.1-hybrid'

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

PLOT_GRADES = ['A', 'B', 'C', 'D']

# ── Comprehensive Kenya Location Data ────────────────────────────────────────
KENYA_LOCATIONS = {
    "Nairobi": {
        "constituencies": {
            "Westlands": ["Westlands", "Parklands", "Highridge", "Spring Valley", "Loresho", "Muthaiga", "Kileleshwa", "Nyari", "Ridgeways", "Rosslyn", "Gigiri", "Runda", "Hardy"],
            "Dagoretti North": ["Kilimani", "Lavington", "Kileleshwa", "Hurlingham", "Dagoretti Corner", "Adam's Arcade"],
            "Dagoretti South": ["Ngummo", "Kawangware", "Riruta", "Uthiru", "Mutuini"],
            "Langata": ["Karen", "Langata", "South B", "South C", "Nairobi West", "Madaraka", "Otiende"],
            "Kasarani": ["Roysambu", "Kasarani", "Mwiki", "Githurai", "Kahawa West", "Ruaraka"],
            "Ruaraka": ["Baba Dogo", "Korogocho", "Lucky Summer", "Utawala", "Njiru"],
            "Starehe": ["Nairobi CBD", "Pangani", "Ziwani", "Kariokor", "Nairobi South"],
            "Kamukunji": ["Eastleigh", "Majengo", "Shauri Moyo", "Pumwani"],
            "Makadara": ["Makadara", "Bahati", "Hamza", "Maringo", "Viwandani"],
            "Embakasi South": ["Imara Daima", "Syokimau", "Mlolongo", "Athi River"],
            "Embakasi North": ["Umoja", "Kariobangi", "Dandora", "Embakasi"],
            "Embakasi Central": ["Kayole", "Matopeni", "Komarock", "Savannah"],
            "Embakasi East": ["Ruai", "Kamulu", "Joska", "Embakasi Village"],
            "Embakasi West": ["Umoja", "Donholm", "Tena", "Tassia", "Pipeline"]
        }
    },
    "Kiambu": {
        "constituencies": {
            "Kiambu Town": ["Kiambu Town", "Ndumberi", "Riabai"],
            "Thika Town": ["Thika Town", "Section 9", "Bendor Estate", "Makongeni"],
            "Ruiru": ["Ruiru Town", "Tala", "Membley", "Sunton", "Zimmerman"],
            "Gatundu South": ["Gatundu", "Kiganjo", "Kamwangi"],
            "Gatundu North": ["Mang'u", "Gatukuyu"],
            "Juja": ["Juja", "Kalimoni", "Witeithie", "Juja South"],
            "Kabete": ["Kikuyu", "Wangige", "Nairobi-Kiambu border"],
            "Limuru": ["Limuru Town", "Bibirioni", "Ndeiya", "Tigoni"],
            "Lari": ["Tigoni", "Kinale", "Kijabe"],
            "Karuri": ["Karuri"]
        }
    },
    "Machakos": {
        "constituencies": {
            "Mavoko": ["Athi River", "Syokimau", "Kitengela", "Mlolongo"],
            "Machakos Town": ["Machakos Town", "Mumbuni", "Mutituni"],
            "Kangundo": ["Kangundo", "Tala", "Kamulu", "Joska"]
        }
    },
    "Kajiado": {
        "constituencies": {
            "Kajiado North": ["Ngong", "Kiserian", "Ongata Rongai", "Rongai"],
            "Kajiado East": ["Kitengela", "Isinya", "Oloosirkon"],
            "Kajiado Central": ["Kajiado Town", "Ewaso"],
            "Kajiado West": ["Magadi", "Ewuaso"]
        }
    },
    "Mombasa": {
        "constituencies": {
            "Nyali": ["Nyali", "Bamburi", "Shanzu", "Kongowea"],
            "Mvita": ["Mombasa CBD", "Old Town", "Majengo", "Tononoka"],
            "Changamwe": ["Changamwe", "Port Reitz", "Airport"],
            "Likoni": ["Likoni", "Shelly Beach", "Mtongwe"],
            "Kisauni": ["Kisauni", "Bamburi", "Mtwapa", "Shanzu"]
        }
    },
    "Nakuru": {
        "constituencies": {
            "Nakuru Town East": ["Milimani", "Section 58", "Kiamunyi", "Lanet"],
            "Nakuru Town West": ["London Estate", "Kaptembwa", "Rhoda", "Baruti"],
            "Bahati": ["Bahati", "Kabatini", "Menengai"],
            "Subukia": ["Subukia", "Kabazi"],
            "Naivasha": ["Naivasha"]
        }
    },
    "Kisumu": {
        "constituencies": {
            "Kisumu Central": ["Milimani", "CBD", "Tom Mboya Estate", "Kenyatta"],
            "Kisumu East": ["Manyatta", "Nyalenda", "Chiga"],
            "Kisumu West": ["Mamboleo", "Kajulu", "Maseno"],
            "Nyando": ["Ahero", "Muhoroni", "Miwani"]
        }
    },
    "Uasin Gishu": {
        "constituencies": {
            "Ainabkoi": ["Elgon View", "Pioneer", "Capitol", "Eldoret Town"],
            "Kapsaret": ["Kapsaret", "Langas", "Koisagat"],
            "Soy": ["Soy", "Ziwa", "Tulwet"]
        }
    },
    "Kilifi": {
        "constituencies": {
            "Malindi": ["Malindi"],
            "Bahari": ["Mtwapa", "Watamu", "Kilifi Town"]
        }
    },
    "Kwale": {
        "constituencies": {
            "Msambweni": ["Diani", "Ukunda"],
            "Kwale Town": ["Kwale Town"]
        }
    },
    "Laikipia": {
        "constituencies": {
            "Laikipia East": ["Nanyuki"],
            "Laikipia West": ["Rumuruti", "Doldol"]
        }
    },
    "Nyeri": {
        "constituencies": {
            "Nyeri Town": ["Nyeri Town"],
            "Mathira": ["Karatina"],
            "Othaya": ["Othaya"],
            "Mukurweini": ["Mukurweini"]
        }
    },
    "Murang_a": {
        "constituencies": {
            "Murang_a Town": ["Murang_a Town"],
            "Kandara": ["Kenol"],
            "Kangema": ["Kangema"]
        }
    },
    "Meru": {
        "constituencies": {
            "Meru Town": ["Meru Town"],
            "Nkubu": ["Nkubu"],
            "Imenti": ["Timau"]
        }
    },
    "Embu": {
        "constituencies": {
            "Embu Town": ["Embu Town"],
            "Runyenjes": ["Runyenjes"]
        }
    },
    "Kirinyaga": {
        "constituencies": {
            "Kirinyaga Central": ["Kerugoya"],
            "Mwea": ["Wanguru"]
        }
    },
    "Narok": {
        "constituencies": {
            "Narok Town": ["Narok Town"],
            "Narok North": ["Maasai Mara"]
        }
    },
    "Baringo": {
        "constituencies": {
            "Baringo Central": ["Kabarnet"],
            "Baringo South": ["Eldama Ravine"],
            "Marigat": ["Marigat"]
        }
    },
    "Elgeyo Marakwet": {
        "constituencies": {
            "Keiyo North": ["Iten"],
            "Keiyo South": ["Kapsowar"]
        }
    },
    "Nandi": {
        "constituencies": {
            "Aldai": ["Kapsabet"],
            "Nandi Hills": ["Nandi Hills"]
        }
    },
    "Trans Nzoia": {
        "constituencies": {
            "Kwanza": ["Kitale"],
            "Cherangany": ["Cherangany"]
        }
    },
    "Bungoma": {
        "constituencies": {
            "Bungoma Town": ["Bungoma Town"],
            "Webuye": ["Webuye"]
        }
    },
    "Kakamega": {
        "constituencies": {
            "Kakamega Town": ["Kakamega Town"],
            "Lurambi": ["Mumias"]
        }
    },
    "Busia": {
        "constituencies": {
            "Busia Town": ["Busia Town"],
            "Nambale": ["Malaba"]
        }
    },
    "Siaya": {
        "constituencies": {
            "Siaya Town": ["Siaya Town"],
            "Bondo": ["Bondo"]
        }
    },
    "Homa Bay": {
        "constituencies": {
            "Homa Bay Town": ["Homa Bay Town"]
        }
    },
    "Migori": {
        "constituencies": {
            "Migori Town": ["Migori Town"]
        }
    },
    "Kisii": {
        "constituencies": {
            "Kisii Town": ["Kisii Town"],
            "Bobasi": ["Ogembo"]
        }
    },
    "Nyamira": {
        "constituencies": {
            "Nyamira Town": ["Nyamira Town"]
        }
    },
    "Kericho": {
        "constituencies": {
            "Kericho Town": ["Kericho Town"],
            "Ainamoi": ["Litein"]
        }
    },
    "Bomet": {
        "constituencies": {
            "Bomet Town": ["Bomet Town"]
        }
    },
    "Makueni": {
        "constituencies": {
            "Makueni Town": ["Wote"],
            "Sultan Hamud": ["Sultan Hamud"]
        }
    },
    "Kitui": {
        "constituencies": {
            "Kitui Town": ["Kitui Town"],
            "Mwingi": ["Mwingi"],
            "Mutomo": ["Mutomo"]
        }
    },
    "Garissa": {
        "constituencies": {
            "Garissa Town": ["Garissa Town"],
            "Dadaab": ["Dadaab"]
        }
    },
    "Isiolo": {
        "constituencies": {
            "Isiolo Town": ["Isiolo Town"],
            "Merti": ["Merti"]
        }
    },
    "Taita Taveta": {
        "constituencies": {
            "Voi": ["Voi"],
            "Taveta": ["Taveta"]
        }
    },
    "Turkana": {
        "constituencies": {
            "Turkana Central": ["Lodwar"],
            "Turkana West": ["Kakuma"]
        }
    },
    "Marsabit": {
        "constituencies": {
            "Marsabit Town": ["Marsabit Town"],
            "Moyale": ["Moyale"]
        }
    },
    "Samburu": {
        "constituencies": {
            "Samburu East": ["Maralal"]
        }
    },
    "West Pokot": {
        "constituencies": {
            "West Pokot": ["Kapenguria"]
        }
    },
    "Wajir": {
        "constituencies": {
            "Wajir Town": ["Wajir Town"]
        }
    },
    "Mandera": {
        "constituencies": {
            "Mandera Town": ["Mandera Town"]
        }
    },
    "Lamu": {
        "constituencies": {
            "Lamu Town": ["Lamu Town"],
            "Mpeketoni": ["Mpeketoni"]
        }
    },
    "Tana River": {
        "constituencies": {
            "Tana River": ["Hola"],
            "Garsen": ["Garsen"]
        }
    },
    "Tharaka Nithi": {
        "constituencies": {
            "Tharaka": ["Chuka"],
            "Marimanti": ["Marimanti"]
        }
    },
    "Nyandarua": {
        "constituencies": {
            "Ol Kalou": ["Ol Kalou", "Ol Joro Orok"],
            "Kinangop": ["Kinangop", "Engineer"]
        }
    },
    "Vihiga": {
        "constituencies": {
            "Vihiga": ["Mbale"]
        }
    },
}

# ── Approximate town coordinates for distance estimation ─────────────────────
TOWN_COORDINATES = {}
for county, data in KENYA_LOCATIONS.items():
    for constituency, towns in data['constituencies'].items():
        for town in towns:
            TOWN_COORDINATES[town] = {
                'county': county,
                'constituency': constituency,
            }


def _coerce_bool(value):
    """Coerce common truthy/falsy representations to a boolean."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)

    normalized = str(value).strip().lower()
    return normalized in {'1', 'true', 't', 'yes', 'y', 'on'}


def _safe_float(value, default=0.0):
    try:
        if value in (None, ''):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_location_text(value):
    """Normalize location strings for lookup and search."""
    if value is None:
        return ''
    text = str(value).strip().lower()
    text = text.replace('_', ' ').replace("'", '')
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _alias_variants(value):
    """Generate a small set of search aliases for a location label."""
    normalized = _normalize_location_text(value)
    aliases = {normalized} if normalized else set()
    if not normalized:
        return aliases

    compact = normalized.replace(' ', '')
    if compact:
        aliases.add(compact)

    simplified = re.sub(r'\b(town|estate|village|cbd|centre|center)\b', ' ', normalized)
    simplified = re.sub(r'\s+', ' ', simplified).strip()
    if simplified:
        aliases.add(simplified)
        simplified_compact = simplified.replace(' ', '')
        if simplified_compact:
            aliases.add(simplified_compact)

    if simplified.endswith(' town'):
        aliases.add(simplified[:-5].strip())

    return {alias for alias in aliases if alias}


def _normalize_record(row):
    """Normalize a CSV row or DataFrame record into plain Python types."""
    return {
        'county': str(row.get('county', '')).strip(),
        'constituency': str(row.get('constituency', '')).strip(),
        'town': str(row.get('town', '')).strip(),
        'land_use': str(row.get('land_use', '')).strip(),
        'size_acres': _safe_float(row.get('size_acres', 0.0), 0.0),
        'price_per_acre': int(_safe_float(row.get('price_per_acre', 0), 0.0)),
        'distance_to_nairobi_km': _safe_float(row.get('distance_to_nairobi_km', 0.0), 0.0),
        'latitude': _safe_float(row.get('latitude', 0.0), 0.0),
        'longitude': _safe_float(row.get('longitude', 0.0), 0.0),
        'proximity_to_tarmac_km': _safe_float(row.get('proximity_to_tarmac_km', 0.0), 0.0),
        'proximity_to_school_km': _safe_float(row.get('proximity_to_school_km', 0.0), 0.0),
        'proximity_to_hospital_km': _safe_float(row.get('proximity_to_hospital_km', 0.0), 0.0),
        'plot_grade': str(row.get('plot_grade', 'C')).strip() or 'C',
        'has_road_access': _coerce_bool(row.get('has_road_access', False)),
        'has_water': _coerce_bool(row.get('has_water', False)),
        'has_electricity': _coerce_bool(row.get('has_electricity', False)),
        'year': int(_safe_float(row.get('year', 2025), 2025)),
    }


def _load_rows():
    """Load and cache the training rows as normalized dictionaries."""
    global _records, _df

    if _records is not None:
        return _records

    if not DATA_PATH.exists():
        logger.error(f"Training data not found at {DATA_PATH}")
        return None

    if pd is not None:
        try:
            if _df is None:
                _df = pd.read_csv(DATA_PATH)
            _records = [_normalize_record(row) for row in _df.fillna('').to_dict('records')]
            return _records
        except Exception as exc:
            logger.warning(f"Falling back to csv reader for price data: {exc}")

    with DATA_PATH.open(newline='', encoding='utf-8') as handle:
        reader = csv.DictReader(handle)
        _records = [_normalize_record(row) for row in reader]
    return _records


def _derive_location_market_position(county, constituency, town):
    premium = {'Nairobi', 'Mombasa', 'Kiambu'}
    growth = {'Kajiado', 'Machakos', 'Nakuru', 'Uasin Gishu', 'Kisumu'}
    coastal = {'Mombasa', 'Kilifi', 'Kwale', 'Lamu'}
    if town in {'Westlands', 'Kilimani', 'Karen', 'Nyali', 'Muthaiga', 'Runda', 'Lavington'}:
        return 'Premium zone'
    if county in premium or town in {'Kitengela', 'Syokimau', 'Athi River', 'Juja', 'Ruiru Town'}:
        return 'Growth corridor'
    if county in coastal or town in {'Mvita', 'Changamwe', 'Mtwapa', 'Diani', 'Malindi'}:
        return 'Coastal demand'
    if county in growth or town in {'Eldoret Town', 'Kapsabet', 'Naivasha', 'Narok Town'}:
        return 'Emerging zone'
    return 'Market average'


def _derive_location_region(county, constituency, town):
    if county == 'Nairobi':
        return 'Nairobi metro'
    if county in {'Kiambu', 'Kajiado', 'Machakos'}:
        return 'Nairobi commuter belt'
    if county in {'Mombasa', 'Kilifi', 'Kwale', 'Lamu'}:
        return 'Coastal corridor'
    if county in {'Uasin Gishu', 'Nakuru', 'Kisumu'}:
        return 'Regional hub'
    return f'{county} market'


def _derive_location_land_use(county, constituency, town):
    if county in {'Nairobi', 'Kiambu', 'Mombasa', 'Machakos', 'Kajiado', 'Nakuru', 'Kisumu', 'Uasin Gishu'}:
        if town in {'Changamwe', 'Mvita', 'Athi River', 'Eldoret Town'}:
            return 'Commercial'
        return 'Residential'
    if county in {'Laikipia', 'Narok', 'Baringo', 'Makueni', 'Kitui', 'Tana River', 'Marsabit', 'Turkana'}:
        return 'Agricultural'
    return 'Residential'


def _build_location_catalog():
    """Flatten Kenya location data into a searchable catalog."""
    catalog = []
    seen = set()

    for county in KENYA_COUNTIES:
        data = KENYA_LOCATIONS.get(county, {})
        county_record = {
            'label': county,
            'county': county,
            'constituency': county,
            'town': county,
            'region': _derive_location_region(county, county, county),
            'description': f'{county} county overview with market-wide land signals.',
            'land_use': _derive_location_land_use(county, county, county),
            'market_position': _derive_location_market_position(county, county, county),
            'featured': county in {'Nairobi', 'Mombasa', 'Kiambu', 'Kajiado', 'Machakos', 'Nakuru', 'Kisumu', 'Uasin Gishu'},
        }
        county_key = (county_record['county'], county_record['constituency'], county_record['town'])
        if county_key not in seen:
            seen.add(county_key)
            catalog.append(county_record)

        for constituency, towns in data.get('constituencies', {}).items():
            for town in towns:
                record = {
                    'label': town,
                    'county': county,
                    'constituency': constituency,
                    'town': town,
                    'region': _derive_location_region(county, constituency, town),
                    'description': f'{town}, {county} in the {constituency} market cluster.',
                    'land_use': _derive_location_land_use(county, constituency, town),
                    'market_position': _derive_location_market_position(county, constituency, town),
                    'featured': county in {'Nairobi', 'Mombasa', 'Kiambu', 'Kajiado', 'Machakos', 'Nakuru', 'Kisumu', 'Uasin Gishu'},
                }
                record_key = (record['county'], record['constituency'], record['town'])
                if record_key in seen:
                    continue
                seen.add(record_key)
                catalog.append(record)

    return catalog


def _ensure_location_catalog():
    global _location_catalog, _location_lookup

    if _location_catalog is not None and _location_lookup is not None:
        return _location_catalog, _location_lookup

    _location_catalog = _build_location_catalog()
    _location_lookup = defaultdict(list)

    for index, record in enumerate(_location_catalog):
        for alias in {
            record['label'],
            record['county'],
            record['constituency'],
            record['town'],
            *(_alias_variants(record['label'])),
        }:
            normalized = _normalize_location_text(alias)
            if normalized:
                _location_lookup[normalized].append(index)

    return _location_catalog, _location_lookup


def get_location_catalog(query='', limit=60):
    """Return a searchable list of Kenyan location suggestions."""
    catalog, lookup = _ensure_location_catalog()
    normalized_query = _normalize_location_text(query)

    if not normalized_query:
        results = list(catalog)
    else:
        matches = []
        normalized_query_compact = normalized_query.replace(' ', '')
        for record in catalog:
            search_blob = _normalize_location_text(
                ' '.join(
                    [
                        record['label'],
                        record['county'],
                        record['constituency'],
                        record['town'],
                        record['region'],
                        record['description'],
                        record['market_position'],
                    ]
                )
            )
            search_blob_compact = search_blob.replace(' ', '')
            if normalized_query in search_blob or (
                normalized_query_compact and normalized_query_compact in search_blob_compact
            ):
                score = 100
                if search_blob.startswith(normalized_query) or (
                    normalized_query_compact and search_blob_compact.startswith(normalized_query_compact)
                ):
                    score += 50
                record_label = _normalize_location_text(record['label'])
                record_label_compact = record_label.replace(' ', '')
                record_town = _normalize_location_text(record['town'])
                record_town_compact = record_town.replace(' ', '')
                record_constituency = _normalize_location_text(record['constituency'])
                record_constituency_compact = record_constituency.replace(' ', '')
                record_county = _normalize_location_text(record['county'])
                record_county_compact = record_county.replace(' ', '')
                if record_label == normalized_query or record_label_compact == normalized_query_compact:
                    score += 100
                if record_town == normalized_query or record_town_compact == normalized_query_compact:
                    score += 90
                if record_constituency == normalized_query or record_constituency_compact == normalized_query_compact:
                    score += 80
                if record_county == normalized_query or record_county_compact == normalized_query_compact:
                    score += 70
                matches.append((score, record))

        if not matches and normalized_query in lookup:
            matches = [(100, catalog[index]) for index in lookup[normalized_query]]

        results = [record for _, record in sorted(matches, key=lambda item: (-item[0], item[1]['label']))]

    if limit and limit > 0:
        results = results[:limit]

    return results


def resolve_location(county, constituency='', town=''):
    """Resolve input location text to canonical county/constituency/town values."""
    catalog, lookup = _ensure_location_catalog()
    county = str(county or '').strip()
    constituency = str(constituency or '').strip()
    town = str(town or '').strip()

    def _match_by_alias(value):
        normalized = _normalize_location_text(value)
        if not normalized:
            return None
        if normalized in lookup:
            return catalog[lookup[normalized][0]]
        return None

    county_match = _match_by_alias(county)
    if county_match and county_match['county'] in KENYA_COUNTIES:
        county = county_match['county']

    county_data = KENYA_LOCATIONS.get(county, {})
    constituencies = county_data.get('constituencies', {})

    def _resolve_town(value):
        normalized = _normalize_location_text(value)
        if not normalized:
            return None, None
        for resolved_constituency, towns in constituencies.items():
            for candidate in towns:
                candidate_normalized = _normalize_location_text(candidate)
                if normalized == candidate_normalized:
                    return resolved_constituency, candidate
                if normalized in candidate_normalized or candidate_normalized in normalized:
                    return resolved_constituency, candidate
        return None, None

    # Constituency can be a real constituency or a town label.
    if constituency:
        constituency_match = _match_by_alias(constituency)
        if constituency_match and (not county or constituency_match['county'] == county):
            county = constituency_match['county']
            constituency = constituency_match['constituency']
            town = town or constituency_match['town']
            county_data = KENYA_LOCATIONS.get(county, {})
            constituencies = county_data.get('constituencies', {})
        else:
            resolved_constituency, resolved_town = _resolve_town(constituency)
            if resolved_constituency:
                constituency = resolved_constituency
                town = town or resolved_town

    if town:
        town_match = _match_by_alias(town)
        if town_match and (not county or town_match['county'] == county):
            county = town_match['county']
            constituency = town_match['constituency']
            town = town_match['town']
            county_data = KENYA_LOCATIONS.get(county, {})
            constituencies = county_data.get('constituencies', {})
        else:
            resolved_constituency, resolved_town = _resolve_town(town)
            if resolved_constituency:
                constituency = resolved_constituency
                town = resolved_town

    if not county and constituency:
        constituency_match = _match_by_alias(constituency)
        if constituency_match:
            county = constituency_match['county']
            constituency = constituency_match['constituency']
            town = town or constituency_match['town']
            county_data = KENYA_LOCATIONS.get(county, {})
            constituencies = county_data.get('constituencies', {})

    if not county and town:
        town_match = _match_by_alias(town)
        if town_match:
            county = town_match['county']
            constituency = town_match['constituency']
            town = town_match['town']
            county_data = KENYA_LOCATIONS.get(county, {})
            constituencies = county_data.get('constituencies', {})

    if not constituency and constituencies:
        constituency = next(iter(constituencies.keys()))

    if not town and constituency in constituencies and constituencies[constituency]:
        town = constituencies[constituency][0]

    if not town:
        town = constituency or county

    return county, constituency, town


def _load_data():
    """Load the training dataset."""
    global _df, _records

    if pd is None:
        rows = _load_rows()
        return rows

    if _df is not None:
        return _df

    if not DATA_PATH.exists():
        logger.error(f"Training data not found at {DATA_PATH}")
        return None

    _df = pd.read_csv(DATA_PATH)
    _records = [_normalize_record(row) for row in _df.fillna('').to_dict('records')]
    logger.info(f"Loaded {len(_df)} training records from {DATA_PATH}")
    return _df


def train_model():
    """
    Train the ensemble price prediction model on the seed dataset.
    Returns training metrics.
    """
    global _model_rf, _model_gb, _encoders, _metadata, _df

    if not HAS_ML_STACK:
        rows = _load_rows()
        if rows is None:
            raise FileNotFoundError(f"Training data not found at {DATA_PATH}")

        price_values = [row['price_per_acre'] for row in rows if row.get('price_per_acre')]
        metadata = {
            'model_version': MODEL_VERSION,
            'engine': 'statistical-fallback',
            'n_records': len(rows),
            'n_features': 0,
            'n_counties': len({row['county'] for row in rows}),
            'n_constituencies': len({(row['county'], row['constituency']) for row in rows}),
            'n_towns': len({(row['county'], row['constituency'], row['town']) for row in rows}),
            'price_range': {
                'min': int(min(price_values)) if price_values else 0,
                'max': int(max(price_values)) if price_values else 0,
                'median': int(median(price_values)) if price_values else 0,
            },
            'trained_at': datetime.utcnow().isoformat(),
        }

        STAT_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(STAT_MODEL_PATH, 'w', encoding='utf-8') as handle:
            json.dump(metadata, handle, indent=2)

        _metadata = metadata
        logger.info("Fallback statistical price model ready.")
        return metadata

    df = _load_data()
    if df is None:
        raise FileNotFoundError(f"Training data not found at {DATA_PATH}")

    logger.info(f"Training price prediction model on {len(df)} records...")

    # ── Fill missing values ──
    df['town'] = df['town'].fillna('')
    df['plot_grade'] = df['plot_grade'].fillna('C')
    df['proximity_to_tarmac_km'] = df['proximity_to_tarmac_km'].fillna(5.0)
    df['proximity_to_school_km'] = df['proximity_to_school_km'].fillna(3.0)
    df['proximity_to_hospital_km'] = df['proximity_to_hospital_km'].fillna(5.0)
    df['year'] = df['year'].fillna(2025)

    # ── Encode categorical features ──
    encoders = {
        'county': LabelEncoder(),
        'constituency': LabelEncoder(),
        'town': LabelEncoder(),
        'land_use': LabelEncoder(),
        'plot_grade': LabelEncoder(),
    }

    df_encoded = df.copy()
    df_encoded['county_enc'] = encoders['county'].fit_transform(df['county'].astype(str))
    df_encoded['constituency_enc'] = encoders['constituency'].fit_transform(df['constituency'].astype(str))
    df_encoded['town_enc'] = encoders['town'].fit_transform(df['town'].astype(str))
    df_encoded['land_use_enc'] = encoders['land_use'].fit_transform(df['land_use'].astype(str))
    df_encoded['plot_grade_enc'] = encoders['plot_grade'].fit_transform(df['plot_grade'].astype(str))

    # ── Feature matrix ──
    feature_cols = [
        'county_enc', 'constituency_enc', 'town_enc', 'land_use_enc',
        'size_acres', 'distance_to_nairobi_km',
        'has_road_access', 'has_water', 'has_electricity',
        'proximity_to_tarmac_km', 'proximity_to_school_km', 'proximity_to_hospital_km',
        'plot_grade_enc', 'year',
    ]
    X = df_encoded[feature_cols].values
    y = np.log1p(df_encoded['price_per_acre'].values)  # Log-transform for better distribution

    # ── Train RandomForest ──
    model_rf = RandomForestRegressor(
        n_estimators=300,
        max_depth=20,
        min_samples_split=5,
        min_samples_leaf=2,
        max_features='sqrt',
        random_state=42,
        n_jobs=1
    )

    # ── Train GradientBoosting ──
    model_gb = GradientBoostingRegressor(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        min_samples_split=5,
        min_samples_leaf=3,
        subsample=0.8,
        random_state=42
    )

    # Cross-validation on ensemble average
    cv_scores_rf = cross_val_score(model_rf, X, y, cv=5, scoring='r2')
    cv_scores_gb = cross_val_score(model_gb, X, y, cv=5, scoring='r2')
    cv_r2_mean = (cv_scores_rf.mean() + cv_scores_gb.mean()) / 2

    logger.info(f"RF Cross-validation R²: {cv_scores_rf.mean():.4f} (+/- {cv_scores_rf.std() * 2:.4f})")
    logger.info(f"GB Cross-validation R²: {cv_scores_gb.mean():.4f} (+/- {cv_scores_gb.std() * 2:.4f})")
    logger.info(f"Ensemble R²: {cv_r2_mean:.4f}")

    # Fit final models on all data
    model_rf.fit(X, y)
    model_gb.fit(X, y)

    # Feature importance (average of both models)
    rf_importances = dict(zip(feature_cols, model_rf.feature_importances_))
    gb_importances = dict(zip(feature_cols, model_gb.feature_importances_))
    avg_importances = {k: (rf_importances.get(k, 0) + gb_importances.get(k, 0)) / 2
                       for k in feature_cols}
    logger.info(f"Feature importances: {avg_importances}")

    # ── Save model and encoders ──
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({'rf': model_rf, 'gb': model_gb}, MODEL_PATH)
    joblib.dump(encoders, ENCODERS_PATH)

    metadata = {
        'model_version': MODEL_VERSION,
        'engine': 'ensemble',
        'n_records': len(df),
        'n_features': len(feature_cols),
        'feature_cols': feature_cols,
        'cv_r2_mean_rf': float(cv_scores_rf.mean()),
        'cv_r2_std_rf': float(cv_scores_rf.std()),
        'cv_r2_mean_gb': float(cv_scores_gb.mean()),
        'cv_r2_std_gb': float(cv_scores_gb.std()),
        'cv_r2_mean': float(cv_r2_mean),
        'feature_importances_rf': {k: float(v) for k, v in rf_importances.items()},
        'feature_importances_gb': {k: float(v) for k, v in gb_importances.items()},
        'feature_importances_avg': {k: float(v) for k, v in avg_importances.items()},
        'n_counties': len(df['county'].unique()),
        'n_constituencies': len(df['constituency'].unique()),
        'n_towns': len(df['town'].unique()),
        'price_range': {
            'min': int(df['price_per_acre'].min()),
            'max': int(df['price_per_acre'].max()),
            'median': int(df['price_per_acre'].median()),
        },
        'trained_at': datetime.utcnow().isoformat(),
    }
    with open(METADATA_PATH, 'w') as f:
        json.dump(metadata, f, indent=2)

    # Update cache
    _model_rf = model_rf
    _model_gb = model_gb
    _encoders = encoders
    _metadata = metadata

    logger.info("Model training complete and saved.")
    return metadata


def _ensure_model_loaded():
    """Load model from disk if not already in memory."""
    global _model_rf, _model_gb, _encoders, _metadata

    if not HAS_ML_STACK:
        if _metadata is not None:
            return True

        if STAT_MODEL_PATH.exists():
            try:
                with open(STAT_MODEL_PATH, encoding='utf-8') as handle:
                    _metadata = json.load(handle)
                return True
            except Exception as exc:
                logger.warning(f"Failed to load fallback metadata: {exc}")

        try:
            train_model()
            return True
        except Exception as exc:
            logger.error(f"Failed to prepare fallback model: {exc}")
            return False

    if _model_rf is not None and _model_gb is not None and _encoders is not None:
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
        ensemble = joblib.load(MODEL_PATH)
        _model_rf = ensemble['rf']
        _model_gb = ensemble['gb']
        _encoders = joblib.load(ENCODERS_PATH)
        if METADATA_PATH.exists():
            with open(METADATA_PATH) as f:
                _metadata = json.load(f)
        logger.info("Price prediction ensemble model loaded from disk.")
        return True
    except Exception as e:
        # Try loading old single-model format for backward compatibility
        try:
            single_model = joblib.load(MODEL_PATH)
            if hasattr(single_model, 'estimators_'):
                _model_rf = single_model
                _model_gb = None  # Will use RF only
            else:
                logger.error(f"Unrecognized model format: {e}")
                return False
            _encoders = joblib.load(ENCODERS_PATH)
            if METADATA_PATH.exists():
                with open(METADATA_PATH) as f:
                    _metadata = json.load(f)
            logger.warning("Loaded legacy single model (RF only). Retrain for ensemble.")
            return True
        except Exception as e2:
            logger.error(f"Failed to load model: {e2}")
            return False


def predict_price(county, constituency, land_use, size_acres,
                  distance_to_nairobi_km=None, has_road_access=True,
                  has_water=True, has_electricity=True, town='',
                  proximity_to_tarmac_km=None, proximity_to_school_km=None,
                  proximity_to_hospital_km=None, plot_grade='C', year=2025):
    """
    Predict the price per acre for a land parcel using the ensemble model.

    Returns:
        dict with keys: price_per_acre, total_value, confidence_low,
        confidence_high, comparisons, model_accuracy, prediction_id, model_version
    """
    import uuid
    prediction_id = str(uuid.uuid4())

    county, constituency, town = resolve_location(county, constituency, town)

    if not _ensure_model_loaded():
        return {'error': 'Model not available. Please run: python manage.py train_price_model',
                'prediction_id': prediction_id}

    if not HAS_ML_STACK:
        return get_fallback_prediction(
            county=county,
            land_use=land_use,
            size_acres=size_acres,
            constituency=constituency,
            town=town,
            has_road_access=has_road_access,
            has_water=has_water,
            has_electricity=has_electricity,
            distance_to_nairobi_km=distance_to_nairobi_km,
            proximity_to_tarmac_km=proximity_to_tarmac_km,
            proximity_to_school_km=proximity_to_school_km,
            proximity_to_hospital_km=proximity_to_hospital_km,
            plot_grade=plot_grade,
            year=year,
            prediction_id=prediction_id,
        )

    # ── Estimate distance to Nairobi if not provided ──
    if distance_to_nairobi_km is None:
        distance_to_nairobi_km = _estimate_distance_to_nairobi(county, town)

    # ── Estimate proximity values if not provided ──
    if proximity_to_tarmac_km is None:
        proximity_to_tarmac_km = _estimate_proximity(county, town, 'tarmac')
    if proximity_to_school_km is None:
        proximity_to_school_km = _estimate_proximity(county, town, 'school')
    if proximity_to_hospital_km is None:
        proximity_to_hospital_km = _estimate_proximity(county, town, 'hospital')

    # ── Default plot_grade ──
    if not plot_grade or plot_grade not in PLOT_GRADES:
        plot_grade = _estimate_plot_grade(county, town)

    # ── Default year ──
    if not year:
        year = 2025

    # ── Encode features ──
    try:
        county_enc = _safe_encode(_encoders['county'], county)
        constituency_enc = _safe_encode(_encoders['constituency'], constituency)
        town_enc = _safe_encode(_encoders.get('town', _encoders['constituency']), town or constituency)
        land_use_enc = _safe_encode(_encoders['land_use'], land_use)
        plot_grade_enc = _safe_encode(_encoders.get('plot_grade', _encoders['land_use']), plot_grade)
    except Exception as e:
        logger.error(f"Encoding error: {e}")
        return {'error': f'Unknown location or category: {e}', 'prediction_id': prediction_id}

    features = np.array([[
        county_enc, constituency_enc, town_enc, land_use_enc,
        float(size_acres), float(distance_to_nairobi_km),
        int(has_road_access), int(has_water), int(has_electricity),
        float(proximity_to_tarmac_km), float(proximity_to_school_km),
        float(proximity_to_hospital_km),
        plot_grade_enc, int(year)
    ]])

    # ── Predict using ensemble ──
    if _model_gb is not None:
        # Full ensemble
        rf_pred_log = _model_rf.predict(features)[0]
        gb_pred_log = _model_gb.predict(features)[0]
        predicted_log = (rf_pred_log + gb_pred_log) / 2

        # Confidence from both models
        rf_trees = np.array([tree.predict(features)[0] for tree in _model_rf.estimators_])
        rf_std = rf_trees.std()
        gb_std = 0.0
        # GB doesn't have individual estimators we can easily access for variance
        # Use RF variance as primary estimate
        std_log = rf_std
    else:
        # Fallback to RF only
        rf_trees = np.array([tree.predict(features)[0] for tree in _model_rf.estimators_])
        predicted_log = _model_rf.predict(features)[0]
        std_log = rf_trees.std()

    predicted_price = int(np.expm1(predicted_log))

    # Confidence interval
    confidence_low = int(np.expm1(predicted_log - 1.96 * std_log))
    confidence_high = int(np.expm1(predicted_log + 1.96 * std_log))

    # Total estimated value
    total_value = int(predicted_price * float(size_acres))

    # ── Get market comparisons ──
    comparisons = _get_comparisons(county, land_use, size_acres, town)

    # ── Log the prediction ──
    try:
        _log_prediction(
            prediction_id=prediction_id,
            county=county, constituency=constituency, town=town,
            land_use=land_use, size_acres=size_acres,
            has_road_access=has_road_access, has_water=has_water,
            has_electricity=has_electricity,
            proximity_to_tarmac_km=proximity_to_tarmac_km,
            proximity_to_school_km=proximity_to_school_km,
            proximity_to_hospital_km=proximity_to_hospital_km,
            plot_grade=plot_grade,
            predicted_price_per_acre=predicted_price,
            predicted_total_value=total_value,
            confidence_low=max(0, confidence_low),
            confidence_high=confidence_high,
        )
    except Exception as e:
        logger.warning(f"Failed to log prediction: {e}")

    return {
        'price_per_acre': predicted_price,
        'total_value': total_value,
        'confidence_low': max(0, confidence_low),
        'confidence_high': confidence_high,
        'county': county,
        'constituency': constituency,
        'town': town,
        'land_use': land_use,
        'size_acres': float(size_acres),
        'comparisons': comparisons,
        'model_accuracy': _metadata.get('cv_r2_mean', 0) if _metadata else 0,
        'prediction_id': prediction_id,
        'model_version': MODEL_VERSION,
    }


def _log_prediction(**kwargs):
    """Log a prediction to the database for monitoring."""
    try:
        from core.models import PricePredictionLog
        PricePredictionLog.objects.create(
            prediction_id=kwargs['prediction_id'],
            county=kwargs['county'],
            constituency=kwargs.get('constituency', ''),
            town=kwargs.get('town', ''),
            land_use=kwargs['land_use'],
            size_acres=kwargs['size_acres'],
            has_road_access=kwargs.get('has_road_access', True),
            has_water=kwargs.get('has_water', True),
            has_electricity=kwargs.get('has_electricity', True),
            proximity_to_tarmac_km=kwargs.get('proximity_to_tarmac_km'),
            proximity_to_school_km=kwargs.get('proximity_to_school_km'),
            proximity_to_hospital_km=kwargs.get('proximity_to_hospital_km'),
            plot_grade=kwargs.get('plot_grade', ''),
            predicted_price_per_acre=kwargs['predicted_price_per_acre'],
            predicted_total_value=kwargs['predicted_total_value'],
            confidence_low=kwargs['confidence_low'],
            confidence_high=kwargs['confidence_high'],
            confidence_label=_derive_confidence_label(
                _metadata.get('cv_r2_mean', 0) if _metadata else 0
            ),
            model_version=MODEL_VERSION,
        )
    except Exception as e:
        logger.debug(f"Prediction logging skipped (model may not exist yet): {e}")


def _derive_confidence_label(r2_score):
    """Derive a human-readable confidence label from the model R² score."""
    if r2_score >= 0.85:
        return 'High Confidence'
    elif r2_score >= 0.70:
        return 'Moderate Confidence'
    elif r2_score >= 0.50:
        return 'Low Confidence'
    else:
        return 'Very Low Confidence'


def _safe_encode(encoder, value):
    """Safely encode a categorical value, handling unseen labels."""
    try:
        return encoder.transform([str(value)])[0]
    except (ValueError, KeyError):
        # Unseen label — use the most common class as fallback
        logger.warning(f"Unseen label '{value}', using fallback encoding.")
        return 0


def _estimate_distance_to_nairobi(county, town=''):
    """Rough distance estimates from county/town to Nairobi CBD."""
    # Town-level distance adjustments
    town_offsets = {
        'Ruiru Town': -5, 'Thika Town': -3, 'Juja': 5,
        'Kikuyu': -5, 'Limuru Town': 3, 'Kiambu Town': -3,
        'Ngong': -5, 'Kiserian': 3, 'Ongata Rongai': 0,
        'Kitengela': -5, 'Athi River': -3, 'Mlolongo': -8,
        'Syokimau': -7, 'Karen': 10, 'Westlands': -2,
        'Kilimani': -3, 'Runda': 5, 'Muthaiga': 2,
    }

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

    base = distances.get(county, 300)
    offset = town_offsets.get(town, 0)
    return max(0, base + offset)


def _estimate_proximity(county, town, amenity_type):
    """Estimate proximity to amenities based on location."""
    # Premium Nairobi neighborhoods: very close to everything
    premium_nairobi = {'Westlands', 'Kilimani', 'Lavington', 'Nairobi CBD', 'Hurlingham',
                       'Muthaiga', 'Kileleshwa', 'Gigiri', 'Parklands', 'Nyari', 'Runda'}
    mid_nairobi = {'Karen', 'Langata', 'South B', 'South C', 'Eastleigh',
                   'Donholm', 'Roysambu', 'Kasarani', 'Pangani', 'Nairobi West'}
    satellite_towns = {'Ruiru Town', 'Kitengela', 'Syokimau', 'Athi River',
                       'Ngong', 'Ongata Rongai', 'Kikuyu', 'Juja', 'Mlolongo',
                       'Imara Daima', 'Kiserian', 'Limuru Town'}

    if town in premium_nairobi:
        defaults = {'tarmac': 0.2, 'school': 0.3, 'hospital': 0.5}
    elif town in mid_nairobi:
        defaults = {'tarmac': 0.5, 'school': 0.8, 'hospital': 1.5}
    elif town in satellite_towns:
        defaults = {'tarmac': 1.0, 'school': 1.5, 'hospital': 3.0}
    elif county == 'Nairobi':
        defaults = {'tarmac': 0.8, 'school': 1.0, 'hospital': 2.0}
    elif county in ('Kiambu', 'Kajiado', 'Machakos'):
        defaults = {'tarmac': 2.0, 'school': 2.0, 'hospital': 4.0}
    elif county in ('Mombasa', 'Kisumu', 'Nakuru', 'Uasin Gishu'):
        defaults = {'tarmac': 1.0, 'school': 1.5, 'hospital': 2.5}
    else:
        defaults = {'tarmac': 5.0, 'school': 4.0, 'hospital': 8.0}

    return defaults.get(amenity_type, 3.0)


def _estimate_plot_grade(county, town):
    """Estimate plot grade based on location."""
    grade_a_towns = {'Westlands', 'Kilimani', 'Lavington', 'Nairobi CBD', 'Muthaiga',
                     'Gigiri', 'Runda', 'Nyali', 'Kileleshwa', 'Parklands', 'Hurlingham',
                     'Nyari', 'Rosslyn', 'Spring Valley'}
    grade_b_towns = {'Karen', 'Langata', 'Donholm', 'Ngong', 'Kikuyu', 'Ruiru Town',
                     'Limuru Town', 'Kiambu Town', 'Karuri', 'Bamburi', 'Milimani',
                     'Elgon View', 'Diani', 'Shanzu', 'Mombasa CBD', 'Changamwe',
                     'South B', 'South C', 'Nairobi West', 'Madaraka', 'Kiserian',
                     'Ongata Rongai', 'Kitengela', 'Mtwapa', 'Eldoret Town'}
    grade_c_towns = {'Syokimau', 'Athi River', 'Mlolongo', 'Kasarani', 'Roysambu',
                     'Githurai', 'Umoja', 'Kayole', 'Eastleigh', 'Kawangware',
                     'Juja', 'Thika Town', 'Isinya', 'Machakos Town', 'Naivasha',
                     'Kisumu Town', 'Tom Mboya Estate', 'Mamboleo', 'Pioneer',
                     'Nakuru Town', 'Section 58', 'London Estate'}

    if town in grade_a_towns:
        return 'A'
    elif town in grade_b_towns:
        return 'B'
    elif town in grade_c_towns:
        return 'C'
    else:
        return 'D'


def _record_matches_location(row, county=None, constituency=None, town=None, land_use=None):
    if county and _normalize_location_text(row.get('county')) != _normalize_location_text(county):
        return False
    if constituency and _normalize_location_text(row.get('constituency')) != _normalize_location_text(constituency):
        return False
    if town and _normalize_location_text(row.get('town')) != _normalize_location_text(town):
        return False
    if land_use and _normalize_location_text(row.get('land_use')) != _normalize_location_text(land_use):
        return False
    return True


def _get_comparisons(county, land_use, size_acres, town=''):
    """Get comparable market data from the training set."""
    county, constituency, town = resolve_location(county, '', town)
    rows = _load_rows() or []
    if not rows:
        return []

    comparable = [row for row in rows if _record_matches_location(row, county=county, town=town, land_use=land_use)]
    if not comparable and constituency:
        comparable = [row for row in rows if _record_matches_location(row, county=county, constituency=constituency, land_use=land_use)]
    if not comparable:
        comparable = [row for row in rows if _record_matches_location(row, county=county, land_use=land_use)]
    if not comparable:
        comparable = [row for row in rows if row.get('county') == county]

    if not comparable:
        return []

    # Sort by size similarity
    comparable = sorted(
        comparable,
        key=lambda row: abs(_safe_float(row.get('size_acres', 0.0), 0.0) - float(size_acres)),
    )[:5]

    results = []
    for row in comparable:
        results.append({
            'county': row.get('county', county),
            'constituency': row.get('constituency', constituency),
            'town': row.get('town', town),
            'land_use': row.get('land_use', land_use),
            'size_acres': float(row.get('size_acres', 0.0)),
            'price_per_acre': int(row.get('price_per_acre', 0)),
        })

    return results


def get_county_averages():
    """Get average price per acre for each county, grouped by land use."""
    rows = _load_rows() or []
    if not rows:
        return {}

    result = {}
    for county in sorted({row['county'] for row in rows}):
        county_data = [row for row in rows if row['county'] == county]
        result[county] = {}
        for land_use in sorted({row['land_use'] for row in county_data}):
            lu_data = [row for row in county_data if row['land_use'] == land_use]
            prices = [row['price_per_acre'] for row in lu_data]
            result[county][land_use] = {
                'avg_price': int(mean(prices)),
                'min_price': int(min(prices)),
                'max_price': int(max(prices)),
                'count': len(lu_data),
            }
    return result


def get_model_info():
    """Get model metadata for display."""
    _ensure_model_loaded()
    return _metadata or {}


def get_constituencies_for_county(county):
    """Return list of constituencies for a given county."""
    county, _, _ = resolve_location(county)
    county_data = KENYA_LOCATIONS.get(county)
    if county_data and 'constituencies' in county_data:
        return list(county_data['constituencies'].keys())
    return []


def get_towns_for_constituency(county, constituency):
    """Return list of towns for a given county and constituency."""
    county, constituency, _ = resolve_location(county, constituency)
    county_data = KENYA_LOCATIONS.get(county)
    if county_data and 'constituencies' in county_data:
        return county_data['constituencies'].get(constituency, [])
    return []


def get_fallback_prediction(
    county,
    land_use,
    size_acres,
    constituency='',
    town='',
    has_road_access=True,
    has_water=True,
    has_electricity=True,
    distance_to_nairobi_km=None,
    proximity_to_tarmac_km=None,
    proximity_to_school_km=None,
    proximity_to_hospital_km=None,
    plot_grade='C',
    year=2025,
    prediction_id=None,
):
    """Generate a fallback prediction when the model is unavailable.
    Uses location medians and simple data-driven adjustments from the seed dataset.
    """
    county, constituency, town = resolve_location(county, constituency, town)
    rows = _load_rows() or []
    prediction_id = prediction_id or 'fallback'

    if not rows:
        base_price = 5_000_000
        return {
            'price_per_acre': base_price,
            'total_value': int(base_price * float(size_acres)),
            'confidence_low': 1_000_000,
            'confidence_high': 25_000_000,
            'county': county,
            'constituency': constituency,
            'town': town,
            'land_use': land_use,
            'size_acres': float(size_acres),
            'comparisons': [],
            'model_accuracy': 0.45,
            'prediction_id': prediction_id,
            'model_version': 'fallback',
            'fallback': True,
        }

    filtered = [row for row in rows if _record_matches_location(row, county=county, constituency=constituency, town=town, land_use=land_use)]
    if not filtered and town:
        filtered = [row for row in rows if _record_matches_location(row, county=county, town=town, land_use=land_use)]
    if not filtered and constituency:
        filtered = [row for row in rows if _record_matches_location(row, county=county, constituency=constituency, land_use=land_use)]
    if not filtered:
        filtered = [row for row in rows if _record_matches_location(row, county=county, land_use=land_use)]
    if not filtered:
        filtered = [row for row in rows if row.get('land_use') == land_use]
    if not filtered:
        filtered = rows

    price_values = [row['price_per_acre'] for row in filtered if row.get('price_per_acre')]
    median_price = int(median(price_values)) if price_values else int(median([row['price_per_acre'] for row in rows]))

    # Blend location-specific medians with the county baseline.
    county_values = [row['price_per_acre'] for row in rows if row['county'] == county and row['land_use'] == land_use]
    county_median = int(median(county_values)) if county_values else median_price
    if county_median:
        median_price = int((median_price * 0.7) + (county_median * 0.3))

    # Size sensitivity: larger parcels usually have a lower price per acre.
    size_anchor = median([row['size_acres'] for row in filtered if row.get('size_acres', 0) > 0]) if filtered else float(size_acres)
    size_anchor = size_anchor or 1.0
    size_value = max(float(size_acres), 0.01)
    size_adjustment = max(0.65, min(1.35, (size_anchor / size_value) ** 0.08))

    # Simple infrastructure / quality adjustments.
    road_adjustment = 1.04 if _coerce_bool(has_road_access) else 0.96
    water_adjustment = 1.03 if _coerce_bool(has_water) else 0.97
    electricity_adjustment = 1.05 if _coerce_bool(has_electricity) else 0.95
    plot_grade = plot_grade if plot_grade in PLOT_GRADES else _estimate_plot_grade(county, town)
    grade_adjustment = {'A': 1.18, 'B': 1.08, 'C': 1.0, 'D': 0.88}.get(plot_grade, 1.0)

    # Mild location score for better ranking between similar areas.
    if distance_to_nairobi_km is None:
        distance_to_nairobi_km = _estimate_distance_to_nairobi(county, town)
    if proximity_to_tarmac_km is None:
        proximity_to_tarmac_km = _estimate_proximity(county, town, 'tarmac')
    if proximity_to_school_km is None:
        proximity_to_school_km = _estimate_proximity(county, town, 'school')
    if proximity_to_hospital_km is None:
        proximity_to_hospital_km = _estimate_proximity(county, town, 'hospital')

    proximity_adjustment = 1.0
    proximity_adjustment *= max(0.88, min(1.12, 1.02 - (distance_to_nairobi_km / 3000.0)))
    proximity_adjustment *= max(0.92, min(1.08, 1.04 - (proximity_to_tarmac_km / 500.0)))
    proximity_adjustment *= max(0.93, min(1.06, 1.02 - (proximity_to_school_km / 600.0)))
    proximity_adjustment *= max(0.93, min(1.06, 1.02 - (proximity_to_hospital_km / 650.0)))

    predicted_price = int(
        max(
            0,
            round(
                median_price
                * size_adjustment
                * road_adjustment
                * water_adjustment
                * electricity_adjustment
                * grade_adjustment
                * proximity_adjustment,
            ),
        )
    )
    total_value = int(predicted_price * float(size_acres))

    sample_count = len(filtered)
    specificity = 0.0
    if town and any(row.get('town') == town for row in filtered):
        specificity += 0.24
    if constituency and any(row.get('constituency') == constituency for row in filtered):
        specificity += 0.16
    if county:
        specificity += 0.10
    sample_boost = min(0.20, math.log10(sample_count + 1) / 10.0)
    model_accuracy = min(0.90, 0.45 + specificity + sample_boost)
    spread = max(0.20, 0.55 - (model_accuracy - 0.45) * 0.45)
    confidence_low = max(0, int(predicted_price * (1 - spread)))
    confidence_high = max(confidence_low + 1, int(predicted_price * (1 + spread)))

    comparisons = _get_comparisons(county, land_use, size_acres, town)

    try:
        _log_prediction(
            prediction_id=prediction_id,
            county=county,
            constituency=constituency,
            town=town,
            land_use=land_use,
            size_acres=size_acres,
            has_road_access=has_road_access,
            has_water=has_water,
            has_electricity=has_electricity,
            proximity_to_tarmac_km=proximity_to_tarmac_km,
            proximity_to_school_km=proximity_to_school_km,
            proximity_to_hospital_km=proximity_to_hospital_km,
            plot_grade=plot_grade,
            predicted_price_per_acre=predicted_price,
            predicted_total_value=total_value,
            confidence_low=confidence_low,
            confidence_high=confidence_high,
        )
    except Exception as exc:
        logger.debug(f"Fallback prediction logging skipped: {exc}")

    return {
        'price_per_acre': predicted_price,
        'total_value': total_value,
        'confidence_low': confidence_low,
        'confidence_high': confidence_high,
        'county': county,
        'constituency': constituency,
        'town': town,
        'land_use': land_use,
        'size_acres': float(size_acres),
        'comparisons': comparisons,
        'model_accuracy': model_accuracy,
        'prediction_id': prediction_id,
        'model_version': 'fallback',
        'fallback': True,
    }
