# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'kindle_helper.ui'
##
## Created by: Qt User Interface Compiler version 6.3.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (
    QCoreApplication,
    QDate,
    QDateTime,
    QLocale,
    QMetaObject,
    QObject,
    QPoint,
    QRect,
    QSize,
    QTime,
    QUrl,
    Qt,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QConicalGradient,
    QCursor,
    QFont,
    QFontDatabase,
    QGradient,
    QIcon,
    QImage,
    QKeySequence,
    QLinearGradient,
    QPainter,
    QPalette,
    QPixmap,
    QRadialGradient,
    QTransform,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpinBox,
    QTableView,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


class Ui_MainDialog(object):
    def setupUi(self, MainDialog):
        if not MainDialog.objectName():
            MainDialog.setObjectName("MainDialog")
        MainDialog.resize(1190, 872)
        self.horizontalLayout = QHBoxLayout(MainDialog)
        self.horizontalLayout.setSpacing(10)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.leftLayout = QVBoxLayout()
        self.leftLayout.setObjectName("leftLayout")
        self.listBox = QGroupBox(MainDialog)
        self.listBox.setObjectName("listBox")
        self.verticalLayout_5 = QVBoxLayout(self.listBox)
        self.verticalLayout_5.setObjectName("verticalLayout_5")
        self.fetchButton = QPushButton(self.listBox)
        self.fetchButton.setObjectName("fetchButton")

        self.verticalLayout_5.addWidget(self.fetchButton, 0, Qt.AlignRight)

        self.bookView = QTableView(self.listBox)
        self.bookView.setObjectName("bookView")

        self.verticalLayout_5.addWidget(self.bookView)

        self.horizontalLayout_4 = QHBoxLayout()
        self.horizontalLayout_4.setObjectName("horizontalLayout_4")
        self.label_2 = QLabel(self.listBox)
        self.label_2.setObjectName("label_2")

        self.horizontalLayout_4.addWidget(self.label_2)

        self.outDirEdit = QLineEdit(self.listBox)
        self.outDirEdit.setObjectName("outDirEdit")

        self.horizontalLayout_4.addWidget(self.outDirEdit)

        self.browseButton = QPushButton(self.listBox)
        self.browseButton.setObjectName("browseButton")

        self.horizontalLayout_4.addWidget(self.browseButton)

        self.downloadButton = QPushButton(self.listBox)
        self.downloadButton.setObjectName("downloadButton")

        self.horizontalLayout_4.addWidget(self.downloadButton)

        self.verticalLayout_5.addLayout(self.horizontalLayout_4)

        self.leftLayout.addWidget(self.listBox)

        self.groupBox_2 = QGroupBox(MainDialog)
        self.groupBox_2.setObjectName("groupBox_2")
        self.groupBox_2.setMaximumSize(QSize(16777215, 200))
        self.verticalLayout_7 = QVBoxLayout(self.groupBox_2)
        self.verticalLayout_7.setObjectName("verticalLayout_7")
        self.logBrowser = QTextBrowser(self.groupBox_2)
        self.logBrowser.setObjectName("logBrowser")

        self.verticalLayout_7.addWidget(self.logBrowser)

        self.leftLayout.addWidget(self.groupBox_2)

        self.horizontalLayout.addLayout(self.leftLayout)

        self.rightLayout = QVBoxLayout()
        self.rightLayout.setSpacing(6)
        self.rightLayout.setObjectName("rightLayout")
        self.settingsBox = QGroupBox(MainDialog)
        self.settingsBox.setObjectName("settingsBox")
        self.settingsBox.setMaximumSize(QSize(400, 16777215))
        self.verticalLayout = QVBoxLayout(self.settingsBox)
        self.verticalLayout.setObjectName("verticalLayout")
        self.loginGroupBox = QGroupBox(self.settingsBox)
        self.loginGroupBox.setObjectName("loginGroupBox")
        self.horizontalLayout_2 = QHBoxLayout(self.loginGroupBox)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.verticalLayout_2 = QVBoxLayout()
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.radioCOM = QRadioButton(self.loginGroupBox)
        self.radioCOM.setObjectName("radioCOM")

        self.verticalLayout_2.addWidget(self.radioCOM)

        self.radioCN = QRadioButton(self.loginGroupBox)
        self.radioCN.setObjectName("radioCN")
        self.radioCN.setChecked(True)

        self.verticalLayout_2.addWidget(self.radioCN)

        self.horizontalLayout_2.addLayout(self.verticalLayout_2)

        self.loginButton = QPushButton(self.loginGroupBox)
        self.loginButton.setObjectName("loginButton")
        self.loginButton.setMaximumSize(QSize(80, 16777215))

        self.horizontalLayout_2.addWidget(self.loginButton)

        self.verticalLayout.addWidget(self.loginGroupBox)

        self.cookiesGroupBox = QGroupBox(self.settingsBox)
        self.cookiesGroupBox.setObjectName("cookiesGroupBox")
        self.verticalLayout_3 = QVBoxLayout(self.cookiesGroupBox)
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.cookieTextEdit = QPlainTextEdit(self.cookiesGroupBox)
        self.cookieTextEdit.setObjectName("cookieTextEdit")

        self.verticalLayout_3.addWidget(self.cookieTextEdit)

        self.horizontalLayout_3 = QHBoxLayout()
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.radioFromInput = QRadioButton(self.cookiesGroupBox)
        self.radioFromInput.setObjectName("radioFromInput")

        self.horizontalLayout_3.addWidget(self.radioFromInput)

        self.radioFromBrowser = QRadioButton(self.cookiesGroupBox)
        self.radioFromBrowser.setObjectName("radioFromBrowser")
        self.radioFromBrowser.setChecked(True)

        self.horizontalLayout_3.addWidget(self.radioFromBrowser)

        self.verticalLayout_3.addLayout(self.horizontalLayout_3)

        self.verticalLayout.addWidget(self.cookiesGroupBox)

        self.groupBox = QGroupBox(self.settingsBox)
        self.groupBox.setObjectName("groupBox")
        self.verticalLayout_4 = QVBoxLayout(self.groupBox)
        self.verticalLayout_4.setObjectName("verticalLayout_4")
        self.csrfEdit = QLineEdit(self.groupBox)
        self.csrfEdit.setObjectName("csrfEdit")

        self.verticalLayout_4.addWidget(self.csrfEdit)

        self.verticalLayout.addWidget(self.groupBox)

        self.horizontalLayout_5 = QHBoxLayout()
        self.horizontalLayout_5.setObjectName("horizontalLayout_5")
        self.label = QLabel(self.settingsBox)
        self.label.setObjectName("label")

        self.horizontalLayout_5.addWidget(self.label)

        self.cutLengthSpin = QSpinBox(self.settingsBox)
        self.cutLengthSpin.setObjectName("cutLengthSpin")
        self.cutLengthSpin.setMaximum(999)
        self.cutLengthSpin.setValue(100)

        self.horizontalLayout_5.addWidget(self.cutLengthSpin)

        self.verticalLayout.addLayout(self.horizontalLayout_5)

        self.rightLayout.addWidget(self.settingsBox, 0, Qt.AlignTop)

        self.copyrightBox = QGroupBox(MainDialog)
        self.copyrightBox.setObjectName("copyrightBox")
        self.verticalLayout_6 = QVBoxLayout(self.copyrightBox)
        self.verticalLayout_6.setObjectName("verticalLayout_6")
        self.label_6 = QLabel(self.copyrightBox)
        self.label_6.setObjectName("label_6")

        self.verticalLayout_6.addWidget(self.label_6)

        self.label_3 = QLabel(self.copyrightBox)
        self.label_3.setObjectName("label_3")
        self.label_3.setTextFormat(Qt.MarkdownText)

        self.verticalLayout_6.addWidget(self.label_3)

        self.label_4 = QLabel(self.copyrightBox)
        self.label_4.setObjectName("label_4")
        self.label_4.setTextFormat(Qt.MarkdownText)

        self.verticalLayout_6.addWidget(self.label_4)

        self.label_5 = QLabel(self.copyrightBox)
        self.label_5.setObjectName("label_5")

        self.verticalLayout_6.addWidget(self.label_5)

        self.rightLayout.addWidget(self.copyrightBox, 0, Qt.AlignTop)

        self.horizontalLayout.addLayout(self.rightLayout)

        self.horizontalLayout.setStretch(0, 1)

        self.retranslateUi(MainDialog)

        QMetaObject.connectSlotsByName(MainDialog)

    # setupUi

    def retranslateUi(self, MainDialog):
        MainDialog.setWindowTitle(
            QCoreApplication.translate(
                "MainDialog", "Kindle \u4e0b\u8f7d\u52a9\u624b", None
            )
        )
        self.listBox.setTitle(
            QCoreApplication.translate("MainDialog", "\u4e0b\u8f7d\u5217\u8868", None)
        )
        self.fetchButton.setText(
            QCoreApplication.translate(
                "MainDialog", "\u83b7\u53d6\u4e66\u7c4d\u5217\u8868", None
            )
        )
        self.label_2.setText(
            QCoreApplication.translate(
                "MainDialog", "\u76ee\u6807\u6587\u4ef6\u5939", None
            )
        )
        self.outDirEdit.setText(
            QCoreApplication.translate("MainDialog", "DOWNLOADS", None)
        )
        self.browseButton.setText(
            QCoreApplication.translate("MainDialog", "\u6d4f\u89c8...", None)
        )
        self.downloadButton.setText(
            QCoreApplication.translate("MainDialog", "\u4e0b\u8f7d\u5168\u90e8", None)
        )
        self.groupBox_2.setTitle(
            QCoreApplication.translate("MainDialog", "\u8f93\u51fa", None)
        )
        self.logBrowser.setHtml(
            QCoreApplication.translate(
                "MainDialog",
                '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0//EN" "http://www.w3.org/TR/REC-html40/strict.dtd">\n'
                '<html><head><meta name="qrichtext" content="1" /><meta charset="utf-8" /><style type="text/css">\n'
                "p, li { white-space: pre-wrap; }\n"
                "hr { height: 1px; border-width: 0; }\n"
                "</style></head><body style=\" font-family:'Microsoft YaHei UI'; font-size:9pt; font-weight:400; font-style:normal;\">\n"
                '<p style="-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><br /></p></body></html>',
                None,
            )
        )
        self.settingsBox.setTitle(
            QCoreApplication.translate("MainDialog", "\u8bbe\u7f6e", None)
        )
        self.loginGroupBox.setTitle("")
        self.radioCOM.setText(
            QCoreApplication.translate("MainDialog", "\u7f8e\u4e9a(.com)", None)
        )
        self.radioCN.setText(
            QCoreApplication.translate("MainDialog", "\u4e2d\u4e9a(.cn)", None)
        )
        self.loginButton.setText(
            QCoreApplication.translate("MainDialog", "\u767b\u5f55", None)
        )
        self.cookiesGroupBox.setTitle(
            QCoreApplication.translate("MainDialog", "Cookies", None)
        )
        self.radioFromInput.setText(
            QCoreApplication.translate("MainDialog", "\u6765\u81ea\u8f93\u5165", None)
        )
        self.radioFromBrowser.setText(
            QCoreApplication.translate(
                "MainDialog", "\u6765\u81ea\u6d4f\u89c8\u5668", None
            )
        )
        self.groupBox.setTitle(
            QCoreApplication.translate("MainDialog", "CSRF Token", None)
        )
        self.label.setText(
            QCoreApplication.translate(
                "MainDialog", "\u6587\u4ef6\u540d\u622a\u65ad", None
            )
        )
        self.copyrightBox.setTitle("")
        self.label_6.setText(
            QCoreApplication.translate(
                "MainDialog",
                "\u9690\u79c1\u58f0\u660e\uff1a\u6211\u4eec\u4e0d\u4f1a\u6536\u96c6\u4efb\u4f55\u7528\u6237\u4fe1\u606f\uff0c\u8bf7\u653e\u5fc3\u4f7f\u7528",
                None,
            )
        )
        self.label_3.setText(
            QCoreApplication.translate(
                "MainDialog",
                "Copyright 2022 \u00a9 [yihong0618](https://github.com/yihong0618)",
                None,
            )
        )
        self.label_4.setText(
            QCoreApplication.translate(
                "MainDialog",
                "GitHub: <https://github.com/yihong0618/Kindle_download_helper>",
                None,
            )
        )
        self.label_5.setText(
            QCoreApplication.translate("MainDialog", "License: MIT", None)
        )

    # retranslateUi
