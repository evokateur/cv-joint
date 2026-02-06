import argparse
from renderers.latex import render_cv, render_cover_letter


def main_cv():
    """CLI entry point for CV generation"""
    parser = argparse.ArgumentParser(description="Build CV from JSON/YAML data and LaTeX template")
    parser.add_argument("input_file", help="Path to input JSON or YAML file")
    parser.add_argument("output_file", help="Path to output LaTeX file")
    parser.add_argument("--template", default="cv.tex", help="Template file name (default: cv.tex)")

    args = parser.parse_args()
    render_cv(args.input_file, args.output_file, template_name=args.template)


def main_cover_letter():
    """CLI entry point for cover letter generation"""
    parser = argparse.ArgumentParser(description="Build cover letter from JSON/YAML data and LaTeX template")
    parser.add_argument("input_file", help="Path to input JSON or YAML file")
    parser.add_argument("output_file", help="Path to output LaTeX file")

    args = parser.parse_args()
    render_cover_letter(args.input_file, args.output_file)


if __name__ == "__main__":
    main_cv()
