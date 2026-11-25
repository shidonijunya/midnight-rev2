"""Unified image editor for character portraits, scenes and bosses."""
from io import BytesIO
from uuid import uuid4

import streamlit as st
from PIL import Image, ImageOps, UnidentifiedImageError

from shared_backend import upload_asset

SIZES = {"portrait": (600, 750), "boss": (1200, 900), "scene": (1600, 900), "token": (768, 768)}
MAX_BYTES = 10 * 1024 * 1024


def prepare_image(raw, kind, focus=(0.5, 0.5)):
    if kind not in SIZES:
        raise ValueError("Categoria de imagem inválida.")
    if len(raw) > MAX_BYTES:
        raise ValueError("O arquivo ultrapassa 10 MB.")
    try:
        with Image.open(BytesIO(raw)) as src:
            if src.width * src.height > 40_000_000:
                raise ValueError("Imagem muito grande.")
            rgb = ImageOps.exif_transpose(src).convert("RGBA" if kind in ("token", "scene") else "RGB")
            if kind == "scene":
                output = BytesIO()
                rgb.save(output, format="WEBP", lossless=True, method=4)
            elif kind == "token":
                # Preserve transparent edges and native detail, never upscale.
                # Older 256px token conversions blurred fine lines unnecessarily.
                rgb.thumbnail(SIZES[kind], Image.Resampling.LANCZOS)
                output = BytesIO()
                rgb.save(output, format="WEBP", lossless=True, method=6)
            else:
                cropped = ImageOps.fit(
                    rgb, SIZES[kind], method=Image.Resampling.LANCZOS,
                    centering=focus,
                )
                output = BytesIO()
                cropped.save(output, format="WEBP", quality=88, method=6)
            return output.getvalue()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Imagem inválida ou danificada.") from exc


def render_image_editor(kind, owner_id, current_url="", key="portrait"):
    """Returns the updated public URL only after a successful upload."""
    if current_url:
        st.image(current_url, caption="Imagem atual", width=210)
    file = st.file_uploader("Selecionar imagem", type=["png", "jpg", "jpeg", "webp"],
                            key=f"{key}_file")
    if not file:
        return current_url
    horizontal = vertical = 50
    if kind != "scene":
        h, v = st.columns(2)
        horizontal = h.slider("Enquadramento horizontal", 0, 100, 50, key=f"{key}_horizontal")
        vertical = v.slider("Enquadramento vertical", 0, 100, 50, key=f"{key}_vertical")
    try:
        edited = prepare_image(file.getvalue(), kind,
                               (horizontal / 100, vertical / 100))
    except ValueError as exc:
        st.error(str(exc))
        return current_url
    st.image(edited, caption="Prévia")
    if st.button("Salvar imagem", key=f"{key}_save", type="primary"):
        folder = {"portrait": f"players/{owner_id}", "token": f"players/{owner_id}", "boss": f"bosses/{owner_id}", "scene": f"scenes/{owner_id}"}[kind]
        path = f"{folder}/{uuid4().hex}.webp"
        url = upload_asset(path, edited, "image/webp")
        if url:
            st.success("Imagem atualizada.")
            return url
        st.error("Falha ao salvar a imagem.")
    return current_url


def upload_map_background(file):
    """Keep entire image: cropping and stretching happen in the browser editor."""
    if file is None:
        return None
    raw = file.getvalue()
    if len(raw) > MAX_BYTES:
        raise ValueError("O mapa deve ter no máximo 10 MB.")
    try:
        with Image.open(BytesIO(raw)) as image:
            if image.width * image.height > 40_000_000:
                raise ValueError("Mapa muito grande.")
            formats = {"JPEG": ("jpg", "image/jpeg"), "PNG": ("png", "image/png"), "WEBP": ("webp", "image/webp")}
            if image.format not in formats:
                raise ValueError("Formato de mapa inválido.")
            ext, mime = formats[image.format]
            image.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Imagem de mapa inválida.") from exc
    return upload_asset(f"scenes/maps/{uuid4().hex}.{ext}", raw, mime)
