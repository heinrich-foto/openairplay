#!/usr/bin/env python3
#  Copyright (C) 2015-2016 Ben Klein.

import sys
import asyncio

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QSettings
from qasync import QEventLoop

from . import log
from . import discovery
from .receiver_device import AirplayReceiver
from .mirroring import OpenAirPlayMirroringClient

# TEMP
log.setLevel(log.DEBUG)
log.debug("Debugging enabled.")
log.debug("Called with system args: " + str(sys.argv))
log.debug("Python version: " + sys.version)

AIRPLAY_NO_DISPLAY_NAME = "No display."


class Window(QtWidgets.QWidget):
    def __init__(self):
        super(Window, self).__init__()

        self.settings = QSettings('open-airplay')
        # Establishes a hook on our system settings.
        # http://pyqt.sourceforge.net/Docs/PyQt4/pyqt_qsettings.html

        # Place items in our window.
        self.createIconGroupBox() # Tray Icon Settings
        self.createMessageGroupBox() # Test notification group
        self.createDeviceListGroupBox() # Airplay server selection

        # Set the iconlabel to it's minimum width without scollbaring.
        self.iconLabel.setMinimumWidth(self.durationLabel.sizeHint().width())

        # Create action groups to put actionable items into.
        self.createActions()
        self.createTrayIcon()

        # Attach clicks on things to actual functions
        self.showMessageButton.clicked.connect(self.showMessage)
        self.showIconCheckBox.toggled.connect(self.trayIconVisible)
        self.systrayClosePromptCheckBox.toggled.connect(self.setSystrayClosePrompt)
        self.iconComboBox.currentIndexChanged.connect(self.setIcon)
        self.trayIcon.messageClicked.connect(self.messageClicked)
        self.trayIcon.activated.connect(self.iconActivated)

        # Finally add the GUI item groupings we made to the layout and init it.
        mainLayout = QtWidgets.QVBoxLayout()
        mainLayout.addWidget(self.iconGroupBox)
        mainLayout.addWidget(self.deviceListGroupBox)
        mainLayout.addWidget(self.messageGroupBox)
        self.setLayout(mainLayout)

        # Set our System Tray Presence
        self.iconComboBox.setCurrentIndex(1)
        self.trayIcon.show()
        self.trayIcon.setToolTip("OpenAirplay")

        # Set our basic window things.
        self.setWindowTitle("OpenAirplay Settings")
        self.resize(400, 300)

        # If the user chose not to show the system tray icon:
        if self.settings.value('systrayicon', type=bool) is False:
            log.info("The user chose not to show the system tray icon.")
            self.trayIconVisible(False)

        # # Setup stuff to poll available receivers every 3 seconds.
        # self.oldReceiverList = []
        # self.timer=QtCore.QTimer()
        # self.timer.start(3000)
        # self.timer.timeout.connect(self.updateReceivers)

        # Start discovery of airplay receivers:
        log.debug("Starting discovery service...")
        try:
            loop = asyncio.get_event_loop()
            log.debug(f"Event loop running: {loop}")
            self.service_listener = discovery.AirplayServiceListener(loop)
            self.service_listener.start()
            self.service_listener.receiver_added.connect(self.add_receiver)
            self.service_listener.receiver_removed.connect(self.remove_receiver)
        except RuntimeError as e:
            log.error(f"Failed to get running event loop: {e}")

    def setVisible(self, visible):
        # When we want to 'disappear' into the system tray.
        self.minimizeAction.setEnabled(visible)
        #self.maximizeAction.setEnabled(not self.isMaximized())
        self.restoreAction.setEnabled(self.isMaximized() or not visible)
        super(Window, self).setVisible(visible)

    def closeEvent(self, event):
        # When someone clicks to close the window, not the tray icon.
        if self.trayIcon.isVisible():
            if self.settings.value('promptOnClose_systray', type=bool):
                log.info("The program is returning to the system tray, user notified.")
                QtWidgets.QMessageBox.information(self, "Systray",
                    "The program will keep running in the system tray. \
                    To terminate the program, choose <b>Quit</b> in \
                    the menu of the system tray airplay icon.")
            else:
                log.info("Program returned to system tray, user chose not to be notified.")
            self.hide()
            event.ignore()
            log.info("Closing to System Tray")
        else:
            log.warn("Tray Icon not visible, quitting.")
            self.quit(0)

    def setIcon(self, index):
        # Sets the selected icon in the tray and taskbar.
        icon = self.iconComboBox.itemIcon(index)
        self.trayIcon.setIcon(icon)
        self.setWindowIcon(icon)

    def setSystrayClosePrompt(self, preference):
        print("Prompt on close is now " + str(preference))
        self.settings.setValue('promptOnClose_systray', preference)

    def trayIconVisible(self, preference):
        self.trayIcon.setVisible(preference)
        self.settings.setValue('systrayicon', preference)

    def iconActivated(self, reason):
        if reason in (QtWidgets.QSystemTrayIcon.ActivationReason.Trigger,
                      QtWidgets.QSystemTrayIcon.ActivationReason.DoubleClick):
            self.iconComboBox.setCurrentIndex(
                (self.iconComboBox.currentIndex() + 1)
                % self.iconComboBox.count())
        elif reason == QtWidgets.QSystemTrayIcon.ActivationReason.MiddleClick:
            self.showMessage()

    def showMessage(self):
        # Show the message that was typed in the boxes
        icon = QtWidgets.QSystemTrayIcon.MessageIcon(
            self.typeComboBox.itemData(self.typeComboBox.currentIndex()))
        self.trayIcon.showMessage(self.titleEdit.text(),
                                  self.bodyEdit.toPlainText(), icon,
                                  self.durationSpinBox.value() * 1000)

    def messageClicked(self):
        # In the case that someone clicks on the notification popup (impossible on Ubuntu Unity)
        QtWidgets.QMessageBox.information(None, "OpenAirplay Help", "If you need help with OpenAirplay, "
        "see the Github page to file bug reports or see further documentation and help.")

    def add_receiver(self, receiver: AirplayReceiver):
        log.debug(f"Adding receiver to UI: {receiver.list_entry_name}")
        item = QtWidgets.QListWidgetItem(receiver.list_entry_name)
        item.setData(QtCore.Qt.ItemDataRole.UserRole, receiver)
        self.deviceSelectList.addItem(item)
        log.debug(f"Added receiver to deviceSelectList: '{receiver.name}'")

        # log.debug(f"Scanning for pyatv device...")
        # # # XXX HACK TODO: non-blocking lookup
        # tv = asyncio.ensure_future(receiver._scan_for_device())
        # # log.debug(f"scan found: {tv}")

    def remove_receiver(self, receiver: AirplayReceiver):
        item_name = receiver.list_entry_name
        items = self.deviceSelectList.findItems(item_name, QtCore.Qt.MatchFlag.MatchExactly)
        for x in items:
            self.deviceSelectList.takeItem(self.deviceSelectList.row(x))
            log.debug(f"Removed receiver from deviceSelectList: '{receiver.name}'")

    def start_mirroring_to_selection(self):
        selected = [x.row() for x in self.deviceSelectList.selectedIndexes()]
        if len(selected) > 1:
            log.error(f"Mirroring to more than one display not supported")
            raise NotImplementedError(f"Cannot mirror to more than one display.")
        elif not selected:
            log.warn(f"Select a device to mirror to.")
            return

        target_device_name = self.deviceSelectList.item(selected[0]).text()
        if target_device_name == AIRPLAY_NO_DISPLAY_NAME:
            # TODO stop mirroring to other displays
            log.warn(f"TODO: no display -> stop")
            return
        target_device = self.deviceSelectList.item(selected[0]).data(QtCore.Qt.ItemDataRole.UserRole)
        log.info(f"Starting mirroring to {target_device_name} ...")

        self._active_mirroring_client = OpenAirPlayMirroringClient(target_device)
        self._active_mirroring = asyncio.ensure_future(
            self._active_mirroring_client.start()
        )

    def createIconGroupBox(self): # Add the SysTray preferences window grouping
        self.iconGroupBox = QtWidgets.QGroupBox("Tray Icon")

        self.iconLabel = QtWidgets.QLabel("Icon:")

        self.iconComboBox = QtWidgets.QComboBox()
        self.iconComboBox.addItem(QtGui.QIcon('images/Airplay-Light'), "Black Icon")
        self.iconComboBox.addItem(QtGui.QIcon('images/Airplay-Dark'), "White Icon")

        self.showIconCheckBox = QtWidgets.QCheckBox("Show tray icon")
        self.showIconCheckBox.setChecked(self.settings.value('systrayicon', type=bool))
        print("Got systrayicon from settings:" + str(self.settings.value('systrayicon', type=bool)))

        self.systrayClosePromptCheckBox = QtWidgets.QCheckBox("Systray Close warning")
        self.systrayClosePromptCheckBox.setChecked(self.settings.value('promptOnClose_systray', type=bool))
        print("Got promptOnClose_systray from settings:" + str(self.settings.value('promptOnClose_systray', type=bool)))

        iconLayout = QtWidgets.QHBoxLayout()
        iconLayout.addWidget(self.iconLabel)
        iconLayout.addWidget(self.iconComboBox)
        iconLayout.addStretch()
        iconLayout.addWidget(self.showIconCheckBox)
        iconLayout.addWidget(self.systrayClosePromptCheckBox)
        self.iconGroupBox.setLayout(iconLayout)

    # Creates the device selection list.
    def createDeviceListGroupBox(self):
        self.deviceListGroupBox = QtWidgets.QGroupBox("Airplay to")

        self.deviceSelectList = QtWidgets.QListWidget()
        deviceSelectListNoDisplayItem = QtWidgets.QListWidgetItem(AIRPLAY_NO_DISPLAY_NAME)
        self.deviceSelectList.addItem(deviceSelectListNoDisplayItem)

        self.deviceSelectStartMirroringButton = QtWidgets.QPushButton("Start Mirroring")
        self.deviceSelectStartMirroringButton.clicked.connect(self.start_mirroring_to_selection)

        # layout
        deviceListLayout = QtWidgets.QHBoxLayout()
        deviceListLayout.addWidget(self.deviceSelectList)
        deviceListLayout.addWidget(self.deviceSelectStartMirroringButton)
        self.deviceListGroupBox.setLayout(deviceListLayout)

    def createMessageGroupBox(self): # Add the message test GUI window grouping.
        self.messageGroupBox = QtWidgets.QGroupBox("Notification Test:")

        typeLabel = QtWidgets.QLabel("Type:")

        self.typeComboBox = QtWidgets.QComboBox()
        self.typeComboBox.addItem("None", QtWidgets.QSystemTrayIcon.MessageIcon.NoIcon)
        #self.typeComboBox.addItem(self.style().standardIcon(
        #        QtWidgets.QStyle.SP_MessageBoxInformation), "Information", #QtWidgets.QSystemTrayIcon.Information)
        #self.typeComboBox.addItem(self.style().standardIcon(
        #        QtWidgets.QStyle.SP_MessageBoxWarning), "Warning", #QtWidgets.QSystemTrayIcon.Warning)
        #self.typeComboBox.addItem(self.style().standardIcon(
        #        QtWidgets.QStyle.SP_MessageBoxCritical), "Critical", #QtWidgets.QSystemTrayIcon.Critical)
        self.typeComboBox.addItem("Information", QtWidgets.QSystemTrayIcon.MessageIcon.Information)
        self.typeComboBox.addItem("Warning", QtWidgets.QSystemTrayIcon.MessageIcon.Warning)
        self.typeComboBox.addItem("Critical", QtWidgets.QSystemTrayIcon.MessageIcon.Critical)
        self.typeComboBox.setCurrentIndex(1)

        self.durationLabel = QtWidgets.QLabel("Duration:")

        self.durationSpinBox = QtWidgets.QSpinBox()
        self.durationSpinBox.setRange(2, 15)
        self.durationSpinBox.setSuffix("s")
        self.durationSpinBox.setValue(5)

        durationWarningLabel = QtWidgets.QLabel("(some systems might ignore this hint)")
        durationWarningLabel.setIndent(10)

        titleLabel = QtWidgets.QLabel("Title:")

        self.titleEdit = QtWidgets.QLineEdit("Cannot connect to network")

        bodyLabel = QtWidgets.QLabel("Body:")

        self.bodyEdit = QtWidgets.QTextEdit()
        self.bodyEdit.setPlainText("Don't believe me. Honestly, I don't have a clue.")

        self.showMessageButton = QtWidgets.QPushButton("Show Message")
        self.showMessageButton.setDefault(True)

        messageLayout = QtWidgets.QGridLayout()
        messageLayout.addWidget(typeLabel, 0, 0)
        messageLayout.addWidget(self.typeComboBox, 0, 1, 1, 2)
        messageLayout.addWidget(self.durationLabel, 1, 0)
        messageLayout.addWidget(self.durationSpinBox, 1, 1)
        messageLayout.addWidget(durationWarningLabel, 1, 2, 1, 3)
        messageLayout.addWidget(titleLabel, 2, 0)
        messageLayout.addWidget(self.titleEdit, 2, 1, 1, 4)
        messageLayout.addWidget(bodyLabel, 3, 0)
        messageLayout.addWidget(self.bodyEdit, 3, 1, 2, 4)
        messageLayout.addWidget(self.showMessageButton, 5, 4)
        messageLayout.setColumnStretch(3, 1)
        messageLayout.setRowStretch(4, 1)
        self.messageGroupBox.setLayout(messageLayout)

    def createActions(self): # Create Actions that can be taken from the System Tray Icon
        self.minimizeAction = QtGui.QAction("Mi&nimize to Tray", self, triggered=self.hide)

        # Application is not the kind to be maximized
        #self.maximizeAction = QtWidgets.QAction("Ma&ximize", self, triggered=self.showMaximized)

        self.restoreAction = QtGui.QAction("Show &Window", self, triggered=self.showNormal)

        self.quitAction = QtGui.QAction("&Quit", self, triggered=QtWidgets.QApplication.quit)

    def createTrayIcon(self):
        self.trayIconMenu = QtWidgets.QMenu()
        self.trayIconMenu.addAction(self.minimizeAction)
        #self.trayIconMenu.addAction(self.maximizeAction)
        self.trayIconMenu.addAction(self.restoreAction)
        self.trayIconMenu.addSeparator()
        self.trayIconMenu.addAction(self.quitAction)

        self.trayIcon = QtWidgets.QSystemTrayIcon(self)
        self.trayIcon.setContextMenu(self.trayIconMenu)

    def quit(self, reason):
        del self.settings
        asyncio.ensure_future(self.service_listener.quit())
        # pending = asyncio.all_tasks()
        asyncio.get_running_loop().stop()
        sys.exit(reason)

def __main__():

    app = QtWidgets.QApplication(['Open Airplay'])
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    # if not QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
    #     QtWidgets.QMessageBox.critical(None, "Systray", "I couldn't detect any system tray on this system.")
    #     sys.exit(1)

    QtWidgets.QApplication.setQuitOnLastWindowClosed(False)

    window = Window()
    window.show()

    with loop:
        loop.run_forever()

if __name__ == '__main__':
    __main__()
