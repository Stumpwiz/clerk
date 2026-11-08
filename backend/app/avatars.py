"""Bounded, metadata-free avatar normalization. No filesystem storage."""
from io import BytesIO

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_PIXELS = 16_000_000


def normalize_avatar(data: bytes) -> bytes:
    try:
        with Image.open(BytesIO(data), formats=["JPEG", "PNG", "WEBP"]) as source:
            if source.width * source.height > MAX_PIXELS:
                raise HTTPException(413, "Image exceeds 16 megapixels")
            if getattr(source, "is_animated", False):
                raise HTTPException(415, "Animated images are not supported")
            # Decoding alone can tolerate corrupt PNG chunk checksums. Verify
            # separately because verify() consumes the image's input stream.
            with Image.open(BytesIO(data), formats=["JPEG", "PNG", "WEBP"]) as check:
                check.verify()
            source.load()
            oriented = ImageOps.exif_transpose(source)
            thumbnail = ImageOps.fit(
                oriented.convert("RGBA"), (256, 256), method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )
            # A fresh image prevents EXIF, ICC, text and other metadata propagation.
            clean = Image.new("RGBA", (256, 256))
            clean.paste(thumbnail)
            output = BytesIO()
            clean.save(output, format="PNG")
            return output.getvalue()
    except Image.DecompressionBombError as exc:
        raise HTTPException(413, "Image exceeds pixel limit") from exc
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        raise HTTPException(415, "Invalid or unsupported image") from exc
