"""
Utility functions for logging, statistics, and helpers.
"""
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import logging
import json
import hashlib


def setup_logging(log_file: Path = None, verbose: bool = False) -> logging.Logger:
    """
    Setup logging configuration.

    Args:
        log_file: Path to log file (optional)
        verbose: If True, set DEBUG level; otherwise INFO

    Returns:
        Configured logger
    """
    level = logging.DEBUG if verbose else logging.INFO

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)  # Always log everything to file
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    return root_logger


class Statistics:
    """Track and display execution statistics."""

    def __init__(self):
        self.start_time = datetime.now()
        self.total_files = 0
        self.processed_files = 0
        self.skipped_files = 0
        self.failed_files = 0
        self.files_with_gps = 0
        self.files_without_gps = 0
        self.files_with_date = 0
        self.files_without_date = 0
        self.unique_locations: set = set()
        self.duplicates_found = 0
        self.api_calls_made = 0
        self.cache_hits = 0
        self.errors: List[str] = []

    def record_processed(self):
        """Record a successfully processed file."""
        self.processed_files += 1

    def record_skipped(self):
        """Record a skipped file."""
        self.skipped_files += 1

    def record_failed(self, error_msg: str = None):
        """Record a failed file."""
        self.failed_files += 1
        if error_msg:
            self.errors.append(error_msg)

    def record_gps(self, has_gps: bool):
        """Record GPS availability."""
        if has_gps:
            self.files_with_gps += 1
        else:
            self.files_without_gps += 1

    def record_date(self, has_date: bool):
        """Record date metadata availability."""
        if has_date:
            self.files_with_date += 1
        else:
            self.files_without_date += 1

    def record_location(self, location: str):
        """Record unique location."""
        self.unique_locations.add(location)

    def record_duplicate(self):
        """Record a duplicate file."""
        self.duplicates_found += 1

    def record_api_call(self):
        """Record an API call."""
        self.api_calls_made += 1

    def record_cache_hit(self):
        """Record a cache hit."""
        self.cache_hits += 1

    def get_summary(self) -> Dict:
        """
        Get statistics summary.

        Returns:
            Dictionary with all statistics
        """
        elapsed = datetime.now() - self.start_time
        elapsed_seconds = elapsed.total_seconds()

        files_per_second = self.processed_files / elapsed_seconds if elapsed_seconds > 0 else 0

        return {
            'total_files': self.total_files,
            'processed': self.processed_files,
            'skipped': self.skipped_files,
            'failed': self.failed_files,
            'files_with_gps': self.files_with_gps,
            'files_without_gps': self.files_without_gps,
            'files_with_date': self.files_with_date,
            'files_without_date': self.files_without_date,
            'unique_locations': len(self.unique_locations),
            'duplicates': self.duplicates_found,
            'api_calls': self.api_calls_made,
            'cache_hits': self.cache_hits,
            'elapsed_seconds': elapsed_seconds,
            'files_per_second': files_per_second,
            'errors': self.errors
        }

    def print_summary(self):
        """Print formatted statistics summary."""
        summary = self.get_summary()

        print("\n" + "=" * 60)
        print("EXECUTION SUMMARY")
        print("=" * 60)

        print(f"\n📁 Total Files: {summary['total_files']}")
        print(f"   ✓ Processed: {summary['processed']}")
        print(f"   ⊘ Skipped: {summary['skipped']}")
        print(f"   ✗ Failed: {summary['failed']}")

        print(f"\n📍 Location Statistics:")
        print(f"   With GPS: {summary['files_with_gps']}")
        print(f"   Without GPS: {summary['files_without_gps']}")
        print(f"   Unique Locations: {summary['unique_locations']}")

        print(f"\n📅 Date Statistics:")
        print(f"   With Date Metadata: {summary['files_with_date']}")
        print(f"   Without Date: {summary['files_without_date']}")

        if summary['duplicates'] > 0:
            print(f"\n🔄 Duplicates Found: {summary['duplicates']}")

        print(f"\n⏱️  Performance:")
        print(f"   Total Time: {summary['elapsed_seconds']:.1f} seconds")
        print(f"   Speed: {summary['files_per_second']:.1f} files/second")
        print(f"   API Calls: {summary['api_calls']}")
        print(f"   Cache Hits: {summary['cache_hits']}")

        if summary['errors']:
            print(f"\n⚠️  Errors ({len(summary['errors'])}):")
            for error in summary['errors'][:5]:  # Show first 5 errors
                print(f"   - {error}")
            if len(summary['errors']) > 5:
                print(f"   ... and {len(summary['errors']) - 5} more")

        print("\n" + "=" * 60 + "\n")


class TransactionLog:
    """Log file operations for potential rollback."""

    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.transactions: List[Dict] = []

    def log_operation(self, operation: str, source: Path, destination: Path,
                     success: bool, error: str = None):
        """
        Log a file operation.

        Args:
            operation: Type of operation ('move', 'copy')
            source: Source file path
            destination: Destination file path
            success: Whether operation succeeded
            error: Error message if failed
        """
        transaction = {
            'timestamp': datetime.now().isoformat(),
            'operation': operation,
            'source': str(source),
            'destination': str(destination),
            'success': success,
            'error': error
        }
        self.transactions.append(transaction)

    def save(self):
        """Save transaction log to file."""
        try:
            with open(self.log_file, 'w') as f:
                json.dump(self.transactions, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save transaction log: {e}")

    def load(self) -> List[Dict]:
        """Load transaction log from file."""
        try:
            if self.log_file.exists():
                with open(self.log_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logging.error(f"Failed to load transaction log: {e}")
        return []


def calculate_file_hash(file_path: Path, algorithm: str = 'sha256') -> str:
    """
    Calculate hash of a file.

    Args:
        file_path: Path to file
        algorithm: Hash algorithm ('md5', 'sha1', 'sha256')

    Returns:
        Hex digest of file hash
    """
    hash_obj = hashlib.new(algorithm)

    with open(file_path, 'rb') as f:
        # Read in chunks for large files
        for chunk in iter(lambda: f.read(8192), b''):
            hash_obj.update(chunk)

    return hash_obj.hexdigest()


def verify_file_integrity(source: Path, destination: Path) -> bool:
    """
    Verify that two files are identical.

    Args:
        source: Source file path
        destination: Destination file path

    Returns:
        True if files are identical
    """
    if not source.exists() or not destination.exists():
        return False

    # Quick check: file sizes
    if source.stat().st_size != destination.stat().st_size:
        return False

    # Full verification: hash comparison
    source_hash = calculate_file_hash(source)
    dest_hash = calculate_file_hash(destination)

    return source_hash == dest_hash


def format_bytes(bytes_value: int) -> str:
    """
    Format bytes into human-readable string.

    Args:
        bytes_value: Size in bytes

    Returns:
        Formatted string (e.g., "1.5 GB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"


def get_disk_space(path: Path) -> Dict[str, int]:
    """
    Get disk space information for a path.

    Args:
        path: Path to check

    Returns:
        Dictionary with 'total', 'used', 'free' in bytes
    """
    import shutil
    stat = shutil.disk_usage(path)

    return {
        'total': stat.total,
        'used': stat.used,
        'free': stat.free
    }
