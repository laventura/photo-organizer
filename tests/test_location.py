"""
Tests for location module.
"""
import pytest
from pathlib import Path
import tempfile

from src.location import LocationIntelligence
from src.cache import GeocodingCache


@pytest.fixture
def temp_cache():
    """Create a temporary cache for testing."""
    temp_file = Path(tempfile.mktemp(suffix='.db'))
    cache = GeocodingCache(cache_path=temp_file)

    yield cache

    cache.close()
    if temp_file.exists():
        temp_file.unlink()


@pytest.fixture
def location_intel(temp_cache):
    """Create LocationIntelligence instance for testing."""
    return LocationIntelligence(
        cache=temp_cache,
        locationiq_api_key=None  # Use only Nominatim for tests
    )


def test_haversine_distance(location_intel):
    """Test distance calculation between coordinates."""
    # San Francisco to Los Angeles (approximately 380 miles)
    sf_lat, sf_lon = 37.7749, -122.4194
    la_lat, la_lon = 34.0522, -118.2437

    distance = location_intel.calculate_distance_miles(sf_lat, sf_lon, la_lat, la_lon)

    # Should be approximately 380 miles (allow 10% margin)
    assert 340 <= distance <= 420


def test_should_cluster_locations_close(location_intel):
    """Test that nearby locations should be clustered."""
    # Two points 10 miles apart
    lat1, lon1 = 37.7749, -122.4194
    lat2, lon2 = 37.8749, -122.4194  # About 10 miles north

    should_cluster = location_intel.should_cluster_locations(lat1, lon1, lat2, lon2)

    assert should_cluster is True


def test_should_cluster_locations_far(location_intel):
    """Test that distant locations should not be clustered."""
    # San Francisco to Los Angeles
    sf_lat, sf_lon = 37.7749, -122.4194
    la_lat, la_lon = 34.0522, -118.2437

    should_cluster = location_intel.should_cluster_locations(sf_lat, sf_lon, la_lat, la_lon)

    assert should_cluster is False


def test_normalize_name(location_intel):
    """Test location name normalization."""
    assert location_intel._normalize_name("San Francisco") == "San_Francisco"
    assert location_intel._normalize_name("New York City") == "New_York_City"
    assert location_intel._normalize_name("Test-Location") == "Test-Location"


def test_state_abbreviation(location_intel):
    """Test state name to abbreviation conversion."""
    assert location_intel._get_state_abbreviation("California") == "CA"
    assert location_intel._get_state_abbreviation("New York") == "NY"
    assert location_intel._get_state_abbreviation("Unknown") == "Unknown"


def test_apply_granularity_foreign_country(location_intel):
    """Test granularity for foreign countries."""
    location_data = {
        'country': 'France',
        'state': 'Île-de-France',
        'city': 'Paris',
        'county': ''
    }

    result = location_intel._apply_granularity_rules(location_data)

    assert result == "France"
    assert location_data['granularity'] == 'country'


def test_apply_granularity_us_major_city(location_intel):
    """Test granularity for US major cities."""
    location_data = {
        'country': 'United States',
        'state': 'California',
        'city': 'San Francisco',
        'county': ''
    }

    result = location_intel._apply_granularity_rules(location_data)

    assert result == "CA-San_Francisco"
    assert location_data['granularity'] == 'major_city'


def test_apply_granularity_us_rural(location_intel):
    """Test granularity for US rural areas."""
    location_data = {
        'country': 'United States',
        'state': 'Montana',
        'city': 'Small Town',
        'county': ''
    }

    result = location_intel._apply_granularity_rules(location_data)

    assert result == "MT"
    assert location_data['granularity'] == 'state'


def test_apply_granularity_national_park(location_intel):
    """Test granularity for national parks."""
    location_data = {
        'country': 'United States',
        'state': 'California',
        'city': '',
        'county': 'Yosemite National Park'
    }

    result = location_intel._apply_granularity_rules(location_data)

    assert result == "CA-Yosemite"
    assert location_data['granularity'] == 'national_park'


def test_cache_integration(location_intel):
    """Test that cache is used properly."""
    # Pre-populate cache
    location_data = {
        'location_name': 'CA-San_Francisco',
        'granularity': 'major_city',
        'country': 'United States',
        'state': 'California',
        'city': 'San Francisco'
    }

    location_intel.cache.set(37.7749, -122.4194, location_data)

    # Should get from cache
    result = location_intel.get_location_name(37.7749, -122.4194)

    assert result == 'CA-San_Francisco'


def test_context_manager(temp_cache):
    """Test LocationIntelligence as context manager."""
    with LocationIntelligence(cache=temp_cache) as loc_intel:
        assert loc_intel.cache is not None

    # Cache should be closed
    assert temp_cache.conn is None
