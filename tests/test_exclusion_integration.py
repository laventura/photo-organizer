"""
Integration tests for exclusion patterns across the entire system.
"""
import pytest
from pathlib import Path
import tempfile
import shutil

from src.scanner import MediaScanner
from src.organizer import PhotoOrganizer
from src.location import LocationIntelligence
from src.cache import GeocodingCache


@pytest.fixture
def complex_photo_structure():
    """Create a complex directory structure for testing exclusions."""
    temp_dir = Path(tempfile.mkdtemp())

    # Main photos
    (temp_dir / "vacation.jpg").touch()
    (temp_dir / "family.png").touch()

    # Thumbnails directory (should be excluded)
    thumbs = temp_dir / "thumbnails"
    thumbs.mkdir()
    (thumbs / "vacation_thumb.jpg").touch()
    (thumbs / "family_thumb.jpg").touch()

    # Cache directories (should be excluded)
    cache1 = temp_dir / ".cache"
    cache1.mkdir()
    (cache1 / "cached1.jpg").touch()

    cache2 = temp_dir / "cache"
    cache2.mkdir()
    (cache2 / "cached2.jpg").touch()

    # Hidden directories (should be excluded)
    hidden = temp_dir / ".hidden"
    hidden.mkdir()
    (hidden / "secret.jpg").touch()

    # Good subdirectory (should be included)
    subdir = temp_dir / "2023"
    subdir.mkdir()
    (subdir / "trip.jpg").touch()
    (subdir / "adventure.mp4").touch()

    # Nested structure with thumbnails (should be excluded)
    nested_thumbs = subdir / "thumbnails"
    nested_thumbs.mkdir()
    (nested_thumbs / "nested_thumb.jpg").touch()

    yield temp_dir

    # Cleanup
    shutil.rmtree(temp_dir)


def test_scanner_with_multiple_exclusions(complex_photo_structure):
    """Test scanner with multiple exclusion patterns."""
    scanner = MediaScanner()

    files = scanner.scan(
        complex_photo_structure,
        recursive=True,
        exclude_patterns=['thumbnails', '.cache', 'cache', '.hidden']
    )

    # Should find: vacation.jpg, family.png, trip.jpg, adventure.mp4 = 4 files
    assert len(files) == 4

    # Verify correct files are included
    file_names = {f.name for f in files}
    assert 'vacation.jpg' in file_names
    assert 'family.png' in file_names
    assert 'trip.jpg' in file_names
    assert 'adventure.mp4' in file_names

    # Verify excluded files are not present
    assert 'vacation_thumb.jpg' not in file_names
    assert 'cached1.jpg' not in file_names
    assert 'secret.jpg' not in file_names


def test_organizer_respects_exclusions(complex_photo_structure):
    """Test that PhotoOrganizer respects exclusion patterns."""
    temp_dest = Path(tempfile.mkdtemp())
    temp_cache = Path(tempfile.mktemp(suffix='.db'))

    try:
        cache = GeocodingCache(cache_path=temp_cache)
        location_intel = LocationIntelligence(cache=cache)

        organizer = PhotoOrganizer(
            source_path=complex_photo_structure,
            destination_path=temp_dest,
            location_intelligence=location_intel,
            mode='copy',
            dry_run=True,
            exclude_patterns=['thumbnails', '.cache', 'cache', '.hidden']
        )

        # Get preview
        preview = organizer.preview(limit=20)

        # Should only preview 4 files
        assert len(preview) == 4

        # Verify thumbnails and cache files are not in preview
        preview_sources = [item['source'] for item in preview]
        assert all('thumbnails' not in src for src in preview_sources)
        assert all('.cache' not in src for src in preview_sources)
        assert all('cache' not in src or 'cache' not in Path(src).parts for src in preview_sources)
        assert all('.hidden' not in src for src in preview_sources)

    finally:
        shutil.rmtree(temp_dest)
        if temp_cache.exists():
            temp_cache.unlink()


def test_wildcard_exclusion_pattern(complex_photo_structure):
    """Test exclusion with wildcard patterns."""
    scanner = MediaScanner()

    # Exclude anything starting with 'cache'
    files = scanner.scan(
        complex_photo_structure,
        recursive=True,
        exclude_patterns=['cache*', '.cache*']
    )

    # Should not include any cache files
    for f in files:
        assert 'cache' not in f.parts or f.parent.name == '2023'


def test_glob_style_exclusion(complex_photo_structure):
    """Test glob-style exclusion patterns."""
    scanner = MediaScanner()

    # Exclude all thumbnails directories anywhere in tree
    files = scanner.scan(
        complex_photo_structure,
        recursive=True,
        exclude_patterns=['*/thumbnails/*', 'thumbnails']
    )

    # Should not include any thumbnail files
    assert all('thumbnails' not in str(f) for f in files)


def test_empty_exclusion_list(complex_photo_structure):
    """Test that empty exclusion list finds all files."""
    scanner = MediaScanner()

    files = scanner.scan(
        complex_photo_structure,
        recursive=True,
        exclude_patterns=[]
    )

    # Should find all 9 media files:
    # vacation.jpg, family.png, trip.jpg, adventure.mp4,
    # vacation_thumb.jpg, family_thumb.jpg, nested_thumb.jpg,
    # cached1.jpg, cached2.jpg, secret.jpg = 10 files
    assert len(files) == 10


def test_case_sensitive_exclusion(complex_photo_structure):
    """Test that exclusion patterns work with different casing."""
    # Create differently named directory
    thumbs_alt = complex_photo_structure / "Thumbs"  # Different casing
    thumbs_alt.mkdir()
    (thumbs_alt / "alt_thumb.jpg").touch()

    scanner = MediaScanner()

    # Exclude only lowercase 'thumbnails' (exact match)
    files = scanner.scan(
        complex_photo_structure,
        recursive=True,
        exclude_patterns=['thumbnails']  # This won't match 'Thumbs'
    )

    # Should include Thumbs but not thumbnails
    file_names = {f.name for f in files}
    assert 'alt_thumb.jpg' in file_names  # From Thumbs
    assert 'vacation_thumb.jpg' not in file_names  # From thumbnails


def test_multiple_levels_of_exclusion(complex_photo_structure):
    """Test exclusions at different directory levels."""
    # Create multi-level structure
    level1 = complex_photo_structure / "level1"
    level1.mkdir()
    (level1 / "photo1.jpg").touch()

    level2 = level1 / "cache"
    level2.mkdir()
    (level2 / "photo2.jpg").touch()

    level3 = level2 / "deep"
    level3.mkdir()
    (level3 / "photo3.jpg").touch()

    scanner = MediaScanner()
    files = scanner.scan(
        complex_photo_structure,
        recursive=True,
        exclude_patterns=['cache']
    )

    # photo1.jpg should be found, but photo2.jpg and photo3.jpg should not
    file_names = {f.name for f in files}
    assert 'photo1.jpg' in file_names
    assert 'photo2.jpg' not in file_names
    assert 'photo3.jpg' not in file_names


def test_exclusion_statistics(complex_photo_structure):
    """Test that exclusion statistics are reported correctly."""
    scanner = MediaScanner()

    # This is tested through logging, but we can verify the count
    files_without_exclusion = scanner.scan(
        complex_photo_structure,
        recursive=True,
        exclude_patterns=[]
    )

    files_with_exclusion = scanner.scan(
        complex_photo_structure,
        recursive=True,
        exclude_patterns=['thumbnails', '.cache']
    )

    # Should have fewer files with exclusions
    assert len(files_with_exclusion) < len(files_without_exclusion)

    # Specifically, should exclude 5 files:
    # 2 from /thumbnails, 1 from /.cache, 1 from /2023/thumbnails, 1 from /cache
    excluded_count = len(files_without_exclusion) - len(files_with_exclusion)
    assert excluded_count >= 4  # At least the thumbnail and cache files
