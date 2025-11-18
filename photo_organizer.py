#!/usr/bin/env python3
"""
Photo/Video Organizer - Main CLI entry point
"""
import argparse
import sys
from pathlib import Path
from datetime import datetime
import yaml
import logging

from src.organizer import PhotoOrganizer
from src.location import LocationIntelligence
from src.cache import GeocodingCache
from src.utils import setup_logging, get_disk_space, format_bytes

logger = logging.getLogger(__name__)


def load_config(config_path: Path = None) -> dict:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to config file (defaults to ./config.yaml)

    Returns:
        Configuration dictionary
    """
    if config_path is None:
        config_path = Path(__file__).parent / "config.yaml"

    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.warning(f"Config file not found: {config_path}, using defaults")
        return {}
    except yaml.YAMLError as e:
        logger.error(f"Error parsing config file: {e}")
        return {}


def check_disk_space(destination: Path, required_gb: float = 1.0) -> bool:
    """
    Check if destination has enough disk space.

    Args:
        destination: Destination path
        required_gb: Required space in GB

    Returns:
        True if sufficient space available
    """
    try:
        space = get_disk_space(destination)
        free_gb = space['free'] / (1024 ** 3)

        logger.info(f"Disk space at {destination}:")
        logger.info(f"  Free: {format_bytes(space['free'])}")
        logger.info(f"  Total: {format_bytes(space['total'])}")

        if free_gb < required_gb:
            logger.error(f"Insufficient disk space! Required: {required_gb}GB, Available: {free_gb:.1f}GB")
            return False

        return True

    except Exception as e:
        logger.warning(f"Could not check disk space: {e}")
        return True  # Allow to proceed if check fails


def confirm_operation(organizer: PhotoOrganizer, preview_count: int = 10):
    """
    Show preview and ask for user confirmation.

    Args:
        organizer: PhotoOrganizer instance
        preview_count: Number of files to preview
    """
    print("\n" + "=" * 80)
    print("OPERATION PREVIEW")
    print("=" * 80)
    print(f"Source:      {organizer.source_path}")
    print(f"Destination: {organizer.destination_path}")
    print(f"Mode:        {organizer.mode.upper()}")
    print(f"Dry Run:     {organizer.dry_run}")
    print("=" * 80 + "\n")

    # Show preview
    organizer.print_preview(limit=preview_count)

    # Ask for confirmation
    if organizer.dry_run:
        print("This is a DRY RUN - no files will be modified.")
        return True

    response = input(f"\nProceed with {organizer.mode} operation? [y/N]: ")
    return response.lower() in ('y', 'yes')


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Photo/Video Organizer - Automatically organize media files by date and location",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (preview only)
  python photo_organizer.py --source ~/Pictures/Unsorted --destination ~/Pictures/Organized --dry-run

  # Move files (default)
  python photo_organizer.py --source ~/Pictures/Unsorted --destination ~/Pictures/Organized

  # Copy files (safer)
  python photo_organizer.py --source ~/Pictures/Unsorted --destination ~/Pictures/Organized --mode copy

  # Exclude directories
  python photo_organizer.py --source ~/Pictures/Unsorted --destination ~/Pictures/Organized --exclude thumbnails --exclude .cache

  # Retry geocoding for previously unknown locations
  python photo_organizer.py --source ~/Pictures/Unsorted --destination ~/Pictures/Organized --retry-unknown --dry-run

  # Clear entire cache and start fresh
  python photo_organizer.py --source ~/Pictures/Unsorted --destination ~/Pictures/Organized --clear-cache

  # Use custom config
  python photo_organizer.py --source ~/Pictures/Unsorted --destination ~/Pictures/Organized --config myconfig.yaml
        """
    )

    parser.add_argument(
        '--source',
        type=str,
        required=True,
        help='Source directory with unorganized photos/videos'
    )

    parser.add_argument(
        '--destination',
        type=str,
        required=True,
        help='Destination directory for organized library'
    )

    parser.add_argument(
        '--mode',
        choices=['move', 'copy'],
        default='move',
        help='Operation mode: move or copy files (default: move)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview only, do not modify files'
    )

    parser.add_argument(
        '--no-verify',
        action='store_true',
        help='Skip file integrity verification (faster but less safe)'
    )

    parser.add_argument(
        '--exclude',
        action='append',
        metavar='PATTERN',
        help='Exclude directories/files matching pattern (can be used multiple times). Examples: thumbnails, .git, */cache/*'
    )

    parser.add_argument(
        '--config',
        type=str,
        help='Path to configuration file (default: ./config.yaml)'
    )

    parser.add_argument(
        '--locationiq-key',
        type=str,
        help='LocationIQ API key (overrides config file)'
    )

    parser.add_argument(
        '--yes',
        action='store_true',
        help='Skip confirmation prompt'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    parser.add_argument(
        '--preview-only',
        type=int,
        metavar='N',
        help='Show preview of N files and exit'
    )

    parser.add_argument(
        '--clear-cache',
        action='store_true',
        help='Clear entire geocoding cache before processing'
    )

    parser.add_argument(
        '--retry-unknown',
        action='store_true',
        help='Retry geocoding for locations previously marked as "Unknown"'
    )

    args = parser.parse_args()

    # Load configuration
    config_path = Path(args.config) if args.config else None
    config = load_config(config_path)

    # Validate paths (before logging setup, so we can create destination for log file)
    source_path = Path(args.source).expanduser().resolve()
    destination_path = Path(args.destination).expanduser().resolve()

    if not source_path.exists():
        print(f"ERROR: Source path does not exist: {source_path}", file=sys.stderr)
        sys.exit(1)

    if not source_path.is_dir():
        print(f"ERROR: Source path is not a directory: {source_path}", file=sys.stderr)
        sys.exit(1)

    # Validate/create destination directory
    if not destination_path.exists():
        if args.dry_run:
            print(f"WARNING: Destination path does not exist: {destination_path}", file=sys.stderr)
            print("WARNING: This is a dry run, so the directory will not be created", file=sys.stderr)
        else:
            print(f"Creating destination directory: {destination_path}")
            try:
                destination_path.mkdir(parents=True, exist_ok=True)
                print("Destination directory created successfully")
            except Exception as e:
                print(f"ERROR: Failed to create destination directory: {e}", file=sys.stderr)
                sys.exit(1)
    elif not destination_path.is_dir():
        print(f"ERROR: Destination path exists but is not a directory: {destination_path}", file=sys.stderr)
        sys.exit(1)

    # Check disk space
    if not args.dry_run:
        if not check_disk_space(destination_path):
            sys.exit(1)

    # Setup logging (after destination validation/creation)
    log_file_pattern = config.get('logging', {}).get('log_file_pattern', 'photo_organizer_%Y%m%d_%H%M%S.log')
    log_file = destination_path / datetime.now().strftime(log_file_pattern)

    if args.dry_run:
        log_file = None  # Don't create log file for dry runs

    setup_logging(log_file=log_file, verbose=args.verbose)

    logger.info("=" * 80)
    logger.info("Photo/Video Organizer Starting")
    logger.info("=" * 80)

    # Initialize location intelligence
    locationiq_key = args.locationiq_key or config.get('location', {}).get('locationiq_api_key')

    major_cities = set(config.get('location', {}).get('major_cities', []))
    national_parks = set(config.get('location', {}).get('national_parks', []))
    clustering_distance = config.get('location', {}).get('clustering_distance_miles', 25.0)

    cache = GeocodingCache()

    # Handle cache clearing
    if args.clear_cache:
        logger.info("Clearing entire geocoding cache...")
        cache.clear()
        logger.info("Cache cleared")

    # Handle retry-unknown
    if args.retry_unknown:
        logger.info("Removing 'Unknown' locations from cache...")
        removed = cache.clear_unknown()
        logger.info(f"Removed {removed} 'Unknown' entries from cache")

    cache_stats = cache.get_stats()
    logger.info(f"Geocoding cache: {cache_stats['total_entries']} entries")

    location_intelligence = LocationIntelligence(
        cache=cache,
        locationiq_api_key=locationiq_key if locationiq_key else None,
        major_cities=major_cities if major_cities else None,
        national_parks=national_parks if national_parks else None,
        clustering_distance_miles=clustering_distance
    )

    # Initialize organizer
    verify = not args.no_verify
    exclude_patterns = args.exclude or []
    filename_pattern = config.get('organization', {}).get('filename_pattern', '{date}_{original_name}{ext}')

    logger.info(f"Using filename pattern: {filename_pattern}")

    organizer = PhotoOrganizer(
        source_path=source_path,
        destination_path=destination_path,
        location_intelligence=location_intelligence,
        mode=args.mode,
        dry_run=args.dry_run,
        verify=verify,
        exclude_patterns=exclude_patterns,
        filename_pattern=filename_pattern
    )

    # Preview only mode
    if args.preview_only:
        organizer.print_preview(limit=args.preview_only)
        sys.exit(0)

    # Show preview and confirm
    require_confirmation = config.get('safety', {}).get('require_confirmation', True)
    if require_confirmation and not args.yes:
        if not confirm_operation(organizer, preview_count=10):
            print("\nOperation cancelled.")
            sys.exit(0)

    # Run organizer
    try:
        stats = organizer.organize()

        # Print summary
        stats.print_summary()

        # Exit code based on results
        if stats.failed_files > 0:
            logger.warning(f"Completed with {stats.failed_files} failures")
            sys.exit(2)
        else:
            logger.info("Organization completed successfully!")
            sys.exit(0)

    except KeyboardInterrupt:
        logger.warning("\nOperation interrupted by user")
        sys.exit(130)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

    finally:
        # Cleanup
        location_intelligence.close()


if __name__ == '__main__':
    main()
