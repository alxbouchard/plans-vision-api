#!/usr/bin/env python3
"""Generate synthetic test fixture images.

This script creates simple PNG images that simulate construction plan pages
for testing purposes. Real fixtures should be manually curated from
actual anonymized plans.

Usage:
    python testdata/generate_fixtures.py
"""

from pathlib import Path
from PIL import Image, ImageDraw

# Output directory
OUTPUT_DIR = Path(__file__).parent


def create_consistent_pages():
    """Create 3 pages with consistent visual conventions."""
    output_dir = OUTPUT_DIR / "consistent_set"
    output_dir.mkdir(exist_ok=True)

    for i in range(1, 4):
        # Create white image
        img = Image.new("RGB", (800, 600), "white")
        draw = ImageDraw.Draw(img)

        # Draw consistent conventions:
        # - Thick black border (structural walls)
        draw.rectangle([50, 50, 750, 550], outline="black", width=3)

        # - Thin gray internal walls
        draw.line([400, 50, 400, 550], fill="gray", width=1)
        draw.line([50, 300, 750, 300], fill="gray", width=1)

        # - Quarter-circle door swing (consistent convention)
        draw.arc([360, 260, 440, 340], 0, 90, fill="black", width=1)

        # - Parallel lines for windows
        draw.line([600, 50, 700, 50], fill="black", width=2)
        draw.line([600, 60, 700, 60], fill="black", width=2)

        # Add page number
        draw.text((720, 520), f"Page {i}", fill="black")

        # Save
        img.save(output_dir / f"page{i}.png", "PNG")
        print(f"Created: {output_dir / f'page{i}.png'}")


def create_contradiction_pages():
    """Create 2 pages with contradicting visual conventions."""
    output_dir = OUTPUT_DIR / "contradiction_set"
    output_dir.mkdir(exist_ok=True)

    # Page 1: Door shown as quarter-circle swing
    img1 = Image.new("RGB", (800, 600), "white")
    draw1 = ImageDraw.Draw(img1)
    draw1.rectangle([50, 50, 750, 550], outline="black", width=3)
    draw1.line([400, 50, 400, 550], fill="gray", width=1)
    # Quarter-circle door swing
    draw1.arc([360, 260, 440, 340], 0, 90, fill="black", width=1)
    draw1.text((720, 520), "Page 1", fill="black")
    img1.save(output_dir / "page1.png", "PNG")
    print(f"Created: {output_dir / 'page1.png'}")

    # Page 2: Door shown as rectangular cutout (CONTRADICTION)
    img2 = Image.new("RGB", (800, 600), "white")
    draw2 = ImageDraw.Draw(img2)
    draw2.rectangle([50, 50, 750, 550], outline="black", width=3)
    draw2.line([400, 50, 400, 550], fill="gray", width=1)
    # Rectangular door cutout (different convention)
    draw2.rectangle([380, 280, 420, 320], fill="white", outline="black", width=1)
    draw2.text((720, 520), "Page 2", fill="black")
    img2.save(output_dir / "page2.png", "PNG")
    print(f"Created: {output_dir / 'page2.png'}")


def create_synthetic_images():
    """Create simple synthetic test images."""
    output_dir = OUTPUT_DIR / "synthetic"
    output_dir.mkdir(exist_ok=True)

    # Create a minimal valid PNG for tests
    img = Image.new("RGB", (100, 100), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, 90, 90], outline="black", width=2)
    draw.text((30, 40), "TEST", fill="black")
    img.save(output_dir / "minimal.png", "PNG")
    print(f"Created: {output_dir / 'minimal.png'}")

    # Create a larger test image
    img_large = Image.new("RGB", (1000, 1000), "white")
    draw_large = ImageDraw.Draw(img_large)
    for x in range(0, 1000, 100):
        draw_large.line([(x, 0), (x, 1000)], fill="lightgray", width=1)
    for y in range(0, 1000, 100):
        draw_large.line([(0, y), (1000, y)], fill="lightgray", width=1)
    draw_large.rectangle([100, 100, 900, 900], outline="black", width=3)
    img_large.save(output_dir / "large.png", "PNG")
    print(f"Created: {output_dir / 'large.png'}")


if __name__ == "__main__":
    print("Generating test fixtures...")
    create_consistent_pages()
    create_contradiction_pages()
    create_synthetic_images()
    print("\nDone! Test fixtures created.")
