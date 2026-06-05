# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for SmartBlue Tasmota Manager."""

import sys
from pathlib import Path

ROOT = Path(SPECPATH)

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # Textual CSS theme file
        (str(ROOT / "tasmota_manager.tcss"), "."),
        # groups.json (region/user hierarchy) – runtime editable, placed next to exe
        (str(ROOT / "groups.json"), "."),
        # Include any existing profiles as defaults
        (str(ROOT / "profiles"), "profiles"),
        # Textual internal CSS / assets (required for the TUI to render)
        ("tasmota_manager", "tasmota_manager"),
        # decode-config.py tool for binary .dmp config parsing (placed next to exe)
        (str(ROOT / "decode_config_tool.py"), "."),
    ],
    hiddenimports=[
        "textual",
        "textual.app",
        "textual.widgets",
        "textual.widgets._select",
        "textual.widgets._data_table",
        "textual.widgets._input",
        "textual.widgets._button",
        "textual.widgets._label",
        "textual.widgets._static",
        "textual.widgets._tab_pane",
        "textual.widgets._tabbed_content",
        "textual.containers",
        "textual.screen",
        "pydantic",
        "pydantic.v1",
        "serial",
        "serial.tools",
        "serial.tools.list_ports",
        "paho",
        "paho.mqtt",
        "paho.mqtt.client",
        "esptool",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SmartBlue-TasmotaManager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,   # keep console for Textual TUI (it needs a terminal)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SmartBlue-TasmotaManager",
)
