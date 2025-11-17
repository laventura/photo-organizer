# Setting Up Photo Organizer with `uv` and Python 3.13

## Quick Reference

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create project directory
mkdir photo-organizer
cd photo-organizer

# Initialize with Python 3.13
uv init --python 3.13

# Add dependencies
uv add pillow exiftool geopy pyyaml tqdm

# Run the script
uv run photo_organizer.py --help
```

---

## Step-by-Step Setup Guide

### Step 1: Install `uv` (if needed)

**On macOS:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Using Homebrew:**
```bash
brew install uv
```

**Verify installation:**
```bash
uv --version
# Should show: uv 0.x.x
```

---

### Step 2: Create Your Project

**Option A: New Directory**
```bash
# Create and navigate to project directory
mkdir ~/photo-organizer
cd ~/photo-organizer

# Initialize with Python 3.13
uv init --python 3.13
```

**Option B: Existing Directory**
```bash
# Navigate to your existing directory
cd ~/path/to/existing/project

# Initialize with Python 3.13
uv init --python 3.13
```

This creates:
- `.python-version` file (specifies Python 3.13)
- `pyproject.toml` (project configuration)
- `.venv/` directory (virtual environment)

---

### Step 3: Add Dependencies

Add all required packages with one command:

```bash
uv add pillow \
       pillow-heif \
       geopy \
       pyyaml \
       tqdm \
       requests
```

**What each package does:**
- `pillow` - Image processing and EXIF extraction
- `pillow-heif` - HEIC/HEIF image support (iPhone photos)
- `geopy` - Geocoding (reverse lookup GPS → location names)
- `pyyaml` - Configuration file parsing
- `tqdm` - Progress bars
- `requests` - HTTP requests for geocoding APIs

**Optional but recommended:**
```bash
# For better EXIF handling
uv add pyexiftool

# For video metadata
uv add mutagen
```

---

### Step 4: Verify Setup

**Check Python version:**
```bash
uv run python --version
# Should show: Python 3.13.x
```

**List installed packages:**
```bash
uv pip list
```

**Check dependencies in pyproject.toml:**
```bash
cat pyproject.toml
```

You should see something like:
```toml
[project]
name = "photo-organizer"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "pillow>=10.0.0",
    "pillow-heif>=0.13.0",
    "geopy>=2.4.0",
    "pyyaml>=6.0",
    "tqdm>=4.66.0",
    "requests>=2.31.0",
]
```

---

## Project Structure

After setup, your project should look like:

```
photo-organizer/
├── .python-version          # Python 3.13 specification
├── pyproject.toml           # Project config & dependencies
├── .venv/                   # Virtual environment (managed by uv)
├── photo_organizer.py       # Main script (to be created)
├── config.yaml              # Configuration file
├── README.md
└── tests/                   # Test files
```

---

## Running Your Script

**Method 1: Using `uv run` (recommended)**
```bash
# Run directly with uv
uv run photo_organizer.py --source ~/Pictures --destination ~/Organized --dry-run
```

**Method 2: Activate virtual environment**
```bash
# Activate the .venv
source .venv/bin/activate

# Run normally
python photo_organizer.py --source ~/Pictures --destination ~/Organized --dry-run

# Deactivate when done
deactivate
```

---

## Common `uv` Commands

### Dependency Management
```bash
# Add a package
uv add package-name

# Add a development dependency
uv add --dev pytest black ruff

# Remove a package
uv remove package-name

# Update all packages
uv sync --upgrade

# Show dependency tree
uv pip show pillow
```

### Environment Management
```bash
# Create/sync environment
uv sync

# Run a command in the environment
uv run python script.py

# Run a one-off command
uv run --with numpy python -c "import numpy; print(numpy.__version__)"
```

### Python Version Management
```bash
# List available Python versions
uv python list

# Install specific Python version
uv python install 3.13

# Use different Python version
uv python pin 3.12  # If dependencies require it
```

---

## Installing ExifTool (External Dependency)

`exiftool` is a powerful external tool for metadata extraction. Install it separately:

**On macOS:**
```bash
brew install exiftool
```

**Verify installation:**
```bash
exiftool -ver
# Should show version number
```

Then add the Python wrapper:
```bash
uv add pyexiftool
```

---

## Development Dependencies (Optional)

For development and testing:

```bash
# Add dev dependencies
uv add --dev pytest pytest-cov black ruff mypy

# Run tests
uv run pytest

# Format code
uv run black .

# Lint code
uv run ruff check .

# Type checking
uv run mypy photo_organizer.py
```

---

## Troubleshooting

### Issue: Python 3.13 not found

**Solution:**
```bash
# Install Python 3.13 via uv
uv python install 3.13

# Or use Homebrew
brew install python@3.13
```

### Issue: Package conflicts

**Solution:**
```bash
# Clear cache and reinstall
rm -rf .venv
uv sync --reinstall
```

### Issue: ExifTool not working

**Solution:**
```bash
# Check if exiftool is installed
which exiftool

# If not, install it
brew install exiftool
```

### Issue: HEIC images not loading

**Solution:**
```bash
# Ensure pillow-heif is installed
uv add pillow-heif

# On macOS, you might need libheif
brew install libheif
```

---

## Complete Setup Script

Here's a complete setup script you can copy-paste:

```bash
#!/bin/bash

# Photo Organizer Setup Script

echo "🚀 Setting up Photo Organizer with Python 3.13..."

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "📦 Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.cargo/env
fi

# Create project directory
echo "📁 Creating project directory..."
mkdir -p ~/photo-organizer
cd ~/photo-organizer

# Initialize with Python 3.13
echo "🐍 Initializing with Python 3.13..."
uv init --python 3.13

# Add dependencies
echo "📚 Installing dependencies..."
uv add pillow pillow-heif geopy pyyaml tqdm requests

# Install exiftool (macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
    if ! command -v exiftool &> /dev/null; then
        echo "🔧 Installing exiftool..."
        brew install exiftool
    fi
fi

# Add dev dependencies (optional)
echo "🛠️  Installing dev dependencies..."
uv add --dev pytest black ruff

# Verify setup
echo ""
echo "✅ Setup complete!"
echo ""
echo "Python version:"
uv run python --version
echo ""
echo "Installed packages:"
uv pip list
echo ""
echo "🎉 Ready to start coding! Next steps:"
echo "   cd ~/photo-organizer"
echo "   uv run python photo_organizer.py --help"
```

**Save and run:**
```bash
chmod +x setup.sh
./setup.sh
```

---

## Alternative: Using Requirements.txt

If you prefer traditional `requirements.txt`:

**Create requirements.txt:**
```txt
pillow>=10.0.0
pillow-heif>=0.13.0
geopy>=2.4.0
pyyaml>=6.0.0
tqdm>=4.66.0
requests>=2.31.0
pyexiftool>=0.5.0
mutagen>=1.47.0
```

**Install with uv:**
```bash
uv pip install -r requirements.txt
```

---

## Next Steps

1. ✅ Set up environment with `uv init --python 3.13`
2. ✅ Install dependencies with `uv add ...`
3. ⏭️ Create `photo_organizer.py` (main script)
4. ⏭️ Create `config.yaml` (configuration)
5. ⏭️ Test with small sample (10-100 files)
6. ⏭️ Run on full library

---

## Quick Reference Card

```bash
# Setup
uv init --python 3.13                    # Initialize project
uv add package                           # Add dependency
uv sync                                  # Install all dependencies

# Running
uv run python script.py                  # Run script
source .venv/bin/activate                # Activate venv manually

# Maintenance
uv sync --upgrade                        # Update all packages
uv remove package                        # Remove dependency
uv python pin 3.12                       # Change Python version

# Info
uv pip list                              # List packages
uv pip show package                      # Show package info
cat pyproject.toml                       # View project config
```

---

**Ready to code!** 🎉

Once you've run `uv init --python 3.13` and `uv add` commands, you're all set to start implementing the photo organizer!