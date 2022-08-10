import logging
import os
import sys
import traceback
import webbrowser
from typing import NamedTuple

from PySide6 import QtCore, QtGui, QtWidgets

from gui.__version__ import __version__
from gui.ui_kindle import Ui_MainDialog
from kindle_download_helper import kindle

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
    filetype: str
    done: bool


class Worker(QtCore.QObject):
    finished = QtCore.Signal()
    progress = QtCore.Signal(int)
    logging = QtCore.Signal(str)
    done = QtCore.Signal(int)

    def __init__(self, iterable, kindle):
        super().__init__()
        self.iterable = iterable
        self.kindle = kindle

    def run(self):
        logger.setLevel(logging.INFO)
        logger.handlers[:] = [SignalLogHandler(self.logging)]
        try:
            devices = self.kindle.get_devices()
        except Exception:
            logger.exception("get devices failed")
            self.finished.emit()
            return
        device = devices[0]
        self.kindle.device_serial_number = device["deviceSerialNumber"]
        for i, book in enumerate(self.iterable):
            try:
                self.kindle.download_one_book(book._asdict(), device, i, book.filetype)
            except Exception:
                logger.exception("download failed")
            else:
                self.done.emit(book.id)
            finally:
                self.progress.emit(i)
        with open(os.path.join(self.kindle.out_dir, "key.txt"), "w") as f:
            f.write(f"Key is: {device['deviceSerialNumber']}")
        self.finished.emit()


class KindleMainDialog(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainDialog()
        self.ui.setupUi(self)
        self.set_version()
        self.kindle = kindle.Kindle("")
        self.setup_signals()
        # self.setup_logger()
        self.book_model = BookItemModel(self.ui.bookView, [], ["序号", "书名", "作者"])
        self.ui.bookView.setModel(self.book_model)
        self.ui.bookView.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.ui.bookView.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.Stretch
        )

    def set_version(self):
        self.setWindowTitle(self.windowTitle() + " " + __version__)

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
        self.log(traceback.format_exc())
        self.show_error(f"{exc_info[0].__name__}: {exc_info[1]}")

    def setup_kindle(self):
        instance = self.kindle
        instance.csrf_token = self.ui.csrfEdit.text()
        instance.urls = kindle.KINDLE_URLS[self.get_domain()]
        instance.out_dir = self.ui.outDirEdit.text()
        instance.out_dedrm_dir = os.path.join(instance.out_dir, "DeDRM")
        instance.dedrm = self.ui.dedrmCkb.isChecked()
        instance.cut_length = self.ui.cutLengthSpin.value()
        instance.total_to_download = 0
        try:
            if self.ui.radioFromInput.isChecked():
                instance.set_cookie_from_string(self.ui.cookieTextEdit.toPlainText())
        except Exception:
            self.on_error()
            return False
        try:
            self.kindle.csrf_token
        except Exception:
            self.show_error("Failed to get CSRF token, please input")
            return False
        return True

    def get_domain(self):
        if self.ui.radioCN.isChecked():
            return "cn"
        elif self.ui.radioJP.isChecked():
            return "jp"
        elif self.ui.radioDE.isChecked():
            return "de"
        else:
            return "com"

    def get_filetype(self):
        if self.ui.radioEBOK.isChecked():
            return "EBOK"
        else:
            return "PDOC"

    def on_login_amazon(self):
        url = kindle.KINDLE_URLS[self.get_domain()]["bookall"]
        webbrowser.open(url)

    def on_from_input(self, checked):
        self.ui.cookieTextEdit.setEnabled(checked)

    def on_from_browser(self, checked):
        self.ui.cookieTextEdit.setEnabled(not checked)

    def on_browse_dir(self):
        file_dialog = QtWidgets.QFileDialog()
        file_dialog.setFileMode(QtWidgets.QFileDialog.Directory)
        file_dialog.setOption(QtWidgets.QFileDialog.ShowDirsOnly)
        if file_dialog.exec():
            self.ui.outDirEdit.setText(file_dialog.selectedFiles()[0])

    def on_fetch_books(self):
        if not self.setup_kindle():
            return
        self.ui.fetchButton.setEnabled(False)
        filetype = self.get_filetype()
        try:
            all_books = self.kindle.get_all_books(filetype=filetype)
            book_data = [
                [item["title"], item["authors"], item["asin"], filetype]
                for item in all_books
            ]
            self.book_model.updateData(book_data)
        except Exception:
            self.on_error()
        finally:
            self.ui.fetchButton.setEnabled(True)

    def log(self, message):
        self.ui.logBrowser.append(message)

    def on_download_books(self):
        if not self.setup_kindle():
            return
        if not os.path.exists(self.kindle.out_dir):
            os.makedirs(self.kindle.out_dir)
        if not os.path.exists(self.kindle.out_dedrm_dir):
            os.makedirs(self.kindle.out_dedrm_dir)
        self.thread = QtCore.QThread()
        iterable = self.book_model.data_to_download()
        total = len(iterable)
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
        self.worker.done.connect(self.on_book_done)
        self.worker.logging.connect(self.log)
        self.worker.progress.connect(
            lambda n: self.progressbar.setValue(round(n / total * 100, 2))
        )
        self.ui.downloadButton.setEnabled(False)
        self.thread.finished.connect(self.on_finish_download)
        self.thread.start()

    def on_finish_download(self):
        self.ui.downloadButton.setEnabled(True)
        QtWidgets.QMessageBox.information(self, "下载完成", "下载完成")
        self.ui.verticalLayout_7.removeWidget(self.progressbar)
        self.progressbar.deleteLater()

    def on_book_done(self, idx):
        self.book_model.mark_done(idx - 1)


class BookItemModel(QtCore.QAbstractTableModel):
    def __init__(self, parent, data, header):
        super().__init__(parent)
        self._data = data
        self._header = header

    def headerData(self, section, orientation, role):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return self._header[section]
        return None

    def mark_done(self, idx):
        if idx >= len(self._data):
            return
        self._data[idx] = Book(*self._data[idx][:-1], done=True)
        self.layoutAboutToBeChanged.emit()
        self.dataChanged.emit(
            self.createIndex(idx, 0), self.createIndex(idx, self.columnCount(0))
        )
        self.layoutChanged.emit()

    def updateData(self, data):
        self._data = [Book(i, *row, False) for i, row in enumerate(data, 1)]
        self.layoutAboutToBeChanged.emit()
        self.dataChanged.emit(
            self.createIndex(0, 0),
            self.createIndex(self.rowCount(0), self.columnCount(0)),
        )
        self.layoutChanged.emit()

    def data_to_download(self):
        return [item for item in self._data if not item.done]

    def data(self, index, role):
        if not index.isValid():
            return None
        value = self._data[index.row()][index.column()]
        if role == QtCore.Qt.DisplayRole:
            return value
        if role == QtCore.Qt.BackgroundRole and self._data[index.row()].done:
            return QtGui.QColor(65, 237, 74, 128)
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
