"""
Tests for cache module.
"""
import pytest
from pathlib import Path
import tempfile

from src.cache import GeocodingCache


@pytest.fixture
def temp_cache():
    """Create a temporary cache database."""
    temp_file = Path(tempfile.mktemp(suffix='.db'))
    cache = GeocodingCache(cache_path=temp_file)

    yield cache

    cache.close()
    if temp_file.exists():
        temp_file.unlink()


def test_cache_initialization(temp_cache):
    """Test cache initialization creates database."""
    assert temp_cache.cache_path.exists()
    assert temp_cache.conn is not None


def test_cache_set_and_get(temp_cache):
    """Test storing and retrieving from cache."""
    location_data = {
        'location_name': 'CA-San_Francisco',
        'granularity': 'major_city',
        'country': 'United States',
        'state': 'California',
        'city': 'San Francisco'
    }

    temp_cache.set(37.7749, -122.4194, location_data)

    result = temp_cache.get(37.7749, -122.4194)

    assert result is not None
    assert result['location_name'] == 'CA-San_Francisco'
    assert result['city'] == 'San Francisco'


def test_cache_miss(temp_cache):
    """Test cache miss returns None."""
    result = temp_cache.get(40.7128, -74.0060)

    assert result is None


def test_cache_rounding(temp_cache):
    """Test that cache uses coordinate rounding."""
    location_data = {
        'location_name': 'CA-San_Francisco',
        'granularity': 'major_city',
        'country': 'United States',
        'state': 'California',
        'city': 'San Francisco'
    }

    # Store with specific coordinates
    temp_cache.set(37.7749, -122.4194, location_data)

    # Should find with slightly different coordinates (within rounding)
    result = temp_cache.get(37.77491, -122.41941, precision=4)

    assert result is not None


def test_cache_replace(temp_cache):
    """Test that cache updates existing entries."""
    location_data_1 = {
        'location_name': 'Location1',
        'granularity': 'city',
        'country': 'US',
        'state': 'CA',
        'city': 'SF'
    }

    location_data_2 = {
        'location_name': 'Location2',
        'granularity': 'state',
        'country': 'US',
        'state': 'CA',
        'city': 'Oakland'
    }

    temp_cache.set(37.7749, -122.4194, location_data_1)
    temp_cache.set(37.7749, -122.4194, location_data_2)

    result = temp_cache.get(37.7749, -122.4194)

    assert result['location_name'] == 'Location2'
    assert result['city'] == 'Oakland'


def test_cache_stats(temp_cache):
    """Test cache statistics."""
    location_data = {
        'location_name': 'Test',
        'granularity': 'city',
        'country': 'US',
        'state': 'CA',
        'city': 'Test'
    }

    temp_cache.set(37.7749, -122.4194, location_data)
    temp_cache.set(40.7128, -74.0060, location_data)

    stats = temp_cache.get_stats()

    assert stats['total_entries'] == 2


def test_cache_clear(temp_cache):
    """Test clearing cache."""
    location_data = {
        'location_name': 'Test',
        'granularity': 'city',
        'country': 'US',
        'state': 'CA',
        'city': 'Test'
    }

    temp_cache.set(37.7749, -122.4194, location_data)
    temp_cache.clear()

    stats = temp_cache.get_stats()
    assert stats['total_entries'] == 0


def test_cache_context_manager():
    """Test using cache as context manager."""
    temp_file = Path(tempfile.mktemp(suffix='.db'))

    with GeocodingCache(cache_path=temp_file) as cache:
        location_data = {
            'location_name': 'Test',
            'granularity': 'city',
            'country': 'US',
            'state': 'CA',
            'city': 'Test'
        }
        cache.set(37.7749, -122.4194, location_data)

    # Connection should be closed
    assert cache.conn is None

    # Cleanup
    if temp_file.exists():
        temp_file.unlink()


def test_cache_clear_unknown(temp_cache):
    """Test clearing only Unknown entries from cache."""
    # Add some entries
    location_data_known = {
        'location_name': 'CA-San_Francisco',
        'granularity': 'major_city',
        'country': 'United States',
        'state': 'California',
        'city': 'San Francisco'
    }

    location_data_unknown = {
        'location_name': 'Unknown',
        'granularity': 'unknown',
        'country': '',
        'state': '',
        'city': ''
    }

    temp_cache.set(37.7749, -122.4194, location_data_known)
    temp_cache.set(40.7608, -111.8910, location_data_unknown)
    temp_cache.set(39.7392, -104.9903, location_data_unknown)

    # Should have 3 entries (1 known, 2 unknown)
    stats = temp_cache.get_stats()
    assert stats['total_entries'] == 3

    # Clear unknown entries
    removed = temp_cache.clear_unknown()
    assert removed == 2

    # Should have 1 entry remaining
    stats = temp_cache.get_stats()
    assert stats['total_entries'] == 1

    # Verify the known entry is still there
    result = temp_cache.get(37.7749, -122.4194)
    assert result is not None
    assert result['location_name'] == 'CA-San_Francisco'

    # Verify unknown entries are gone
    assert temp_cache.get(40.7608, -111.8910) is None
    assert temp_cache.get(39.7392, -104.9903) is None


def test_cache_clear_unknown_when_none_exist(temp_cache):
    """Test clearing unknown when there are no unknown entries."""
    location_data = {
        'location_name': 'CA',
        'granularity': 'state',
        'country': 'United States',
        'state': 'California',
        'city': ''
    }

    temp_cache.set(37.7749, -122.4194, location_data)

    # Clear unknown entries (should be 0)
    removed = temp_cache.clear_unknown()
    assert removed == 0

    # Should still have 1 entry
    stats = temp_cache.get_stats()
    assert stats['total_entries'] == 1
