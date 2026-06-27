"""
Tests for the Land Price Prediction REST API and service layer.

Covers:
  1. API: POST valid request -> 200 with prediction data
  2. API: POST missing county -> 400
  3. API: POST invalid land_use -> 400
  4. API: POST negative size -> 400
  5. API: GET request -> 200 with model info
  6. API: GET ?action=constituencies -> 200 with constituency list
  7. API: GET ?action=towns -> 200 with town list
  8. API: POST with new fields (town, proximity, plot_grade) -> 200
  9. Unit: predict_price() returns expected fields including town
  10. Unit: predict_price() with unknown county uses fallback
  11. Unit: Confidence label derivation
  12. Unit: get_constituencies_for_county() returns valid data
  13. Unit: get_towns_for_constituency() returns valid data
  14. Unit: get_fallback_prediction() works when model unavailable
  15. API: POST invalid proximity values -> 400
  16. API: POST invalid plot_grade -> 400
"""
import django
from django.test import TestCase
from rest_framework.test import APIClient

from .services.price_prediction import (
    predict_price, get_fallback_prediction,
    get_constituencies_for_county, get_towns_for_constituency,
    KENYA_COUNTIES, LAND_USE_TYPES, PLOT_GRADES, KENYA_LOCATIONS,
)
from .api_views import _get_confidence_label, _get_market_position


class PricePredictionAPITests(TestCase):
    """DRF APIClient tests for /api/v1/price-prediction/ endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.url = '/api/v1/price-prediction/'
        # Ensure model is loaded before tests run
        from .services.price_prediction import _ensure_model_loaded
        _ensure_model_loaded()

    # ── Test 1: POST valid request → 200 ──
    def test_post_valid_request_returns_200(self):
        payload = {
            'county': 'Nairobi',
            'constituency': 'Westlands',
            'land_use': 'Residential',
            'size_acres': 0.5,
            'has_road_access': True,
            'has_water': True,
            'has_electricity': True,
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 200, msg=response.data)

        data = response.data
        expected_keys = [
            'price_per_acre', 'total_value', 'confidence_low',
            'confidence_high', 'county', 'constituency', 'town', 'land_use',
            'size_acres', 'comparisons', 'model_accuracy',
            'confidence_label', 'market_position', 'model_version', 'prediction_id',
        ]
        for key in expected_keys:
            self.assertIn(key, data, f'Missing key: {key}')

        self.assertIsInstance(data['price_per_acre'], int)
        self.assertGreater(data['price_per_acre'], 0)
        self.assertIsInstance(data['total_value'], int)
        self.assertGreater(data['total_value'], 0)
        self.assertEqual(data['county'], 'Nairobi')
        self.assertEqual(data['constituency'], 'Westlands')
        self.assertEqual(data['land_use'], 'Residential')
        self.assertAlmostEqual(data['size_acres'], 0.5)
        self.assertIsInstance(data['comparisons'], list)

    # ── Test 2: POST missing county → 400 ──
    def test_post_missing_county_returns_400(self):
        payload = {
            'constituency': 'Westlands',
            'land_use': 'Residential',
            'size_acres': 0.5,
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('errors', response.data)
        self.assertIn('county', response.data['errors'])

    # ── Test 3: POST invalid land_use → 400 ──
    def test_post_invalid_land_use_returns_400(self):
        payload = {
            'county': 'Nairobi',
            'constituency': 'Westlands',
            'land_use': 'Industrial',
            'size_acres': 0.5,
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('errors', response.data)
        self.assertIn('land_use', response.data['errors'])

    # ── Test 4: POST negative size → 400 ──
    def test_post_negative_size_returns_400(self):
        payload = {
            'county': 'Nairobi',
            'constituency': 'Westlands',
            'land_use': 'Residential',
            'size_acres': -5,
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('errors', response.data)
        self.assertIn('size_acres', response.data['errors'])

    # ── Test 5: GET request → 200 with model info ──
    def test_get_returns_model_info(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = response.data

        self.assertIn('model_info', data)
        self.assertIn('n_records', data['model_info'])
        self.assertIn('n_counties', data['model_info'])
        self.assertIn('algorithm', data['model_info'])
        self.assertIn('counties', data)
        self.assertIn('land_use_types', data)
        self.assertIn('plot_grades', data)

        self.assertIsInstance(data['counties'], list)
        self.assertGreater(len(data['counties']), 0)
        self.assertEqual(data['land_use_types'], LAND_USE_TYPES)

    # ── Test 6: GET constituencies → 200 ──
    def test_get_constituencies_returns_list(self):
        response = self.client.get(f'{self.url}?action=constituencies&county=Nairobi')
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertIn('constituencies', data)
        self.assertIsInstance(data['constituencies'], list)
        self.assertGreater(len(data['constituencies']), 0)
        self.assertEqual(data['county'], 'Nairobi')

    # ── Test 7: GET towns → 200 ──
    def test_get_towns_returns_list(self):
        response = self.client.get(f'{self.url}?action=towns&county=Nairobi&constituency=Westlands')
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertIn('towns', data)
        self.assertIsInstance(data['towns'], list)
        self.assertGreater(len(data['towns']), 0)

    # ── Test 8: POST with new fields → 200 ──
    def test_post_with_new_fields_returns_200(self):
        payload = {
            'county': 'Nairobi',
            'constituency': 'Langata',
            'town': 'Karen',
            'land_use': 'Residential',
            'size_acres': 1.0,
            'has_road_access': True,
            'has_water': True,
            'has_electricity': True,
            'proximity_to_tarmac_km': 1.0,
            'proximity_to_school_km': 1.5,
            'proximity_to_hospital_km': 3.0,
            'plot_grade': 'A',
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 200, msg=response.data)
        data = response.data
        self.assertIn('town', data)
        self.assertIn('prediction_id', data)
        self.assertIn('model_version', data)

    # ── Test 15: POST invalid proximity → 400 ──
    def test_post_invalid_proximity_returns_400(self):
        payload = {
            'county': 'Nairobi',
            'constituency': 'Westlands',
            'land_use': 'Residential',
            'size_acres': 0.5,
            'proximity_to_tarmac_km': 100,  # > 50
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('errors', response.data)
        self.assertIn('proximity_to_tarmac_km', response.data['errors'])

    # ── Test 16: POST invalid plot_grade → 400 ──
    def test_post_invalid_plot_grade_returns_400(self):
        payload = {
            'county': 'Nairobi',
            'constituency': 'Westlands',
            'land_use': 'Residential',
            'size_acres': 0.5,
            'plot_grade': 'Z',  # Invalid
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('errors', response.data)
        self.assertIn('plot_grade', response.data['errors'])


class PredictPriceUnitTests(TestCase):
    """Unit tests for the predict_price service function."""

    def setUp(self):
        from .services.price_prediction import _ensure_model_loaded
        _ensure_model_loaded()

    # ── Test 9: predict_price() returns expected fields ──
    def test_predict_price_returns_expected_fields(self):
        result = predict_price(
            county='Nairobi',
            constituency='Westlands',
            land_use='Residential',
            size_acres=0.5,
            has_road_access=True,
            has_water=True,
            has_electricity=True,
            town='Westlands',
            plot_grade='B',
        )
        # Should not contain error key
        self.assertNotIn('error', result)

        expected_keys = [
            'price_per_acre', 'total_value', 'confidence_low',
            'confidence_high', 'county', 'constituency', 'town', 'land_use',
            'size_acres', 'comparisons', 'model_accuracy',
            'prediction_id', 'model_version',
        ]
        for key in expected_keys:
            self.assertIn(key, result, f'Missing key: {key}')

        self.assertGreater(result['price_per_acre'], 0)
        self.assertEqual(result['county'], 'Nairobi')
        self.assertEqual(result['town'], 'Westlands')

    # ── Test 10: predict_price() with unknown county uses fallback ──
    def test_predict_price_unknown_county_uses_fallback(self):
        result = predict_price(
            county='UnknownCounty',
            constituency='SomePlace',
            land_use='Residential',
            size_acres=1.0,
            has_road_access=True,
            has_water=True,
            has_electricity=True,
        )
        self.assertIn('price_per_acre', result)
        self.assertGreater(result['price_per_acre'], 0)

    # ── Test 12: get_constituencies_for_county() ──
    def test_get_constituencies_for_county(self):
        constituencies = get_constituencies_for_county('Nairobi')
        self.assertIsInstance(constituencies, list)
        self.assertGreater(len(constituencies), 5)
        self.assertIn('Westlands', constituencies)
        self.assertIn('Langata', constituencies)

    def test_get_constituencies_unknown_county(self):
        constituencies = get_constituencies_for_county('Atlantis')
        self.assertEqual(constituencies, [])

    # ── Test 13: get_towns_for_constituency() ──
    def test_get_towns_for_constituency(self):
        towns = get_towns_for_constituency('Nairobi', 'Westlands')
        self.assertIsInstance(towns, list)
        self.assertGreater(len(towns), 3)
        self.assertIn('Westlands', towns)
        self.assertIn('Runda', towns)

    def test_get_towns_unknown_constituency(self):
        towns = get_towns_for_constituency('Nairobi', 'Atlantis')
        self.assertEqual(towns, [])

    # ── Test 14: get_fallback_prediction() ──
    def test_get_fallback_prediction(self):
        result = get_fallback_prediction('Nairobi', 'Residential', 1.0)
        self.assertIn('price_per_acre', result)
        self.assertGreater(result['price_per_acre'], 0)
        self.assertTrue(result.get('fallback', False))


class ConfidenceLabelTests(TestCase):
    """Unit tests for confidence label derivation."""

    def test_high_confidence(self):
        self.assertEqual(_get_confidence_label(0.90), 'High Confidence')
        self.assertEqual(_get_confidence_label(0.85), 'High Confidence')

    def test_moderate_confidence(self):
        self.assertEqual(_get_confidence_label(0.80), 'Moderate Confidence')
        self.assertEqual(_get_confidence_label(0.70), 'Moderate Confidence')

    def test_low_confidence(self):
        self.assertEqual(_get_confidence_label(0.60), 'Low Confidence')
        self.assertEqual(_get_confidence_label(0.50), 'Low Confidence')

    def test_very_low_confidence(self):
        self.assertEqual(_get_confidence_label(0.30), 'Very Low Confidence')
        self.assertEqual(_get_confidence_label(0.0), 'Very Low Confidence')

    def test_market_position_premium(self):
        self.assertEqual(_get_market_position(150_000_000), 'Premium zone')

    def test_market_position_high_value(self):
        self.assertEqual(_get_market_position(50_000_000), 'High-value zone')

    def test_market_position_mid_market(self):
        self.assertEqual(_get_market_position(8_000_000), 'Mid-market zone')

    def test_market_position_emerging(self):
        self.assertEqual(_get_market_position(2_000_000), 'Emerging zone')

    def test_market_position_rural(self):
        self.assertEqual(_get_market_position(500_000), 'Rural / remote zone')
