"""
PyQt example that shows how to utilize observ
in combination with Qt.

State is passed to the widgets. One of the widgets
adjusts the state while the other watches the state
and updates the label whenever a computed property
based on the state changes.
"""

from observ import computed, observe, watch
from PyQt5.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget


class Display(QWidget):
    def __init__(self, state, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.state = state

        self.label = QLabel()

        layout = QVBoxLayout()
        layout.addWidget(self.label)

        self.setLayout(layout)

        @computed
        def label_text():
            if state["clicked"] == 0:
                return "Please click the button below"
            return f"Clicked {state['clicked']} times!"

        self.watcher = watch(lambda: label_text(), self.update_label)
        self.watcher.update()

    def update_label(self, old_value, new_value):
        self.label.setText(new_value)


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
        self.state["clicked"] += 1

    def on_reset_clicked(self):
        self.state["clicked"] = 0


if __name__ == "__main__":
    # Define some state
    state = observe({"clicked": 0})

    app = QApplication([])

    # Create layout and pass state to widgets
    layout = QVBoxLayout()
    layout.addWidget(Display(state))
    layout.addWidget(Controls(state))

    widget = QWidget()
    widget.setLayout(layout)
    widget.show()
    widget.setWindowTitle("Clicked?")

    app.exec_()
