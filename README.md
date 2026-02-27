# Clipy for Windows

> A Windows clipboard manager inspired by the macOS [Clipy](https://github.com/Clipy/Clipy) app.

## Features

| Feature | Description |
|---------|-------------|
| **Clipboard History** | Automatically saves copied text (up to 100 items) |
| **Snippet Management** | Organize frequently used text in folders |
| **Custom Shortcuts** | Freely configure hotkeys (default: `Ctrl+Shift+V`) |
| **Incremental Search** | Real-time filtering within the popup |
| **System Tray Resident** | Runs in background, accessible via right-click menu |
| **Dark / Light Theme** | Switch themes to your preference |

## Installation

### Prerequisites

- Python 3.10+
- pip

```bash
pip install -r requirements.txt
```

### Running

```bash
python main.py
```

### Building .exe

```bat
build.bat
```
This generates `dist\Clipy.exe`.

## Usage

1. Run `python main.py` to start the app in the system tray.
2. Press `Ctrl+Shift+V` to display the popup menu.
3. Select an item with arrow keys or mouse, then press Enter or click to paste.
4. Type in the popup to filter search results.
5. Right-click the tray icon to access various features.

## Settings

Right-click tray icon → **Settings** to configure:

- Hotkey shortcuts
- Maximum history count
- Theme (Dark / Light)

## Data Storage

`%APPDATA%\Clipy\clipy.db` (SQLite)

## License

MIT License — Reimplemented for Windows in the spirit of the original [Clipy](https://github.com/Clipy/Clipy).

## Fork Source

- Original macOS app: https://github.com/Clipy/Clipy
- This fork: https://github.com/Iovesophy/Clipy
