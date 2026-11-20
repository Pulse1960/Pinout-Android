[app]
title = Pinout eMMC
package.name = pinoutemmc
package.domain = org.ahmedkemmar
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,db
version = 1.2
requirements = python3,kivy,pillow
orientation = portrait
fullscreen = 0
android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.api = 33
android.minapi = 21
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
