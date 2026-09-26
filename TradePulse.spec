# -*- mode: python ; coding: utf-8 -*-
"""
TradePulse Standard Edition — PyInstaller Build Specification
============================================================
Compiles the standalone Windows executable for the full institutional TradePulse platform.

Key Build Specifications:
- Entry point: main.py
- Embedded Assets: ui/, assets/
- Target Architecture: Windows 64-bit (Console disabled, GUI mode only)
- Output Artifacts:
    1. dist/TradePulse-Standalone.exe (Single-file portable binary)
    2. dist/TradePulse/TradePulse.exe (Folder distribution bundle)
"""
import sys
from pathlib import Path

# Optional bytecode cipher (set to None for default packaging)
block_cipher = None

# Static asset directories bundled into the application root
added_files = [
    ('ui', 'ui'),                   # HTML5/JS Glassmorphic GUI frontend
    ('assets', 'assets'),           # Application icons and branding graphics
]

# Explicitly declare dynamically imported modules to guarantee inclusion in binary
hidden_imports = [
    # Networking and WebSocket Protocol
    'websockets',
    'websockets.legacy',
    'websockets.legacy.client',
    'httpx',
    
    # Data Modeling and Serialization
    'pydantic',
    'pydantic_settings',
    'cryptography',
    
    # Image Generation and Chart Plotting
    'PIL',
    'matplotlib',
    'matplotlib.backends.backend_agg',
    
    # Native Webview2 GUI Framework
    'webview',
    'webview.platforms.winforms',
    'webview.platforms.edgechromium',
    'sqlite3',
    'unittest',
    
    # TradePulse Core Engine Subsystems
    'core',
    'core.config',
    'core.security',
    'core.models.candle',
    'core.models.signal',
    'core.ingester.asset_registry',
    'core.ingester.auth_manager',
    'core.ingester.frame_parser',
    'core.ingester.socket_client',
    'core.ingester.real_market_feed',
    'core.indicators.engine',
    'core.charts.generator',
    'core.strategy.schema',
    'core.strategy.compiler',
    'core.strategy.rules_ast',
    'core.strategy.confluence',
    'core.strategy.cooldown',
    'core.strategy.manager',
    'core.strategy.tracker',
    'core.strategy.backtest',
    'core.storage.db',
    'core.telegram.bridge',
    'core.telegram.formatter',
    'core.telegram.manager',
    'core.webhooks.server',
    'core.news',
    'core.news.calendar',
    'core.strategy.quant_ev',
    'core.strategy.risk_manager',
    'core.strategy.session_scheduler',
    'core.strategy.optimizer',
    'core.licensing',
    'core.licensing.client',
]

# Configure PyInstaller dependency analysis and pruning
a = Analysis(
    ['main.py'],                     # Application entry script
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude bulky unnecessary packages to reduce binary size
        'tkinter', 'pytest',
        'torch', 'torchvision', 'torchaudio', 'tensorboard',
        'scipy', 'pandas', 'IPython', 'jupyter', 'notebook', 'nbconvert', 'nbformat'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Compile pure python bytecode archive
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ------------------------------------------------------------------------------
# Target 1: Single Portable Executable (dist/TradePulse-Standalone.exe)
# ------------------------------------------------------------------------------
exe_standalone = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='TradePulse-Standalone',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                  # Headless windowed mode: No cmd black box
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(Path('assets/icon.ico')) if Path('assets/icon.ico').exists() else None,
)

# ------------------------------------------------------------------------------
# Target 2: Folder Distribution (dist/TradePulse/TradePulse.exe)
# ------------------------------------------------------------------------------
exe_dir = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TradePulse',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,                  # Headless windowed mode: No cmd black box
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(Path('assets/icon.ico')) if Path('assets/icon.ico').exists() else None,
)

# Collect all dynamic library dependencies and static assets into output directory
coll = COLLECT(
    exe_dir,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='TradePulse',
)
