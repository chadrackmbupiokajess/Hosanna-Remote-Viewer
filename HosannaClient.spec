# -*- mode: python ; coding: utf-8 -*-

from kivy.tools.packaging.pyinstaller_hooks import get_hooks

a = Analysis(
    ['client.py'],
    pathex=['C:/Users/chadr/Videos/Projet/Brouillon/Hosanna Remote Viewer'],
    binaries=[],
    datas=[
        ('cert.pem', '.'),
        ('logo.ico', '.'),
        ('seguisym.ttf', '.')
    ],
    hiddenimports=[
        'kivy.core.text.markup',
        'kivy.core.image.img_pil', 
        'kivy.core.image.img_ffpyplayer',
        'kivy.lib.ddsfile',
        'kivy.lib.osc',
        'kivy.lib.mtdev',
        'kivy.lib.gstplayer',
        'kivy.garden.iconfonts',
        'pyperclip',
        'win32timezone'
    ],
    hookspath=get_hooks()['hookspath'],
    runtime_hooks=get_hooks()['runtime_hooks'],
    hooksconfig={},
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='HosannaClient',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Masque la console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='logo.ico'  # Définit l'icône de l'exécutable
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='HosannaClient'
)
