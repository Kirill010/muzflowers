#!/usr/bin/env python
import os
import sys


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'muzflowers.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError('Django не установлен. Запустите start.bat (Windows) или start.sh (Mac/Linux).') from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
