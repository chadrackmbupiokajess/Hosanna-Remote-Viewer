[app]
title = Hosanna Remote Viewer
package.name = hosannaremote
package.domain = org.hosanna
source.dir = .
source.include_exts = py,png,jpg,kv,ttf,ico,pem
version = 1.0.0
requirements = python3,kivy==2.3.0,pyopenssl,cython,pyjnius
orientation = portrait
icon.filename = %(source.dir)s/logo.ico
presplash.filename = %(source.dir)s/Hosanna Cameralogo.png
fullscreen = 0

[buildozer]
log_level = 2
warn_on_root = 1

[android]
android.permissions = INTERNET, ACCESS_NETWORK_STATE, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE, CAMERA
android.api = 31
android.minapi = 21
android.sdk = 24
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a
