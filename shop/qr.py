"""QR-код для музыкальной открытки. Использует пакет segno (он есть в requirements.txt);
если пакета нет, возвращает None — страница печати просто покажет название песни."""
import re
from urllib.parse import quote


def song_link(note):
    """Что зашифровать в QR: ссылка, которую ввёл клиент, или поиск песни в Яндекс Музыке по названию."""
    note = (note or '').strip()
    if note.lower().startswith(('http://', 'https://')):
        return note
    return f'https://music.yandex.ru/search?text={quote(note)}' if note else ''


def qr_svg(data, scale=8):
    """SVG с QR-кодом, который масштабируется под любой размер (размер задаётся стилем страницы)."""
    if not data:
        return None
    try:
        import segno
    except ImportError:
        return None
    svg = segno.make(data, error='m').svg_inline(scale=scale, border=1, dark='#243326', light=None)
    return re.sub(r'<svg width="(\d+)" height="(\d+)"', r'<svg viewBox="0 0 \1 \2"', svg, count=1)
