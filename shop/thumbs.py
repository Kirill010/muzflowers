"""Фото букетов. Снимки с телефона весят по 5–10 МБ, а на странице нужны 400–1200 пикселей:
при загрузке уменьшаем оригинал и поворачиваем как надо, а для страниц делаем маленькие копии в WebP."""
import hashlib
import io
import os
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

MAX_UPLOAD_MB = 20
MAX_SIDE = 2400


def validate_image_size(image):
    if image.size > MAX_UPLOAD_MB * 1024 * 1024:
        raise ValidationError(f'Фото слишком большое (больше {MAX_UPLOAD_MB} МБ). Уменьшите его и загрузите снова.')


def process_upload(file):
    """Поворачивает фото по метке телефона и уменьшает до 2400 px. Возвращает файл для сохранения."""
    try:
        file.seek(0)
        with Image.open(file) as im:
            im = ImageOps.exif_transpose(im)
            has_alpha = im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info)
            if max(im.size) > MAX_SIDE:
                im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
            out = io.BytesIO()
            stem = Path(file.name).stem
            if has_alpha:
                im.convert('RGBA').save(out, 'PNG', optimize=True)
                name = f'{stem}.png'
            else:
                im.convert('RGB').save(out, 'JPEG', quality=88, optimize=True, progressive=True)
                name = f'{stem}.jpg'
        return ContentFile(out.getvalue(), name=name)
    except Exception:  # непонятный файл — пусть Django сохранит как есть
        file.seek(0)
        return file


def thumb_url(image_field, width):
    """Адрес копии шириной `width` px. Если что-то пошло не так — отдаём оригинал."""
    try:
        src = Path(image_field.path)
        key = hashlib.md5(f'{image_field.name}:{int(src.stat().st_mtime)}:{width}'.encode()).hexdigest()[:16]
        rel = f'thumbs/{key}-{width}.webp'
        dst = Path(settings.MEDIA_ROOT) / rel
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(src) as im:
                im = ImageOps.exif_transpose(im)
                if im.width > width:
                    im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
                tmp = dst.with_suffix('.tmp')
                im.convert('RGBA' if im.mode in ('RGBA', 'LA') else 'RGB').save(tmp, 'WEBP', quality=82, method=4)
            os.replace(tmp, dst)  # атомарно: два одновременных запроса не испортят файл
        return settings.MEDIA_URL + rel
    except Exception:
        try:
            return image_field.url
        except Exception:
            return ''
