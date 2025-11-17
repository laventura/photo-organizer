"""
Tests for path generator with filename patterns.
"""
import pytest
from pathlib import Path
import tempfile
import shutil
from datetime import datetime

from src.path_generator import PathGenerator
from src.metadata import MediaMetadata


@pytest.fixture
def temp_dest_dir():
    """Create a temporary destination directory."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_metadata(tmp_path):
    """Create sample metadata for testing."""
    test_file = tmp_path / "IMG_1234.jpg"
    test_file.touch()

    metadata = MediaMetadata(test_file)
    metadata.date_taken = datetime(2023, 6, 15, 14, 30, 0)
    metadata.gps_coords = (37.7749, -122.4194)

    return metadata


def test_default_filename_pattern(temp_dest_dir, sample_metadata):
    """Test default filename pattern {date}_{original_name}{ext}."""
    generator = PathGenerator(temp_dest_dir)

    path = generator.generate_path(sample_metadata, "CA-San_Francisco")

    assert path.name == "2023-06-15_IMG_1234.jpg"
    assert "2023/06/CA-San_Francisco" in str(path)


def test_custom_pattern_year_month_day(temp_dest_dir, sample_metadata):
    """Test pattern with separate year, month, day."""
    generator = PathGenerator(temp_dest_dir, filename_pattern="{year}{month}{day}_{original_name}{ext}")

    path = generator.generate_path(sample_metadata, "CA")

    assert path.name == "20230615_IMG_1234.jpg"


def test_custom_pattern_original_first(temp_dest_dir, sample_metadata):
    """Test pattern with original name first."""
    generator = PathGenerator(temp_dest_dir, filename_pattern="{original_name}_{date}{ext}")

    path = generator.generate_path(sample_metadata, "CA")

    assert path.name == "IMG_1234_2023-06-15.jpg"


def test_custom_pattern_no_date(temp_dest_dir, sample_metadata):
    """Test pattern with only original name."""
    generator = PathGenerator(temp_dest_dir, filename_pattern="{original_name}{ext}")

    path = generator.generate_path(sample_metadata, "CA")

    assert path.name == "IMG_1234.jpg"


def test_custom_pattern_with_separators(temp_dest_dir, sample_metadata):
    """Test pattern with custom separators."""
    generator = PathGenerator(temp_dest_dir, filename_pattern="{year}-{month}-{day}_{original_name}{ext}")

    path = generator.generate_path(sample_metadata, "CA")

    assert path.name == "2023-06-15_IMG_1234.jpg"


def test_pattern_with_unknown_date(temp_dest_dir, tmp_path):
    """Test pattern when date is unknown."""
    test_file = tmp_path / "IMG_9999.jpg"
    test_file.touch()

    metadata = MediaMetadata(test_file)
    metadata.date_taken = None  # No date

    generator = PathGenerator(temp_dest_dir, filename_pattern="{date}_{original_name}{ext}")

    path = generator.generate_path(metadata, "Unknown")

    assert path.name == "Unknown_IMG_9999.jpg"
    assert "Unknown_Date/Unknown" in str(path)


def test_pattern_with_counter_placeholder(temp_dest_dir, sample_metadata):
    """Test pattern with {counter} placeholder for duplicates."""
    generator = PathGenerator(temp_dest_dir, filename_pattern="{date}_{original_name}{counter}{ext}")

    # Create initial file
    path1 = generator.generate_path(sample_metadata, "CA")
    path1.parent.mkdir(parents=True, exist_ok=True)
    path1.touch()

    # Create duplicate - should add counter
    path2 = generator.ensure_unique_path(path1, sample_metadata)

    assert path2.name == "2023-06-15_IMG_1234_1.jpg"

    # Create another duplicate
    path2.touch()
    path3 = generator.ensure_unique_path(path1, sample_metadata)

    assert path3.name == "2023-06-15_IMG_1234_2.jpg"


def test_ensure_unique_without_counter_placeholder(temp_dest_dir, sample_metadata):
    """Test duplicate handling without {counter} in pattern."""
    generator = PathGenerator(temp_dest_dir, filename_pattern="{date}_{original_name}{ext}")

    # Create initial file
    path1 = generator.generate_path(sample_metadata, "CA")
    path1.parent.mkdir(parents=True, exist_ok=True)
    path1.touch()

    # Create duplicate - should add _1 suffix
    path2 = generator.ensure_unique_path(path1)

    assert path2.name == "2023-06-15_IMG_1234_1.jpg"


def test_pattern_preserves_extension(temp_dest_dir, tmp_path):
    """Test that extension is preserved correctly."""
    for ext in ['.jpg', '.png', '.MP4', '.HEIC']:
        test_file = tmp_path / f"test{ext}"
        test_file.touch()

        metadata = MediaMetadata(test_file)
        metadata.date_taken = datetime(2023, 1, 1)

        generator = PathGenerator(temp_dest_dir, filename_pattern="{original_name}_{date}{ext}")

        path = generator.generate_path(metadata, "Test")

        assert path.suffix == ext
        assert path.name == f"test_2023-01-01{ext}"


def test_pattern_with_special_characters(temp_dest_dir, sample_metadata):
    """Test pattern with hyphens and underscores."""
    generator = PathGenerator(temp_dest_dir, filename_pattern="{year}-{month}-{day}--{original_name}{ext}")

    path = generator.generate_path(sample_metadata, "CA")

    assert path.name == "2023-06-15--IMG_1234.jpg"


def test_multiple_patterns(temp_dest_dir, sample_metadata):
    """Test generating paths with different patterns."""
    patterns = [
        ("{date}_{original_name}{ext}", "2023-06-15_IMG_1234.jpg"),
        ("{original_name}{ext}", "IMG_1234.jpg"),
        ("{year}{month}{day}_{original_name}{ext}", "20230615_IMG_1234.jpg"),
        ("{year}/{month}_{original_name}{ext}", "2023/06_IMG_1234.jpg"),  # Note: includes directory separator
    ]

    for pattern, expected_name in patterns:
        generator = PathGenerator(temp_dest_dir, filename_pattern=pattern)
        path = generator.generate_path(sample_metadata, "CA")

        assert path.name == expected_name or expected_name in str(path)
