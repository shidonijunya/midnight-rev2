"""Image and animated GIF uploads for chat using the existing image bucket.

Supabase's existing bucket may only allow PNG/JPEG/WebP; animated GIFs are
converted to animated WebP without requiring a database or bucket migration.
"""
from io import BytesIO
from uuid import uuid4
from PIL import Image, ImageSequence, UnidentifiedImageError
from shared_backend import upload_asset

MAX_UPLOAD = 10 * 1024 * 1024
MAX_PIXELS = 40_000_000


def _animated_webp(raw):
    with Image.open(BytesIO(raw)) as im:
        if im.width * im.height > MAX_PIXELS:
            raise ValueError("Imagem grande demais.")
        frames, durations = [], []
        for i, frame in enumerate(ImageSequence.Iterator(im)):
            if i >= 180:
                break
            picture = frame.convert("RGBA")
            picture.thumbnail((560, 560), Image.Resampling.LANCZOS)
            frames.append(picture.copy())
            durations.append(max(25, int(frame.info.get("duration", 100))))
        if not frames:
            raise ValueError("GIF sem quadros.")
        output = BytesIO()
        frames[0].save(output, format="WEBP", save_all=True,
                       append_images=frames[1:],
                       duration=durations, loop=0, quality=72, method=3)
        data = output.getvalue()
        if len(data) > MAX_UPLOAD:
            raise ValueError("GIF convertido acima de 10 MB. Escolha um GIF menor.")
        return data


def upload_chat_file(file):
    data = file.getvalue()
    if not data or len(data) > MAX_UPLOAD:
        raise ValueError("Arquivo vazio ou acima de 10 MB.")
    name = str(file.name).lower()
    mime = str(file.type or "").lower()
    if name.endswith(".gif") or mime == "image/gif":
        try:
            data = _animated_webp(data)
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError("GIF inválido.") from exc
        extension, mime = "webp", "image/webp"
    elif mime in ("image/png", "image/jpeg", "image/webp"):
        extension = "jpg" if mime == "image/jpeg" else mime.rsplit("/", 1)[1]
    else:
        raise ValueError("Use PNG, JPG, WebP ou GIF.")
    return upload_asset(f"chat/{uuid4().hex}.{extension}", data, mime)
