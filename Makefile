all: dep ui
	pyinstaller -F -w -i resource/kindle.icns kindle_download_helper.py

dep:
	pip install -r requirements.txt

gui_dep:
	pip install -r requirements_gui.txt

ui: gui_dep
	pyside6-rcc ./icon.qrc -o icon_rc.py
	pyside6-uic ./kindle.ui -o ui_kindle.py
clean: 
	rm -rf dist build kindle_download_helper.spec

.PHONY: all dep gui_dep ui
