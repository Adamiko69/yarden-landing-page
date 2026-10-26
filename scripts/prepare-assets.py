"""Extract and optimize the supplied artwork without generating or retouching it.

Desktop delivery is pixel-identical (lossless WebP). Mobile uses a face-safe
crop from the same artwork. Run after explicitly replacing assets/reference.png.
"""

from pathlib import Path
from PIL import Image, ImageOps

ASSETS = Path(__file__).resolve().parents[1] / "assets"
with Image.open(ASSETS / "reference.png") as source:
    source.load()
    if source.size != (1024, 1536):
        raise ValueError("This extraction is specific to the approved 1024 × 1536 design.")
    source = source.convert("RGB")
    source.save(ASSETS / "design.webp", lossless=True, method=6)
    portrait = source.crop((0, 0, 584, 652))
    portrait.save(ASSETS / "portrait.webp", lossless=True, method=6)
    portrait.resize((390, 435), Image.Resampling.LANCZOS).save(
        ASSETS / "portrait-390.webp", lossless=True, method=6
    )
    source.crop((0, 652, 164, 988)).save(ASSETS / "leaves.webp", lossless=True, method=6)
    # Preserve the original display typography on narrow screens as well.
    source.crop((738, 25, 982, 99)).save(ASSETS / "identity.webp", lossless=True, method=6)
    source.crop((628, 234, 980, 264)).save(ASSETS / "eyebrow.webp", lossless=True, method=6)
    source.crop((588, 264, 1000, 366)).save(ASSETS / "headline.webp", lossless=True, method=6)
    source.crop((651, 373, 943, 406)).save(ASSETS / "tagline.webp", lossless=True, method=6)
    source.crop((658, 442, 965, 512)).save(ASSETS / "consultation.webp", lossless=True, method=6)
    source.crop((335, 690, 709, 744)).save(ASSETS / "about-title.webp", lossless=True, method=6)
    source.crop((409, 1127, 617, 1179)).save(ASSETS / "contact-title.webp", lossless=True, method=6)
    # Fit the complete portrait: no face cropping and no added text.
    preview = Image.new("RGB", (1200, 630), source.getpixel((1000, 100)))
    fitted = ImageOps.contain(portrait, preview.size, Image.Resampling.LANCZOS)
    preview.paste(fitted, ((1200 - fitted.width) // 2, (630 - fitted.height) // 2))
    preview.save(ASSETS / "social-preview.jpg", quality=94, optimize=True, progressive=True)

for name in ("design.webp", "portrait.webp", "portrait-390.webp", "leaves.webp", "identity.webp", "eyebrow.webp", "headline.webp", "tagline.webp", "consultation.webp", "about-title.webp", "contact-title.webp", "social-preview.jpg"):
    print(f"{name}: {(ASSETS / name).stat().st_size:,} bytes")
