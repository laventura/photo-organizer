"""
Metadata extraction module for photos and videos.
"""
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple
import logging
import subprocess
import json
import shutil

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from mutagen.mp4 import MP4
import pillow_heif

logger = logging.getLogger(__name__)

# Register HEIF opener
pillow_heif.register_heif_opener()


class MediaMetadata:
    """Container for media file metadata."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.date_taken: Optional[datetime] = None
        self.gps_coords: Optional[Tuple[float, float]] = None  # (latitude, longitude)
        self.width: Optional[int] = None
        self.height: Optional[int] = None
        self.camera_make: Optional[str] = None
        self.camera_model: Optional[str] = None

    def __repr__(self):
        return (f"MediaMetadata(file={self.file_path.name}, "
                f"date={self.date_taken}, gps={self.gps_coords})")


class MetadataExtractor:
    """Extract metadata from photos and videos."""

    def __init__(self):
        """Initialize the metadata extractor."""
        # Check if exiftool is available
        self._exiftool_available = shutil.which('exiftool') is not None
        if not self._exiftool_available:
            logger.warning("exiftool not found - video GPS extraction may be limited")

    def extract(self, file_path: Path) -> MediaMetadata:
        """
        Extract metadata from a media file.

        Args:
            file_path: Path to the media file

        Returns:
            MediaMetadata object with extracted information
        """
        metadata = MediaMetadata(file_path)

        ext = file_path.suffix.lower()

        try:
            # Images
            if ext in {'.jpg', '.jpeg', '.png', '.heic', '.tiff', '.bmp', '.gif'}:
                self._extract_image_metadata(file_path, metadata)
            # RAW formats
            elif ext in {'.cr2', '.nef', '.arw', '.dng'}:
                self._extract_raw_metadata(file_path, metadata)
            # Videos
            elif ext in {'.mp4', '.mov', '.m4v', '.3gp'}:
                self._extract_video_metadata(file_path, metadata)
            # Other video formats
            elif ext in {'.avi', '.mkv', '.mts', '.m2ts'}:
                self._extract_video_metadata_fallback(file_path, metadata)

            # Fallback to file system date if no metadata found
            if metadata.date_taken is None:
                metadata.date_taken = self._get_file_creation_date(file_path)

        except Exception as e:
            logger.warning(f"Error extracting metadata from {file_path.name}: {e}")
            # Still set file creation date as fallback
            metadata.date_taken = self._get_file_creation_date(file_path)

        return metadata

    def _extract_image_metadata(self, file_path: Path, metadata: MediaMetadata):
        """Extract metadata from image files using Pillow."""
        try:
            with Image.open(file_path) as img:
                # Get image dimensions
                metadata.width, metadata.height = img.size

                # Get EXIF data
                exif_data = img.getexif()
                if exif_data:
                    # Extract date
                    date_str = exif_data.get(0x9003) or exif_data.get(0x0132)  # DateTimeOriginal or DateTime
                    if date_str:
                        metadata.date_taken = self._parse_exif_date(date_str)

                    # Extract camera info
                    metadata.camera_make = exif_data.get(0x010F)  # Make
                    metadata.camera_model = exif_data.get(0x0110)  # Model

                    # Extract GPS data
                    gps_info = exif_data.get_ifd(0x8825)  # GPS IFD
                    if gps_info:
                        metadata.gps_coords = self._parse_gps_coords(gps_info)

        except Exception as e:
            logger.debug(f"Error reading image EXIF from {file_path.name}: {e}")

    def _extract_raw_metadata(self, file_path: Path, metadata: MediaMetadata):
        """Extract metadata from RAW image files."""
        # For RAW files, we'll try to use Pillow which can handle some RAW formats
        # For more comprehensive RAW support, we might need rawpy or similar
        try:
            self._extract_image_metadata(file_path, metadata)
        except Exception as e:
            logger.debug(f"Error reading RAW metadata from {file_path.name}: {e}")

    def _extract_metadata_with_exiftool(self, file_path: Path, metadata: MediaMetadata):
        """
        Extract metadata using exiftool (most reliable for video files).

        Args:
            file_path: Path to media file
            metadata: MediaMetadata object to populate
        """
        if not self._exiftool_available:
            return

        try:
            # Run exiftool with JSON output for easy parsing
            result = subprocess.run(
                ['exiftool', '-j', '-G', '-n',  # -n for numeric GPS values
                 '-DateTimeOriginal', '-CreateDate', '-CreationDate', '-MediaCreateDate',
                 '-GPSLatitude', '-GPSLongitude', '-GPSPosition',
                 '-ImageWidth', '-ImageHeight', '-Make', '-Model',
                 str(file_path)],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                logger.debug(f"exiftool failed for {file_path.name}: {result.stderr}")
                return

            data = json.loads(result.stdout)[0]

            # Extract date/time (try multiple fields)
            date_fields = [
                'DateTimeOriginal', 'CreateDate', 'CreationDate',
                'MediaCreateDate', 'QuickTime:CreateDate', 'QuickTime:CreationDate'
            ]
            for field in date_fields:
                if field in data and data[field]:
                    date_value = data[field]
                    # Remove timezone info if present
                    if isinstance(date_value, str):
                        date_value = date_value.split('+')[0].split('-', 3)[0:3]
                        if len(date_value) == 3:
                            date_value = '-'.join(date_value)
                        else:
                            date_value = data[field].split('+')[0]
                    parsed_date = self._parse_exiftool_date(date_value)
                    if parsed_date:
                        metadata.date_taken = parsed_date
                        logger.debug(f"Extracted date from {field}: {parsed_date}")
                        break

            # Extract GPS coordinates
            gps_lat = None
            gps_lon = None

            # Try to get numeric GPS values
            if 'Composite:GPSLatitude' in data:
                gps_lat = float(data['Composite:GPSLatitude'])
            elif 'GPSLatitude' in data:
                gps_lat = float(data['GPSLatitude'])

            if 'Composite:GPSLongitude' in data:
                gps_lon = float(data['Composite:GPSLongitude'])
            elif 'GPSLongitude' in data:
                gps_lon = float(data['GPSLongitude'])

            if gps_lat is not None and gps_lon is not None:
                metadata.gps_coords = (gps_lat, gps_lon)
                logger.debug(f"Extracted GPS: {gps_lat}, {gps_lon}")

            # Extract dimensions
            if 'ImageWidth' in data and data['ImageWidth']:
                metadata.width = int(data['ImageWidth'])
            if 'ImageHeight' in data and data['ImageHeight']:
                metadata.height = int(data['ImageHeight'])

            # Extract camera info
            if 'Make' in data and data['Make']:
                metadata.camera_make = data['Make']
            if 'Model' in data and data['Model']:
                metadata.camera_model = data['Model']

        except subprocess.TimeoutExpired:
            logger.warning(f"exiftool timed out for {file_path.name}")
        except json.JSONDecodeError as e:
            logger.debug(f"Could not parse exiftool JSON for {file_path.name}: {e}")
        except Exception as e:
            logger.debug(f"Error using exiftool on {file_path.name}: {e}")

    def _parse_exiftool_date(self, date_value: str) -> Optional[datetime]:
        """
        Parse date string from exiftool output.

        Args:
            date_value: Date string from exiftool

        Returns:
            datetime object or None
        """
        if not date_value or not isinstance(date_value, str):
            return None

        # Clean up the date string
        date_str = date_value.strip()

        # Try various date formats
        formats = [
            "%Y:%m:%d %H:%M:%S",      # EXIF format
            "%Y-%m-%d %H:%M:%S",      # ISO-like format
            "%Y:%m:%d",               # Date only
            "%Y-%m-%d",               # ISO date only
            "%Y-%m-%dT%H:%M:%S",      # ISO format
            "%Y-%m-%dT%H:%M:%SZ",     # ISO with Z
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str.split('.')[0], fmt)  # Remove microseconds
            except ValueError:
                continue

        logger.debug(f"Could not parse date: {date_value}")
        return None

    def _extract_video_metadata(self, file_path: Path, metadata: MediaMetadata):
        """
        Extract metadata from MP4/MOV video files.

        Uses exiftool as primary method (most reliable for GPS data),
        falls back to mutagen for additional metadata if needed.
        """
        # Try exiftool first - it's the most reliable for video GPS data
        if self._exiftool_available:
            self._extract_metadata_with_exiftool(file_path, metadata)

        # If we still don't have all metadata, try mutagen as fallback
        if metadata.date_taken is None or metadata.width is None:
            try:
                video = MP4(str(file_path))

                # Extract creation date if not already found
                if metadata.date_taken is None:
                    if '\xa9day' in video:  # Creation date
                        date_str = video['\xa9day'][0]
                        metadata.date_taken = self._parse_video_date(date_str)
                    elif 'creation_time' in video:
                        date_str = video['creation_time'][0]
                        metadata.date_taken = self._parse_video_date(date_str)

                # Extract GPS coordinates if not already found (unlikely to work, but try)
                if metadata.gps_coords is None and '\xa9xyz' in video:
                    gps_str = video['\xa9xyz'][0]
                    metadata.gps_coords = self._parse_video_gps(gps_str)

                # Video dimensions if not already found
                if metadata.width is None and 'width' in video.info and 'height' in video.info:
                    metadata.width = video.info.width
                    metadata.height = video.info.height

            except Exception as e:
                logger.debug(f"Error reading video metadata with mutagen from {file_path.name}: {e}")

    def _extract_video_metadata_fallback(self, file_path: Path, metadata: MediaMetadata):
        """
        Fallback video metadata extraction for formats mutagen doesn't handle well.

        For AVI, MKV, MTS, etc., use exiftool if available.
        """
        logger.debug(f"Using fallback metadata extraction for {file_path.name}")

        # Try exiftool for these formats too
        if self._exiftool_available:
            self._extract_metadata_with_exiftool(file_path, metadata)

    def _parse_exif_date(self, date_str: str) -> Optional[datetime]:
        """Parse EXIF date string to datetime."""
        try:
            # EXIF format: "YYYY:MM:DD HH:MM:SS"
            return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
        except ValueError:
            try:
                # Try without time
                return datetime.strptime(date_str, "%Y:%m:%d")
            except ValueError:
                logger.debug(f"Could not parse EXIF date: {date_str}")
                return None

    def _parse_video_date(self, date_str: str) -> Optional[datetime]:
        """Parse video metadata date string to datetime."""
        try:
            # ISO 8601 format
            if 'T' in date_str:
                # Remove timezone info if present
                date_str = date_str.split('+')[0].split('Z')[0]
                return datetime.fromisoformat(date_str)
            else:
                # Simple date format
                return datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, AttributeError) as e:
            logger.debug(f"Could not parse video date: {date_str} - {e}")
            return None

    def _parse_gps_coords(self, gps_info: dict) -> Optional[Tuple[float, float]]:
        """
        Parse GPS coordinates from EXIF GPS IFD.

        Args:
            gps_info: GPS IFD dictionary

        Returns:
            Tuple of (latitude, longitude) or None
        """
        try:
            # Get GPS latitude
            gps_latitude = gps_info.get(2)  # GPSLatitude
            gps_latitude_ref = gps_info.get(1)  # GPSLatitudeRef

            # Get GPS longitude
            gps_longitude = gps_info.get(4)  # GPSLongitude
            gps_longitude_ref = gps_info.get(3)  # GPSLongitudeRef

            if gps_latitude and gps_longitude:
                lat = self._convert_to_degrees(gps_latitude)
                if gps_latitude_ref == 'S':
                    lat = -lat

                lon = self._convert_to_degrees(gps_longitude)
                if gps_longitude_ref == 'W':
                    lon = -lon

                return (lat, lon)

        except Exception as e:
            logger.debug(f"Error parsing GPS coordinates: {e}")

        return None

    def _convert_to_degrees(self, value) -> float:
        """
        Convert GPS coordinates from degrees/minutes/seconds to decimal degrees.

        Args:
            value: GPS coordinate in DMS format (tuple of 3 values)

        Returns:
            Decimal degrees
        """
        d, m, s = value
        return float(d) + float(m) / 60.0 + float(s) / 3600.0

    def _parse_video_gps(self, gps_str: str) -> Optional[Tuple[float, float]]:
        """
        Parse GPS coordinates from video metadata string.

        Args:
            gps_str: GPS string (various formats possible)

        Returns:
            Tuple of (latitude, longitude) or None
        """
        try:
            # Format might be: "+37.7749-122.4194/" or similar
            # This is highly format-dependent, so we'll handle common cases
            parts = gps_str.replace('/', '').split()
            if len(parts) >= 2:
                lat = float(parts[0])
                lon = float(parts[1])
                return (lat, lon)
        except Exception as e:
            logger.debug(f"Could not parse video GPS: {gps_str} - {e}")

        return None

    def _get_file_creation_date(self, file_path: Path) -> datetime:
        """Get file creation date from filesystem."""
        stat = file_path.stat()
        # Use birthtime (creation time) on macOS, or mtime as fallback
        timestamp = getattr(stat, 'st_birthtime', stat.st_mtime)
        return datetime.fromtimestamp(timestamp)


def extract_metadata(file_path: Path) -> MediaMetadata:
    """
    Convenience function to extract metadata from a file.

    Args:
        file_path: Path to the media file

    Returns:
        MediaMetadata object
    """
    extractor = MetadataExtractor()
    return extractor.extract(file_path)
