all: dep ui
	pyinstaller -F -w -i resource/kindle.icns -n kindle_download_helper kindle_gui.py

dep:
	pip install -r requirements.txt

gui_dep:
	pip install -r requirements_gui.txt

ui: gui_dep
	pyside6-rcc gui/icon.qrc -o gui/icon_rc.py
	pyside6-uic gui/kindle.ui -o gui/ui_kindle.py
clean:
	rm -rf dist build kindle_gui.spec

.PHONY: all dep gui_dep ui clean
