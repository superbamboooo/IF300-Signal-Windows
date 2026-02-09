# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['signal_app_main.py'],
    pathex=[],
    binaries=[],
    datas=[('path_manager.py', '.'), ('init_data_path.py', '.'), ('data_updater.py', '.'), ('weekend_data_updater.py', '.'), ('strategy_if300.py', '.'), ('strategy_weekend.py', '.'), ('data', 'data')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MultiStrategy',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
app = BUNDLE(
    exe,
    name='MultiStrategy.app',
    icon=None,
    bundle_identifier=None,
)
