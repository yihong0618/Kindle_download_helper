all: dep ui
	pyinstaller -F -w -i resource/kindle.icns kindle_download_helper.py

dep:
	pip install -r requirements.txt

gui_dep:
	pip install -r requirements_gui.txt

ui: gui_dep
	pyside6-rcc ./icon.qrc -o kindle_rc.py
	pyside6-uic ./kindle.ui -o ui_kindle.py


.PHONY: all dep gui_dep ui
