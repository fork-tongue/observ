"""
PyQt example that shows how to utilize observ
in combination with Qt.

State is passed to the widgets. One of the widgets
adjusts the state while the other watches the state
and updates the label whenever a computed property
based on the state changes.
"""
from time import sleep

from observ import observe, scheduler, watch
from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class Display(QWidget):
    def __init__(self, state, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.state = state

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

        def progress_visible():
            return state["progress"] > 0

        self.watcher = watch(label_text, self.update_label, immediate=True)
        self.progress_watch = watch(
            lambda: state["progress"],
            lambda _, new: self.progress.setValue(new),
            immediate=True,
        )
        self.progress_visible = watch(
            progress_visible, self.update_visibility, immediate=True
        )

    def update_label(self, old_value, new_value):
        self.label.setText(new_value)

    def update_visibility(self, old_value, new_value):
        self.progress.setVisible(new_value)


class LongJob(QObject):
    progress = Signal(int)
    result = Signal(int)
    finished = Signal()

    def run(self):
        self.progress.emit(0)
        for i in range(100):
            sleep(2 / 100.0)
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
            self.state["clicked"] += x

        self.button.setEnabled(False)
        self.thread.finished.connect(lambda: self.button.setEnabled(True))
        self.worker.result.connect(lambda x: bump(x))
        self.worker.progress.connect(lambda x: progress(x))

    def on_reset_clicked(self):
        self.state["clicked"] = 0


if __name__ == "__main__":
    # Define some state
    state = observe({"clicked": 0, "progress": 0})

    app = QApplication([])

    # Use a timer to run the scheduler
    timer = QTimer()
    timer.timeout.connect(scheduler.flush)
    timer.setInterval(1000 / 60)
    timer.start()

    # Create layout and pass state to widgets
    layout = QVBoxLayout()
    layout.addWidget(Display(state))
    layout.addWidget(Controls(state))

    widget = QWidget()
    widget.setLayout(layout)
    widget.show()
    widget.setWindowTitle("Clicked?")

    app.exec()
