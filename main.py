"""
BeamNG Info Config Generator
Run: python main.py
     python main.py --mods-path "C:/path/to/mods"
"""
import sys
import argparse


def main():
    parser = argparse.ArgumentParser(description="BeamNG Info Config Generator")
    parser.add_argument("--mods-path", metavar="PATH",
                        help="Mods folder to scan on startup")
    args = parser.parse_args()

    try:
        import PySide6  # noqa: F401
    except ImportError:
        print("PySide6 not found. Run:  pip install PySide6")
        sys.exit(1)

    from PySide6.QtWidgets import QApplication
    from app import App, make_dark_style

    app = QApplication(sys.argv)
    app.setStyleSheet(make_dark_style())

    window = App(mods_path=args.mods_path)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
