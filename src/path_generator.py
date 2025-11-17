"""
Path generator for organizing media files.
"""
from pathlib import Path
from datetime import datetime
from typing import Optional
import logging

from .metadata import MediaMetadata

logger = logging.getLogger(__name__)


class PathGenerator:
    """Generate organized directory structure and file paths."""

    def __init__(self, destination_root: Path, filename_pattern: str = "{date}_{original_name}{ext}"):
        """
        Initialize path generator.

        Args:
            destination_root: Root directory for organized library
            filename_pattern: Template pattern for generating filenames
                            Available placeholders: {date}, {year}, {month}, {day},
                            {original_name}, {ext}, {counter}
        """
        self.destination_root = Path(destination_root)
        self.filename_pattern = filename_pattern

    def generate_path(self,
                     metadata: MediaMetadata,
                     location_name: Optional[str] = None) -> Path:
        """
        Generate target path for a media file.

        Path structure: YYYY/MM/Location/YYYY-MM-DD_filename.ext

        Args:
            metadata: MediaMetadata object with file information
            location_name: Location name (if None, uses "Unknown")

        Returns:
            Complete target path for the file
        """
        # Get date components
        if metadata.date_taken:
            year = str(metadata.date_taken.year)
            month = f"{metadata.date_taken.month:02d}"
            date_prefix = metadata.date_taken.strftime("%Y-%m-%d")
        else:
            year = "Unknown_Date"
            month = ""
            date_prefix = "Unknown"

        # Get location
        location = location_name or "Unknown"

        # Build directory path
        if year == "Unknown_Date":
            # Special case: no date metadata
            dir_path = self.destination_root / year / location
        else:
            dir_path = self.destination_root / year / month / location

        # Build filename
        filename = self._generate_filename(metadata, date_prefix)

        return dir_path / filename

    def _generate_filename(self, metadata: MediaMetadata, date_prefix: str) -> str:
        """
        Generate filename using the configured pattern.

        Args:
            metadata: MediaMetadata object
            date_prefix: Date prefix (e.g., "2023-06-15" or "Unknown")

        Returns:
            Generated filename
        """
        original_name = metadata.file_path.stem
        extension = metadata.file_path.suffix

        # Extract date components
        if metadata.date_taken:
            year = f"{metadata.date_taken.year:04d}"
            month = f"{metadata.date_taken.month:02d}"
            day = f"{metadata.date_taken.day:02d}"
            date = date_prefix
        else:
            year = "Unknown"
            month = "Unknown"
            day = "Unknown"
            date = "Unknown"

        # Build the filename from pattern
        filename = self.filename_pattern.format(
            date=date,
            year=year,
            month=month,
            day=day,
            original_name=original_name,
            ext=extension,
            counter=""  # Counter is handled separately in ensure_unique_path
        )

        return filename

    def ensure_unique_path(self, target_path: Path, metadata: MediaMetadata = None) -> Path:
        """
        Ensure target path is unique by adding counter if needed.

        If file exists, regenerates filename with {counter} placeholder or adds _N suffix.

        Args:
            target_path: Proposed target path
            metadata: MediaMetadata (optional, needed if pattern uses {counter})

        Returns:
            Unique target path
        """
        if not target_path.exists():
            return target_path

        # Check if pattern uses {counter} placeholder
        uses_counter_placeholder = "{counter}" in self.filename_pattern

        if uses_counter_placeholder and metadata:
            # Regenerate filename with counter in the pattern
            original_name = metadata.file_path.stem
            extension = metadata.file_path.suffix
            base_dir = target_path.parent

            if metadata.date_taken:
                year = f"{metadata.date_taken.year:04d}"
                month = f"{metadata.date_taken.month:02d}"
                day = f"{metadata.date_taken.day:02d}"
                date = metadata.date_taken.strftime("%Y-%m-%d")
            else:
                year = month = day = date = "Unknown"

            counter = 1
            while True:
                filename = self.filename_pattern.format(
                    date=date,
                    year=year,
                    month=month,
                    day=day,
                    original_name=original_name,
                    ext=extension,
                    counter=f"_{counter}"
                )
                new_path = base_dir / filename
                if not new_path.exists():
                    logger.debug(f"Generated unique path with counter: {new_path.name}")
                    return new_path
                counter += 1

                if counter > 1000:
                    raise ValueError(f"Could not generate unique path for {target_path}")
        else:
            # Fallback: add counter before extension
            base_dir = target_path.parent
            stem = target_path.stem
            extension = target_path.suffix

            counter = 1
            while True:
                new_path = base_dir / f"{stem}_{counter}{extension}"
                if not new_path.exists():
                    logger.debug(f"Generated unique path: {new_path.name}")
                    return new_path
                counter += 1

                if counter > 1000:
                    raise ValueError(f"Could not generate unique path for {target_path}")

    def create_directory(self, dir_path: Path, dry_run: bool = False) -> bool:
        """
        Create directory if it doesn't exist.

        Args:
            dir_path: Directory path to create
            dry_run: If True, don't actually create directory

        Returns:
            True if directory was created or already exists
        """
        if dir_path.exists():
            return True

        if dry_run:
            logger.debug(f"[DRY RUN] Would create directory: {dir_path}")
            return True

        try:
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created directory: {dir_path}")
            return True
        except OSError as e:
            logger.error(f"Failed to create directory {dir_path}: {e}")
            return False

    def get_relative_path(self, full_path: Path) -> Path:
        """
        Get path relative to destination root.

        Args:
            full_path: Full path

        Returns:
            Path relative to destination root
        """
        try:
            return full_path.relative_to(self.destination_root)
        except ValueError:
            # Not relative to destination root
            return full_path
