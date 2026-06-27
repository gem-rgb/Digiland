#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path


def _reexec_with_local_venv():
    """
    Prefer the project-local virtual environment when the command is launched
    with the system Python by mistake.

    This avoids mixing packages from different Python builds. The project venv
    includes compiled wheels, so reusing the wrong interpreter can break imports
    such as Pillow even if ``site-packages`` is added to ``sys.path``.
    """
    project_root = Path(__file__).resolve().parent.parent
    venv_dir = project_root / 'venv'
    if not venv_dir.exists():
        return

    candidate_interpreters = [
        venv_dir / 'Scripts' / 'python.exe',
        venv_dir / 'bin' / 'python',
    ]
    for interpreter in candidate_interpreters:
        if interpreter.exists():
            current = Path(sys.executable).resolve()
            target = interpreter.resolve()
            if current != target:
                os.execv(str(target), [str(target), *sys.argv])
            break


def main():
    """Run administrative tasks."""
    _reexec_with_local_venv()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'land_escrow.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
