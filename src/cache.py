"""
SQLite cache for geocoding results.
"""
import sqlite3
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class GeocodingCache:
    """SQLite-based cache for geocoding results."""

    def __init__(self, cache_path: Path = None):
        """
        Initialize the geocoding cache.

        Args:
            cache_path: Path to SQLite database file (defaults to ~/.photo_organizer_cache.db)
        """
        if cache_path is None:
            cache_path = Path.home() / ".photo_organizer_cache.db"

        self.cache_path = cache_path
        self.conn: Optional[sqlite3.Connection] = None
        self._initialize_db()

    def _initialize_db(self):
        """Create the database and tables if they don't exist."""
        self.conn = sqlite3.connect(str(self.cache_path))
        cursor = self.conn.cursor()

        # Create geocoding cache table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS geocoding_cache (
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                location_name TEXT NOT NULL,
                granularity TEXT NOT NULL,
                country TEXT,
                state TEXT,
                city TEXT,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (latitude, longitude)
            )
        """)

        # Create index for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_coords
            ON geocoding_cache(latitude, longitude)
        """)

        self.conn.commit()
        logger.debug(f"Initialized geocoding cache at {self.cache_path}")

    def get(self, lat: float, lon: float, precision: int = 4) -> Optional[dict]:
        """
        Get cached geocoding result.

        Args:
            lat: Latitude
            lon: Longitude
            precision: Decimal places to round coordinates to (default 4 ≈ 11 meters)

        Returns:
            Dictionary with location data or None if not cached
        """
        if self.conn is None:
            return None

        # Round coordinates for cache lookup (allows nearby locations to share cache)
        lat_rounded = round(lat, precision)
        lon_rounded = round(lon, precision)

        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT location_name, granularity, country, state, city, cached_at
            FROM geocoding_cache
            WHERE latitude = ? AND longitude = ?
        """, (lat_rounded, lon_rounded))

        row = cursor.fetchone()
        if row:
            logger.debug(f"Cache hit for ({lat}, {lon})")
            return {
                'location_name': row[0],
                'granularity': row[1],
                'country': row[2],
                'state': row[3],
                'city': row[4],
                'cached_at': row[5]
            }

        logger.debug(f"Cache miss for ({lat}, {lon})")
        return None

    def set(self, lat: float, lon: float, location_data: dict, precision: int = 4):
        """
        Store geocoding result in cache.

        Args:
            lat: Latitude
            lon: Longitude
            location_data: Dictionary with location information
            precision: Decimal places to round coordinates to
        """
        if self.conn is None:
            return

        lat_rounded = round(lat, precision)
        lon_rounded = round(lon, precision)

        cursor = self.conn.cursor()

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO geocoding_cache
                (latitude, longitude, location_name, granularity, country, state, city, cached_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                lat_rounded,
                lon_rounded,
                location_data.get('location_name', ''),
                location_data.get('granularity', ''),
                location_data.get('country', ''),
                location_data.get('state', ''),
                location_data.get('city', ''),
                datetime.now().isoformat()
            ))

            self.conn.commit()
            logger.debug(f"Cached geocoding result for ({lat}, {lon})")

        except sqlite3.Error as e:
            logger.error(f"Error caching geocoding result: {e}")
            self.conn.rollback()

    def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        if self.conn is None:
            return {'total_entries': 0}

        cursor = self.conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM geocoding_cache")
        total = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM geocoding_cache
            WHERE cached_at >= date('now', '-30 days')
        """)
        recent = cursor.fetchone()[0]

        return {
            'total_entries': total,
            'recent_entries': recent,
            'cache_path': str(self.cache_path)
        }

    def clear(self):
        """Clear all cached entries."""
        if self.conn is None:
            return

        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM geocoding_cache")
        self.conn.commit()
        logger.info("Cleared all cache entries")

    def clear_unknown(self) -> int:
        """
        Clear cached entries with 'Unknown' location names.

        Returns:
            Number of entries removed
        """
        if self.conn is None:
            return 0

        cursor = self.conn.cursor()

        # Count how many will be deleted
        cursor.execute("SELECT COUNT(*) FROM geocoding_cache WHERE location_name = 'Unknown'")
        count = cursor.fetchone()[0]

        # Delete Unknown entries
        cursor.execute("DELETE FROM geocoding_cache WHERE location_name = 'Unknown'")
        self.conn.commit()

        logger.info(f"Cleared {count} 'Unknown' cache entries")
        return count

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
