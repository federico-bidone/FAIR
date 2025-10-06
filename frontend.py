"""PySide6 desktop client for the Carbon-styled expense tracker.

The user interface embraces the Carbon Design System visual language by
using a dark header, rounded corners and strong typographic hierarchy.
It consumes the REST API exposed by ``backend.py``.
"""

from __future__ import annotations

import sys
from typing import List

import requests
from PySide6 import QtCore, QtGui, QtWidgets


API_URL = "http://127.0.0.1:5000/expenses"


class ExpenseClient:
    """HTTP client for talking with the backend service."""

    def list_expenses(self) -> List[dict]:
        response = requests.get(API_URL, timeout=5)
        response.raise_for_status()
        return response.json()

    def create_expense(self, payload: dict) -> dict:
        response = requests.post(API_URL, json=payload, timeout=5)
        response.raise_for_status()
        return response.json()

    def delete_expense(self, expense_id: int) -> None:
        response = requests.delete(f"{API_URL}/{expense_id}", timeout=5)
        response.raise_for_status()


class CarbonHeader(QtWidgets.QWidget):
    """Stylised header emulating the Carbon Design System look."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        icon = QtWidgets.QLabel()
        pixmap = QtGui.QPixmap(32, 32)
        pixmap.fill(QtGui.QColor("#0f62fe"))
        icon.setPixmap(pixmap)
        icon.setFixedSize(32, 32)

        title = QtWidgets.QLabel("B.I.D.O. Expense Tracker")
        title.setStyleSheet("font-size: 20pt; font-weight: 600; color: white;")

        subtitle = QtWidgets.QLabel("Monitor your spending with Carbon design elegance")
        subtitle.setStyleSheet("color: #c6c6c6; font-size: 10pt;")

        text_layout = QtWidgets.QVBoxLayout()
        text_layout.addWidget(title)
        text_layout.addWidget(subtitle)

        layout.addWidget(icon)
        layout.addLayout(text_layout)
        layout.addStretch()

        self.setStyleSheet(
            "background-color: #161616; border-top-left-radius: 12px; border-top-right-radius: 12px;"
        )


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.client = ExpenseClient()

        self.setWindowTitle("B.I.D.O. Expense Tracker")
        self.resize(960, 640)
        self.setStyleSheet(self._carbon_palette())

        container = QtWidgets.QWidget()
        container_layout = QtWidgets.QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        self.header = CarbonHeader()
        container_layout.addWidget(self.header)

        body = QtWidgets.QWidget()
        body_layout = QtWidgets.QVBoxLayout(body)
        body_layout.setContentsMargins(24, 24, 24, 24)
        body_layout.setSpacing(16)

        self.total_label = QtWidgets.QLabel("Total: €0.00")
        self.total_label.setObjectName("TotalLabel")

        body_layout.addWidget(self.total_label)

        self.table = QtWidgets.QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Date", "Description", "Category", "Amount (€)"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QTableWidget.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        body_layout.addWidget(self.table)

        form_card = QtWidgets.QGroupBox("Add new expense")
        form_layout = QtWidgets.QGridLayout(form_card)
        form_layout.setHorizontalSpacing(16)
        form_layout.setVerticalSpacing(12)

        self.description_edit = QtWidgets.QLineEdit()
        self.description_edit.setPlaceholderText("Description")

        self.category_combo = QtWidgets.QComboBox()
        self.category_combo.addItems([
            "Housing",
            "Food",
            "Transportation",
            "Health",
            "Entertainment",
            "Utilities",
            "Miscellaneous",
        ])

        self.amount_spin = QtWidgets.QDoubleSpinBox()
        self.amount_spin.setRange(0, 1_000_000)
        self.amount_spin.setPrefix("€")
        self.amount_spin.setDecimals(2)
        self.amount_spin.setSingleStep(1.0)

        self.date_edit = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.date_edit.setCalendarPopup(True)

        self.add_button = QtWidgets.QPushButton("Add expense")
        self.add_button.clicked.connect(self.add_expense)

        self.delete_button = QtWidgets.QPushButton("Delete selected")
        self.delete_button.clicked.connect(self.delete_selected)
        self.delete_button.setObjectName("DangerButton")

        form_layout.addWidget(QtWidgets.QLabel("Description"), 0, 0)
        form_layout.addWidget(self.description_edit, 0, 1)
        form_layout.addWidget(QtWidgets.QLabel("Category"), 1, 0)
        form_layout.addWidget(self.category_combo, 1, 1)
        form_layout.addWidget(QtWidgets.QLabel("Amount"), 2, 0)
        form_layout.addWidget(self.amount_spin, 2, 1)
        form_layout.addWidget(QtWidgets.QLabel("Date"), 3, 0)
        form_layout.addWidget(self.date_edit, 3, 1)
        form_layout.addWidget(self.add_button, 4, 0)
        form_layout.addWidget(self.delete_button, 4, 1)

        body_layout.addWidget(form_card)

        container_layout.addWidget(body)

        footer = QtWidgets.QLabel("Powered by the IBM Carbon Design language")
        footer.setAlignment(QtCore.Qt.AlignCenter)
        footer.setObjectName("Footer")
        container_layout.addWidget(footer)

        self.setCentralWidget(container)

        self.refresh_expenses()

    def _carbon_palette(self) -> str:
        """Return a QSS stylesheet inspired by Carbon's g10 theme."""

        return """
        QWidget {
            background: #f4f4f4;
            color: #161616;
            font-family: "Segoe UI", "IBM Plex Sans", sans-serif;
        }

        QTableWidget {
            background: white;
            border: 1px solid #d0d0d0;
            border-radius: 8px;
            gridline-color: #e0e0e0;
            selection-background-color: #0f62fe;
            selection-color: white;
            alternate-background-color: #f2f2f2;
        }

        QHeaderView::section {
            background: #e5e5e5;
            font-weight: 600;
            padding: 8px;
            border: none;
        }

        QGroupBox {
            background: white;
            border: 1px solid #d0d0d0;
            border-radius: 12px;
            margin-top: 16px;
            padding: 16px;
            font-weight: 600;
        }

        QGroupBox:title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 8px;
            color: #0f62fe;
        }

        QPushButton {
            background: #0f62fe;
            color: white;
            padding: 10px 18px;
            border-radius: 8px;
            font-weight: 600;
        }

        QPushButton#DangerButton {
            background: #da1e28;
        }

        QPushButton:disabled {
            background: #8d8d8d;
            color: #c6c6c6;
        }

        QLabel#TotalLabel {
            font-size: 18pt;
            font-weight: 600;
        }

        QLabel#Footer {
            padding: 12px;
            background: #161616;
            color: #c6c6c6;
            border-bottom-left-radius: 12px;
            border-bottom-right-radius: 12px;
        }
        """

    def refresh_expenses(self) -> None:
        try:
            expenses = self.client.list_expenses()
        except requests.RequestException as exc:
            QtWidgets.QMessageBox.critical(
                self,
                "Connection error",
                f"Could not connect to the backend.\n{exc}\n\nMake sure backend.py is running.",
            )
            return

        self.table.setRowCount(0)
        total = 0.0
        for expense in expenses:
            row = self.table.rowCount()
            self.table.insertRow(row)
            date_item = QtWidgets.QTableWidgetItem(expense["date"])
            date_item.setData(QtCore.Qt.UserRole, expense["id"])
            self.table.setItem(row, 0, date_item)
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(expense["description"]))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(expense["category"]))
            amount_item = QtWidgets.QTableWidgetItem(f"€{expense['amount']:.2f}")
            amount_item.setData(QtCore.Qt.UserRole, expense["amount"])
            amount_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            self.table.setItem(row, 3, amount_item)
            self.table.setRowHeight(row, 36)
            total += float(expense["amount"])

        self.total_label.setText(f"Total: €{total:,.2f}")

    def add_expense(self) -> None:
        description = self.description_edit.text().strip()
        if not description:
            QtWidgets.QMessageBox.warning(self, "Validation", "Description cannot be empty")
            return

        payload = {
            "description": description,
            "category": self.category_combo.currentText(),
            "amount": float(self.amount_spin.value()),
            "date": self.date_edit.date().toString("yyyy-MM-dd"),
        }

        try:
            self.client.create_expense(payload)
        except requests.RequestException as exc:
            QtWidgets.QMessageBox.critical(self, "Error", f"Could not save expense:\n{exc}")
            return

        self.description_edit.clear()
        self.amount_spin.setValue(0.0)
        self.date_edit.setDate(QtCore.QDate.currentDate())
        self.refresh_expenses()

    def delete_selected(self) -> None:
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QtWidgets.QMessageBox.information(self, "Delete", "Select a row to delete")
            return

        row = selected_rows[0].row()

        # The backend requires the database ID. Store it using Qt.UserRole.
        expense_id = self.table.item(row, 0).data(QtCore.Qt.UserRole)

        if expense_id is None:
            QtWidgets.QMessageBox.warning(self, "Delete", "Cannot delete unsaved row")
            return

        confirm = QtWidgets.QMessageBox.question(
            self,
            "Confirm delete",
            "Delete the selected expense?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if confirm != QtWidgets.QMessageBox.Yes:
            return

        try:
            self.client.delete_expense(expense_id)
        except requests.RequestException as exc:
            QtWidgets.QMessageBox.critical(self, "Error", f"Could not delete expense:\n{exc}")
            return

        self.refresh_expenses()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # noqa: N802
        # smooth closing animation hook for Windows 11 feel
        self.setWindowOpacity(1.0)
        animation = QtCore.QPropertyAnimation(self, b"windowOpacity")
        animation.setDuration(200)
        animation.setStartValue(1.0)
        animation.setEndValue(0.0)
        animation.finished.connect(event.accept)
        animation.start(QtCore.QAbstractAnimation.DeleteWhenStopped)
        event.ignore()


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
