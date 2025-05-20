# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

a = Analysis(
    ['src/cli_entry.py'],
    pathex=[],
    binaries=[],
    datas=collect_data_files('runninglog') + 
          collect_data_files('dateparser') +
          collect_data_files('rich'),
    hiddenimports=[
        'zoneinfo',
        'bs4',
        'lxml',
        'dateparser.data',
        'pydantic',
        'aiofiles',
        'typer',
        'rich.console',
        'rich.progress',
    ] + collect_submodules('dateparser') + 
       collect_submodules('rich'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='runninglog',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add an icon path here if available
)

# Create a macOS .app bundle
# Uncomment to create a Mac app bundle if on macOS
# app = BUNDLE(
#     exe,
#     name='RunningLog.app',
#     icon=None,  # Add an icon path here if available
#     bundle_identifier='com.michaelharkins.runninglog',
# )
