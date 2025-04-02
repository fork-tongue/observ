"""
PyQt example that shows how to utilize observ
in combination with Qt.

State is passed to the widgets. One of the widgets
adjusts the state while the other watches the state
and updates the label whenever a computed property
based on the state changes.
"""

import asyncio
from time import sleep

from PySide6 import QtAsyncio
from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from observ import reactive, scheduler, watch


class Display(QWidget):
    def __init__(self, state, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.state = state
        self.watchers = {}

        self.label = QLabel()
        self.progress = QProgressBar()
        self.progress.setMinimum(0)
        self.progress.setMaximum(100)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.progress)

        self.setLayout(layout)

        def label_text():
            if state["clicked"] == 0:
                return "Please click the button below"
            return f"Clicked {state['clicked']} times!"

        self.watchers["label"] = watch(label_text, self.label.setText, immediate=True)
        self.watchers["progress_visible"] = watch(
            lambda: state["progress"] > 0, self.progress.setVisible, immediate=True
        )
        self.watchers["progress"] = watch(
            lambda: state["progress"], self.update_progress
        )

    def update_progress(self, new):
        # Trigger another watcher during scheduler flush
        if new == 50:
            self.state["clicked"] += 0.5
        self.progress.setValue(new)


class LongJob(QObject):
    progress = Signal(int)
    result = Signal(int)
    finished = Signal()

    def run(self):
        self.progress.emit(0)
        for i in range(100):
            sleep(1 / 100.0)
            self.progress.emit(i + 1)

        self.progress.emit(0)
        self.result.emit(1)
        self.finished.emit()


class Controls(QWidget):
    def __init__(self, state, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.state = state

        self.button = QPushButton("Click")
        self.reset = QPushButton("Reset")

        layout = QVBoxLayout()
        layout.addWidget(self.button)
        layout.addWidget(self.reset)

        self.setLayout(layout)

        self.button.clicked.connect(self.on_button_clicked)
        self.reset.clicked.connect(self.on_reset_clicked)

    def on_button_clicked(self):
        self.thread = QThread()
        self.worker = LongJob()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

        def progress(x):
            self.state["progress"] = x

        def bump(x):
            self.state["clicked"] += x * 0.5

        self.button.setEnabled(False)
        self.thread.finished.connect(lambda: self.button.setEnabled(True))
        self.worker.result.connect(bump)
        self.worker.progress.connect(progress)

    def on_reset_clicked(self):
        self.state["clicked"] = 0


if __name__ == "__main__":
    # Define some state
    state = reactive({"clicked": 0, "progress": 0})

    app = QApplication([])

    asyncio.set_event_loop_policy(QtAsyncio.QAsyncioEventLoopPolicy())
    scheduler.register_asyncio()

    # Create layout and pass state to widgets
    layout = QVBoxLayout()
    layout.addWidget(Display(state))
    layout.addWidget(Controls(state))

    widget = QWidget()
    widget.setLayout(layout)
    widget.show()
    widget.setWindowTitle("Clicked?")

    app.exec()
