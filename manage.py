#!/usr/bin/env python
"""Repository-root Django management entry point."""

import os
import sys

from deploy_bootstrap import bootstrap


def main() -> None:
    bootstrap()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "land_escrow.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
