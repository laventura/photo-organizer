"""
Location intelligence and geocoding module.
"""
from typing import Optional, Tuple, Set
from pathlib import Path
import logging
import time
import math

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import requests

from .cache import GeocodingCache

logger = logging.getLogger(__name__)

# Default major US cities
DEFAULT_MAJOR_CITIES = {
    'New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix',
    'Philadelphia', 'San Antonio', 'San Diego', 'Dallas', 'San Francisco',
    'Seattle', 'Boston', 'Miami', 'Atlanta', 'Denver', 'Las Vegas',
    'Portland', 'Austin', 'Nashville', 'Washington'
}

# Default US National Parks (top 20)
DEFAULT_NATIONAL_PARKS = {
    'Yosemite', 'Yellowstone', 'Grand Canyon', 'Zion', 'Rocky Mountain',
    'Acadia', 'Grand Teton', 'Olympic', 'Glacier', 'Bryce Canyon',
    'Arches', 'Joshua Tree', 'Great Smoky Mountains', 'Shenandoah',
    'Canyonlands', 'Mount Rainier', 'Sequoia', 'Kings Canyon',
    'Death Valley', 'Badlands'
}


class LocationIntelligence:
    """Geocoding and location intelligence with smart granularity."""

    def __init__(self,
                 cache: GeocodingCache = None,
                 locationiq_api_key: Optional[str] = None,
                 major_cities: Set[str] = None,
                 national_parks: Set[str] = None,
                 clustering_distance_miles: float = 25.0):
        """
        Initialize location intelligence.

        Args:
            cache: GeocodingCache instance (creates new if None)
            locationiq_api_key: LocationIQ API key (optional)
            major_cities: Set of major city names
            national_parks: Set of national park names
            clustering_distance_miles: Distance for location clustering (default 25 miles)
        """
        self.cache = cache or GeocodingCache()
        self.locationiq_api_key = locationiq_api_key
        self.major_cities = major_cities or DEFAULT_MAJOR_CITIES
        self.national_parks = national_parks or DEFAULT_NATIONAL_PARKS
        self.clustering_distance_miles = clustering_distance_miles

        # Initialize Nominatim geocoder (fallback, always available)
        self.nominatim = Nominatim(user_agent="photo-organizer/1.0")

        # Rate limiting
        self.last_api_call = 0
        self.min_api_interval = 1.0  # Minimum seconds between API calls

    def get_location_name(self, lat: float, lon: float) -> str:
        """
        Get location name with appropriate granularity.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            Location name formatted for folder structure
        """
        # Check cache first
        cached = self.cache.get(lat, lon)
        if cached:
            return cached['location_name']

        # Geocode the coordinates
        location_data = self._geocode(lat, lon)

        if location_data is None:
            logger.warning(f"Could not geocode ({lat}, {lon})")
            return "Unknown"

        # Apply granularity rules
        location_name = self._apply_granularity_rules(location_data)

        # Cache the result
        location_data['location_name'] = location_name
        self.cache.set(lat, lon, location_data)

        return location_name

    def _geocode(self, lat: float, lon: float) -> Optional[dict]:
        """
        Geocode coordinates using available services.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            Dictionary with location components or None
        """
        # Try LocationIQ first if API key available
        if self.locationiq_api_key:
            result = self._geocode_locationiq(lat, lon)
            if result:
                return result

        # Fallback to Nominatim
        return self._geocode_nominatim(lat, lon)

    def _geocode_locationiq(self, lat: float, lon: float) -> Optional[dict]:
        """Geocode using LocationIQ API."""
        try:
            self._rate_limit()

            url = "https://us1.locationiq.com/v1/reverse.php"
            params = {
                'key': self.locationiq_api_key,
                'lat': lat,
                'lon': lon,
                'format': 'json',
                'zoom': 10  # City level
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            address = data.get('address', {})

            return self._parse_geocode_result(address)

        except Exception as e:
            logger.debug(f"LocationIQ geocoding failed: {e}")
            return None

    def _geocode_nominatim(self, lat: float, lon: float) -> Optional[dict]:
        """Geocode using Nominatim (OpenStreetMap)."""
        try:
            self._rate_limit()

            location = self.nominatim.reverse((lat, lon), language='en')

            if location and location.raw:
                address = location.raw.get('address', {})
                return self._parse_geocode_result(address)

        except (GeocoderTimedOut, GeocoderServiceError) as e:
            logger.debug(f"Nominatim geocoding failed: {e}")

        return None

    def _parse_geocode_result(self, address: dict) -> dict:
        """
        Parse geocoding result into standard format.

        Args:
            address: Address dictionary from geocoding service

        Returns:
            Standardized location dictionary
        """
        # Extract components (handle various naming conventions)
        country = address.get('country', '')
        state = (address.get('state') or
                 address.get('province') or
                 address.get('region') or '')
        city = (address.get('city') or
                address.get('town') or
                address.get('village') or
                address.get('municipality') or '')
        county = address.get('county', '')

        return {
            'country': country,
            'state': state,
            'city': city,
            'county': county,
            'granularity': ''  # Will be set by granularity rules
        }

    def _apply_granularity_rules(self, location_data: dict) -> str:
        """
        Apply location granularity rules to determine folder name.

        Rules:
        1. Foreign countries → Country name only
        2. US National Parks → State-Park
        3. US major cities → State-City
        4. US rural areas → State only

        Args:
            location_data: Dictionary with location components

        Returns:
            Location name for folder structure
        """
        country = location_data.get('country', '')
        state = location_data.get('state', '')
        city = location_data.get('city', '')
        county = location_data.get('county', '')

        # Check if in US
        is_us = 'United States' in country or 'USA' in country or country == 'US'

        if not is_us:
            # Foreign country - use country name only
            location_data['granularity'] = 'country'
            return self._normalize_name(country) if country else 'Unknown'

        # US location - check for national parks
        for park in self.national_parks:
            if park.lower() in county.lower() or park.lower() in city.lower():
                location_data['granularity'] = 'national_park'
                state_abbr = self._get_state_abbreviation(state)
                return f"{state_abbr}-{self._normalize_name(park)}"

        # Check if major city
        if city and any(major_city.lower() in city.lower() for major_city in self.major_cities):
            location_data['granularity'] = 'major_city'
            state_abbr = self._get_state_abbreviation(state)
            return f"{state_abbr}-{self._normalize_name(city)}"

        # Rural area - state only
        location_data['granularity'] = 'state'
        return self._get_state_abbreviation(state) if state else 'Unknown'

    def _normalize_name(self, name: str) -> str:
        """
        Normalize location name for folder structure.

        Args:
            name: Location name

        Returns:
            Normalized name (spaces to underscores, special chars removed)
        """
        # Replace spaces with underscores
        name = name.replace(' ', '_')
        # Remove special characters (keep alphanumeric, underscore, hyphen)
        name = ''.join(c for c in name if c.isalnum() or c in ('_', '-'))
        return name

    def _get_state_abbreviation(self, state: str) -> str:
        """
        Convert state name to abbreviation.

        Args:
            state: State name

        Returns:
            Two-letter state abbreviation
        """
        state_abbrev = {
            'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR',
            'California': 'CA', 'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE',
            'Florida': 'FL', 'Georgia': 'GA', 'Hawaii': 'HI', 'Idaho': 'ID',
            'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA', 'Kansas': 'KS',
            'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD',
            'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS',
            'Missouri': 'MO', 'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV',
            'New Hampshire': 'NH', 'New Jersey': 'NJ', 'New Mexico': 'NM', 'New York': 'NY',
            'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH', 'Oklahoma': 'OK',
            'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
            'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT',
            'Vermont': 'VT', 'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV',
            'Wisconsin': 'WI', 'Wyoming': 'WY', 'District of Columbia': 'DC'
        }

        # Return abbreviation if found, otherwise return original
        return state_abbrev.get(state, state)

    def _rate_limit(self):
        """Enforce rate limiting for API calls."""
        now = time.time()
        time_since_last = now - self.last_api_call

        if time_since_last < self.min_api_interval:
            sleep_time = self.min_api_interval - time_since_last
            time.sleep(sleep_time)

        self.last_api_call = time.time()

    def calculate_distance_miles(self, lat1: float, lon1: float,
                                 lat2: float, lon2: float) -> float:
        """
        Calculate distance between two GPS coordinates using Haversine formula.

        Args:
            lat1, lon1: First coordinate
            lat2, lon2: Second coordinate

        Returns:
            Distance in miles
        """
        # Convert to radians
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        # Haversine formula
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon / 2) ** 2)
        c = 2 * math.asin(math.sqrt(a))

        # Earth radius in miles
        radius = 3959.0

        return radius * c

    def should_cluster_locations(self, lat1: float, lon1: float,
                                lat2: float, lon2: float) -> bool:
        """
        Determine if two locations should be clustered together.

        Args:
            lat1, lon1: First coordinate
            lat2, lon2: Second coordinate

        Returns:
            True if locations should be clustered
        """
        distance = self.calculate_distance_miles(lat1, lon1, lat2, lon2)
        return distance <= self.clustering_distance_miles

    def close(self):
        """Close cache connection."""
        if self.cache:
            self.cache.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
