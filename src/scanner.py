"""
File scanner module for discovering photos and videos.
"""
from pathlib import Path
from typing import List, Set, Optional
import logging
import fnmatch

logger = logging.getLogger(__name__)

# Supported file extensions
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.heic', '.cr2', '.nef', '.arw', '.dng', '.gif', '.bmp', '.tiff'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.m4v', '.3gp', '.mts', '.m2ts'}
ALL_MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS


class MediaScanner:
    """Scanner for discovering photo and video files."""

    def __init__(self, image_extensions: Set[str] = None, video_extensions: Set[str] = None,
                 exclude_patterns: Optional[List[str]] = None):
        """
        Initialize the media scanner.

        Args:
            image_extensions: Set of image file extensions (with dots)
            video_extensions: Set of video file extensions (with dots)
            exclude_patterns: List of directory/file patterns to exclude (e.g., ["thumbnails", ".git", "*/cache/*"])
        """
        self.image_extensions = image_extensions or IMAGE_EXTENSIONS
        self.video_extensions = video_extensions or VIDEO_EXTENSIONS
        self.all_extensions = self.image_extensions | self.video_extensions
        self.exclude_patterns = exclude_patterns or []

    def scan(self, source_path: Path, recursive: bool = True,
             exclude_patterns: Optional[List[str]] = None) -> List[Path]:
        """
        Scan directory for media files.

        Args:
            source_path: Directory to scan
            recursive: Whether to scan subdirectories
            exclude_patterns: Additional patterns to exclude (merged with instance patterns)

        Returns:
            List of Path objects for all discovered media files

        Raises:
            ValueError: If source_path is not a directory
            FileNotFoundError: If source_path doesn't exist
        """
        if not source_path.exists():
            raise FileNotFoundError(f"Source path does not exist: {source_path}")

        if not source_path.is_dir():
            raise ValueError(f"Source path is not a directory: {source_path}")

        # Merge exclude patterns
        all_exclude_patterns = self.exclude_patterns + (exclude_patterns or [])

        if all_exclude_patterns:
            logger.info(f"Scanning {source_path} (recursive={recursive}, excluding: {all_exclude_patterns})")
        else:
            logger.info(f"Scanning {source_path} (recursive={recursive})")

        media_files = []

        if recursive:
            # Use rglob for recursive search
            for ext in self.all_extensions:
                # Case-insensitive search using both lower and upper cases
                for file_path in source_path.rglob(f"*{ext}"):
                    if file_path.is_file() and not self._should_exclude(file_path, source_path, all_exclude_patterns):
                        media_files.append(file_path)

                # Also check uppercase extensions
                for file_path in source_path.rglob(f"*{ext.upper()}"):
                    if file_path.is_file() and not self._should_exclude(file_path, source_path, all_exclude_patterns):
                        media_files.append(file_path)
        else:
            # Use glob for non-recursive search
            for ext in self.all_extensions:
                for file_path in source_path.glob(f"*{ext}"):
                    if file_path.is_file() and not self._should_exclude(file_path, source_path, all_exclude_patterns):
                        media_files.append(file_path)

                # Also check uppercase extensions
                for file_path in source_path.glob(f"*{ext.upper()}"):
                    if file_path.is_file() and not self._should_exclude(file_path, source_path, all_exclude_patterns):
                        media_files.append(file_path)

        # Remove duplicates and sort
        media_files = sorted(set(media_files))

        excluded_count = 0
        if all_exclude_patterns:
            # Calculate how many were excluded
            total_possible = len(list(source_path.rglob("*") if recursive else source_path.glob("*")))
            excluded_count = total_possible - len(media_files)

        logger.info(f"Found {len(media_files)} media files" +
                   (f" ({excluded_count} excluded)" if excluded_count > 0 else ""))
        return media_files

    def _should_exclude(self, file_path: Path, source_path: Path, exclude_patterns: List[str]) -> bool:
        """
        Check if a file should be excluded based on patterns.

        Args:
            file_path: Path to check
            source_path: Source directory (for relative path calculation)
            exclude_patterns: List of exclusion patterns

        Returns:
            True if file should be excluded
        """
        if not exclude_patterns:
            return False

        # Get relative path from source
        try:
            rel_path = file_path.relative_to(source_path)
        except ValueError:
            rel_path = file_path

        # Check each pattern
        for pattern in exclude_patterns:
            # Check directory names in path
            for parent in file_path.parents:
                if parent.name == pattern or fnmatch.fnmatch(parent.name, pattern):
                    logger.debug(f"Excluding {file_path.name} (matches directory pattern: {pattern})")
                    return True

            # Check full relative path with glob pattern
            if fnmatch.fnmatch(str(rel_path), pattern):
                logger.debug(f"Excluding {file_path.name} (matches path pattern: {pattern})")
                return True

            # Check if any part of the path matches (for patterns like ".git", "thumbnails")
            path_parts = rel_path.parts
            if pattern in path_parts:
                logger.debug(f"Excluding {file_path.name} (contains: {pattern})")
                return True

        return False

    def is_image(self, file_path: Path) -> bool:
        """Check if file is an image."""
        return file_path.suffix.lower() in self.image_extensions

    def is_video(self, file_path: Path) -> bool:
        """Check if file is a video."""
        return file_path.suffix.lower() in self.video_extensions

    def get_file_stats(self, files: List[Path]) -> dict:
        """
        Get statistics about scanned files.

        Args:
            files: List of file paths

        Returns:
            Dictionary with file statistics
        """
        stats = {
            'total': len(files),
            'images': 0,
            'videos': 0,
            'by_extension': {}
        }

        for file_path in files:
            ext = file_path.suffix.lower()

            if self.is_image(file_path):
                stats['images'] += 1
            elif self.is_video(file_path):
                stats['videos'] += 1

            stats['by_extension'][ext] = stats['by_extension'].get(ext, 0) + 1

        return stats


def scan_directory(source_path: str | Path, recursive: bool = True,
                   exclude_patterns: Optional[List[str]] = None) -> List[Path]:
    """
    Convenience function to scan a directory for media files.

    Args:
        source_path: Directory to scan (string or Path)
        recursive: Whether to scan subdirectories
        exclude_patterns: List of directory/file patterns to exclude

    Returns:
        List of Path objects for all discovered media files
    """
    scanner = MediaScanner()
    return scanner.scan(Path(source_path), recursive=recursive, exclude_patterns=exclude_patterns)
