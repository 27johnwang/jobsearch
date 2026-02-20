#!/usr/bin/env python3
"""Entry point to run the scraper and generate README."""

import sys
from scraper.main import run as run_scraper
from scraper.readme_generator import run as run_readme


def main():
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "scrape":
            run_scraper()
        elif command == "readme":
            run_readme()
        elif command == "all":
            run_scraper()
            run_readme()
        else:
            print(f"Unknown command: {command}")
            print("Usage: python run.py [scrape|readme|all]")
            sys.exit(1)
    else:
        # Default: run everything
        run_scraper()
        run_readme()


if __name__ == "__main__":
    main()
