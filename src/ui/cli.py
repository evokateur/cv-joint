"""
CLI entry point for the Gradio UI.
"""


def main():
    """Launch the Gradio UI."""
    from ui.gradio_app import launch

    launch()


if __name__ == "__main__":
    main()
