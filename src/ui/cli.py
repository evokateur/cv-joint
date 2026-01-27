"""
CLI entry point for the Gradio UI.
"""

import argparse
import sys

import yaml


def main():
    """Launch the Gradio UI or show config."""
    parser = argparse.ArgumentParser(description="CV Joint application")
    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Print merged configuration to stdout and exit",
    )
    args = parser.parse_args()

    if args.show_config:
        from config.settings import get_merged_config

        config = get_merged_config()
        yaml.dump(config, sys.stdout, default_flow_style=False, sort_keys=False)
        return

    from ui.app import launch

    launch()


if __name__ == "__main__":
    main()
