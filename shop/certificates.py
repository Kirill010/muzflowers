import re

ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'


def normalize_certificate_code(raw):
    value = re.sub(r'[\s\-_]', '', str(raw or '').upper())
    if len(value) != 12 or any(char not in ALPHABET for char in value):
        return ''
    return f'{value[:4]}-{value[4:8]}-{value[8:]}'
