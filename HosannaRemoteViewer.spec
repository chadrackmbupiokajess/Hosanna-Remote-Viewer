# -*- mode: python ; coding: utf-8 -*-

from kivy_deps import sdl2, glew

block_cipher = None

a = Analysis(['client.py'],
             pathex=['C:/Users/chadr/Videos/Projet/Brouillon/Hosanna Remote Viewer'],
             binaries=[],
             datas=[
                 ('logo.ico', '.'),
                 ('Hosanna Cameralogo.png', '.'),
                 ('seguisym.ttf', '.'),
                 ('cert.pem', '.')
             ],
             hiddenimports=[],
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='Hosanna Remote Reg',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False, # This is for --windowed
          icon='logo.ico') # This sets the .exe icon

coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               *[Tree(p) for p in sdl2.dep_bins],
               *[Tree(p) for p in glew.dep_bins],
               strip=False,
               upx=True,
               upx_exclude=[],
               name='Hosanna Remote Reg')
