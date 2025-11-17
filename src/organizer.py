"""
File organizer with dry-run support and safety features.
"""
from pathlib import Path
from typing import List, Dict, Optional
import shutil
import logging
from tqdm import tqdm

from .scanner import MediaScanner
from .metadata import MetadataExtractor
from .location import LocationIntelligence
from .path_generator import PathGenerator
from .utils import Statistics, TransactionLog, verify_file_integrity

logger = logging.getLogger(__name__)


class PhotoOrganizer:
    """Main organizer for photo and video files."""

    def __init__(self,
                 source_path: Path,
                 destination_path: Path,
                 location_intelligence: LocationIntelligence,
                 mode: str = 'move',
                 dry_run: bool = False,
                 verify: bool = True,
                 exclude_patterns: Optional[List[str]] = None,
                 filename_pattern: str = "{date}_{original_name}{ext}"):
        """
        Initialize the photo organizer.

        Args:
            source_path: Source directory with unorganized files
            destination_path: Destination directory for organized library
            location_intelligence: LocationIntelligence instance
            mode: 'move' or 'copy'
            dry_run: If True, preview only (no actual file operations)
            verify: If True, verify file integrity after copy/move
            exclude_patterns: List of directory/file patterns to exclude during scanning
            filename_pattern: Template pattern for generating filenames
        """
        self.source_path = Path(source_path)
        self.destination_path = Path(destination_path)
        self.location_intelligence = location_intelligence
        self.mode = mode
        self.dry_run = dry_run
        self.verify = verify
        self.exclude_patterns = exclude_patterns or []
        self.filename_pattern = filename_pattern

        # Initialize components
        self.scanner = MediaScanner(exclude_patterns=self.exclude_patterns)
        self.metadata_extractor = MetadataExtractor()
        self.path_generator = PathGenerator(self.destination_path, filename_pattern=self.filename_pattern)

        # Statistics and logging
        self.stats = Statistics()
        self.duplicates: List[Dict] = []

        # Transaction log
        log_file = self.destination_path / "transaction_log.json"
        self.transaction_log = TransactionLog(log_file)

    def organize(self) -> Statistics:
        """
        Organize all media files.

        Returns:
            Statistics object with execution summary
        """
        logger.info(f"Starting organization (mode={self.mode}, dry_run={self.dry_run})")
        logger.info(f"Source: {self.source_path}")
        logger.info(f"Destination: {self.destination_path}")

        # Validate paths
        if not self.source_path.exists():
            raise FileNotFoundError(f"Source path does not exist: {self.source_path}")

        if not self.destination_path.exists() and not self.dry_run:
            self.destination_path.mkdir(parents=True, exist_ok=True)

        # Scan for files
        logger.info("Scanning for media files...")
        media_files = self.scanner.scan(self.source_path)
        self.stats.total_files = len(media_files)

        if not media_files:
            logger.warning("No media files found!")
            return self.stats

        logger.info(f"Found {len(media_files)} media files")

        # Process each file
        with tqdm(media_files, desc="Organizing files", unit="file") as pbar:
            for file_path in pbar:
                pbar.set_description(f"Processing {file_path.name}")
                self._process_file(file_path)

        # Save transaction log
        if not self.dry_run:
            self.transaction_log.save()

        # Save duplicates report
        if self.duplicates:
            self._save_duplicates_report()

        return self.stats

    def _process_file(self, file_path: Path):
        """
        Process a single media file.

        Args:
            file_path: Path to the media file
        """
        try:
            # Extract metadata
            metadata = self.metadata_extractor.extract(file_path)

            # Update statistics
            has_date = metadata.date_taken is not None
            has_gps = metadata.gps_coords is not None

            self.stats.record_date(has_date)
            self.stats.record_gps(has_gps)

            # Get location name
            location_name = None
            if has_gps:
                lat, lon = metadata.gps_coords

                # Check cache first
                cached = self.location_intelligence.cache.get(lat, lon)
                if cached:
                    location_name = cached['location_name']
                    self.stats.record_cache_hit()
                else:
                    location_name = self.location_intelligence.get_location_name(lat, lon)
                    self.stats.record_api_call()

                self.stats.record_location(location_name)

            # Generate target path
            target_path = self.path_generator.generate_path(metadata, location_name)

            # Check for duplicates
            if target_path.exists():
                target_path = self.path_generator.ensure_unique_path(target_path, metadata)
                self.stats.record_duplicate()
                self.duplicates.append({
                    'original': str(file_path),
                    'target': str(target_path)
                })

            # Create directory
            target_dir = target_path.parent
            if not self.path_generator.create_directory(target_dir, self.dry_run):
                logger.error(f"Failed to create directory: {target_dir}")
                self.stats.record_failed(f"Failed to create directory for {file_path.name}")
                return

            # Perform file operation
            if self.dry_run:
                logger.info(f"[DRY RUN] Would {self.mode}: {file_path} -> {target_path}")
                self.stats.record_processed()
            else:
                success = self._perform_file_operation(file_path, target_path)
                if success:
                    self.stats.record_processed()
                else:
                    self.stats.record_failed(f"Failed to {self.mode} {file_path.name}")

        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}", exc_info=True)
            self.stats.record_failed(f"{file_path.name}: {str(e)}")

    def _perform_file_operation(self, source: Path, destination: Path) -> bool:
        """
        Perform the actual file operation (move or copy).

        Args:
            source: Source file path
            destination: Destination file path

        Returns:
            True if successful
        """
        try:
            if self.mode == 'move':
                shutil.move(str(source), str(destination))
                logger.debug(f"Moved: {source.name} -> {destination}")
            elif self.mode == 'copy':
                shutil.copy2(str(source), str(destination))
                logger.debug(f"Copied: {source.name} -> {destination}")

                # Verify integrity if requested
                if self.verify:
                    if not verify_file_integrity(source, destination):
                        logger.error(f"Integrity verification failed: {destination}")
                        destination.unlink()  # Remove corrupted copy
                        self.transaction_log.log_operation(
                            self.mode, source, destination, False, "Integrity verification failed"
                        )
                        return False
            else:
                raise ValueError(f"Invalid mode: {self.mode}")

            # Log successful operation
            self.transaction_log.log_operation(self.mode, source, destination, True)
            return True

        except Exception as e:
            logger.error(f"File operation failed: {e}")
            self.transaction_log.log_operation(self.mode, source, destination, False, str(e))
            return False

    def _save_duplicates_report(self):
        """Save report of duplicate files."""
        report_path = self.destination_path / "duplicates_report.txt"

        try:
            with open(report_path, 'w') as f:
                f.write("DUPLICATE FILES REPORT\n")
                f.write("=" * 80 + "\n\n")
                f.write(f"Total duplicates found: {len(self.duplicates)}\n\n")

                for i, dup in enumerate(self.duplicates, 1):
                    f.write(f"{i}. Original: {dup['original']}\n")
                    f.write(f"   Target:   {dup['target']}\n\n")

            logger.info(f"Duplicates report saved to: {report_path}")

        except Exception as e:
            logger.error(f"Failed to save duplicates report: {e}")

    def preview(self, limit: int = 20) -> List[Dict]:
        """
        Preview how files would be organized (dry-run preview).

        Args:
            limit: Maximum number of files to preview

        Returns:
            List of dictionaries with source and target paths
        """
        logger.info(f"Generating preview (limit={limit})")

        media_files = self.scanner.scan(self.source_path)
        preview_items = []

        for file_path in media_files[:limit]:
            try:
                metadata = self.metadata_extractor.extract(file_path)

                location_name = None
                if metadata.gps_coords:
                    lat, lon = metadata.gps_coords
                    location_name = self.location_intelligence.get_location_name(lat, lon)

                target_path = self.path_generator.generate_path(metadata, location_name)
                relative_target = self.path_generator.get_relative_path(target_path)

                preview_items.append({
                    'source': str(file_path),
                    'target': str(relative_target),
                    'has_gps': metadata.gps_coords is not None,
                    'has_date': metadata.date_taken is not None,
                    'location': location_name or "Unknown"
                })

            except Exception as e:
                logger.error(f"Error previewing {file_path}: {e}")

        return preview_items

    def print_preview(self, limit: int = 20):
        """
        Print preview of how files would be organized.

        Args:
            limit: Maximum number of files to preview
        """
        preview_items = self.preview(limit)

        print("\n" + "=" * 80)
        print(f"PREVIEW: How files will be organized (showing {len(preview_items)} of {self.stats.total_files})")
        print("=" * 80 + "\n")

        for item in preview_items:
            gps_indicator = "📍" if item['has_gps'] else "  "
            date_indicator = "📅" if item['has_date'] else "  "

            print(f"{gps_indicator} {date_indicator} {Path(item['source']).name}")
            print(f"    → {item['target']}")
            print(f"    Location: {item['location']}\n")

        print("=" * 80 + "\n")
