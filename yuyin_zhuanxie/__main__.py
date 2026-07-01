import sys

from .cli import main

if __name__ == "__main__":
    if len(sys.argv) == 1:
        from .gui_modern import run_modern_gui

        run_modern_gui()
    else:
        main()
