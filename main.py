"""
Clipy for Windows — entry point.

Usage:
    python main.py

Or build an .exe:
    pip install pyinstaller
    pyinstaller --noconsole --onefile --icon=resources/icon.ico main.py
"""
import sys
import os

# Ensure src package is importable when running from project root
sys.path.insert(0, os.path.dirname(__file__))


def main():
    try:
        from src.app import ClipyApp
        app = ClipyApp()
        app.run()
    except Exception:
        import traceback
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            'Clipy Startup Error',
            f'Failed to start:\n\n{traceback.format_exc()}',
        )
        sys.exit(1)


if __name__ == '__main__':
    main()
