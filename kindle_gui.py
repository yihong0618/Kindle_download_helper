from contextlib import contextmanager
import logging
import os
import sys
from typing import NamedTuple
import webbrowser
from PySide6 import QtWidgets, QtCore

import kindle
from kindle_helper_ui import Ui_MainDialog

logger = logging.getLogger("kindle")


class SignalLogHandler(logging.Handler):
    def __init__(self, signal):
        super().__init__(logging.DEBUG)
        formatter = logging.Formatter("[%(asctime)s]%(levelname)s - %(message)s")
        self.setFormatter(formatter)
        self.signal = signal

    def emit(self, record):
        msg = self.format(record)
        self.signal.emit(msg)


class Book(NamedTuple):
    id: int
    title: str
    author: str
    asin: str


class Worker(QtCore.QObject):
    finished = QtCore.Signal()
    progress = QtCore.Signal(int)
    logging = QtCore.Signal(str)

    def __init__(self, iterable, kindle):
        super().__init__()
        self.iterable = iterable
        self.kindle = kindle

    def run(self):
        logger.setLevel(logging.INFO)
        logger.handlers[:] = [SignalLogHandler(self.logging)]
        try:
            devices = self.kindle.get_devices()
            device = devices[0]
            for i, book in enumerate(self.iterable, 1):
                self.kindle.download_one_book(book.asin, device, i)
                self.progress.emit(i)
        except Exception:
            logger.exception("download failed")
        finally:
            self.finished.emit()


class KindleMainDialog(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainDialog()
        self.ui.setupUi(self)
        self.kindle = kindle.Kindle("")
        self.setup_signals()
        # self.setup_logger()
        self.book_model = BookItemModel(self.ui.bookView, [], ["序号", "书名", "作者"])
        self.ui.bookView.setModel(self.book_model)
        self.ui.bookView.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.ui.bookView.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.Stretch
        )

    def setup_signals(self):
        self.ui.radioFromInput.clicked.connect(self.on_from_input)
        self.ui.radioFromBrowser.clicked.connect(self.on_from_browser)
        self.ui.loginButton.clicked.connect(self.on_login_amazon)
        self.ui.browseButton.clicked.connect(self.on_browse_dir)
        self.ui.fetchButton.clicked.connect(self.on_fetch_books)
        self.ui.downloadButton.clicked.connect(self.on_download_books)

    def show_error(self, message):
        msg = QtWidgets.QErrorMessage(self)
        msg.showMessage(message)

    def on_error(self):
        exc_info = sys.exc_info()
        self.show_error(f"{exc_info[0].__name__}: {exc_info[1]}")

    def setup_kindle(self):
        instance = self.kindle
        instance.csrf_token = self.ui.csrfEdit.text()
        instance.urls = kindle.KINDLE_URLS[self.getDomain()]
        instance.out_dir = self.ui.outDirEdit.text()
        instance.cut_length = self.ui.cutLengthSpin.value()
        instance.total_to_download = 0
        if self.ui.radioFromInput.isChecked():
            instance.set_cookie_from_string(self.ui.cookieTextEdit.text())
        else:
            instance.set_cookie_from_browser()
        if not instance.csrf_token:
            self.show_error("Please input CSRF token")

    def getDomain(self):
        if self.ui.radioCN.isChecked():
            return "cn"
        else:
            return "com"

    @QtCore.Slot()
    def on_login_amazon(self):
        url = kindle.KINDLE_URLS[self.getDomain()]["bookall"]
        webbrowser.open(url)

    @QtCore.Slot()
    def on_from_input(self, checked):
        self.ui.cookieTextEdit.setEnabled(checked)

    @QtCore.Slot()
    def on_from_browser(self, checked):
        self.ui.cookieTextEdit.setEnabled(not checked)

    @QtCore.Slot()
    def on_browse_dir(self):
        file_dialog = QtWidgets.QFileDialog()
        file_dialog.setFileMode(QtWidgets.QFileDialog.Directory)
        file_dialog.setOption(QtWidgets.QFileDialog.ShowDirsOnly)
        if file_dialog.exec_():
            self.ui.outDirEdit.setText(file_dialog.selectedFiles()[0])

    @QtCore.Slot()
    def on_fetch_books(self):
        self.ui.fetchButton.setEnabled(False)
        self.setup_kindle()
        try:
            all_books = self.kindle.get_all_books()
            book_data = [
                [item["title"], item["authors"], item["asin"]] for item in all_books
            ]
            self.book_model.updateData(book_data)
        except Exception:
            self.on_error()
        finally:
            self.ui.fetchButton.setEnabled(True)

    @contextmanager
    def make_progressbar(self, iterable, total):
        parent = self.ui.logBrowser.parent()
        progressbar = QtWidgets.QProgressBar(parent)

        def gen():
            for i, item in enumerate(iterable, 1):
                try:
                    yield item
                finally:
                    progressbar.setValue(round(i / total * 100, 2))

        yield gen()
        self.ui.verticalLayout_7.removeWidget(progressbar)

    @QtCore.Slot()
    def on_download_books(self):
        self.setup_kindle()
        if not os.path.exists(self.kindle.out_dir):
            os.makedirs(self.kindle.out_dir)
        self.thread = QtCore.QThread()
        iterable, total = self.book_model._data, self.book_model.rowCount(0)
        self.kindle.total_to_download = total
        self.worker = Worker(iterable, self.kindle)
        self.worker.moveToThread(self.thread)
        parent = self.ui.logBrowser.parent()
        self.progressbar = QtWidgets.QProgressBar(parent)
        self.ui.verticalLayout_7.insertWidget(0, self.progressbar)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.worker.logging.connect(self.ui.logBrowser.append)
        self.worker.progress.connect(
            lambda n: self.progressbar.setValue(round(n / total * 100, 2))
        )
        self.ui.downloadButton.setEnabled(False)
        self.thread.finished.connect(self.on_finish_download)
        self.thread.start()

    def on_finish_download(self):
        self.ui.verticalLayout_7.removeWidget(self.progressbar)
        self.progressbar.deleteLater()


class BookItemModel(QtCore.QAbstractTableModel):
    def __init__(self, parent, data, header):
        super().__init__(parent)
        self._data = data
        self._header = header

    def headerData(self, section, orientation, role):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return self._header[section]
        return None

    def updateData(self, data):
        self._data = [Book(i, *row) for i, row in enumerate(data, 1)]
        self.layoutAboutToBeChanged.emit()
        self.dataChanged.emit(
            self.createIndex(0, 0),
            self.createIndex(self.rowCount(0), self.columnCount(0)),
        )
        self.layoutChanged.emit()

    def data(self, index, role):
        if not index.isValid():
            return None
        value = self._data[index.row()][index.column()]
        if role == QtCore.Qt.DisplayRole:
            return value
        return None

    def rowCount(self, parent):
        return len(self._data)

    def columnCount(self, parent):
        return len(self._header)


def main():
    app = QtWidgets.QApplication()
    dialog = KindleMainDialog()
    dialog.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
