import sys
import os
import json
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QDateEdit,
    QMessageBox,
    QFrame,
    QFormLayout,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QScrollArea,
    QGridLayout,
    QComboBox,
)
from PyQt6.QtCore import Qt, QDate, QTimer
from PyQt6.QtGui import QImage, QPixmap, QFont, QIcon

from app.models.database import Database
from app.utils.config import DATA_DIR, ICONS_DIR


class ClassManagementTab(QWidget):
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.init_ui()

    def init_ui(self):
        """Initialize the class management UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Create tab widget for class registration and class list
        tab_widget = QTabWidget()

        # Class Registration Tab
        class_registration_tab = QWidget()
        registration_layout = QVBoxLayout(class_registration_tab)

        # Registration Form Frame
        form_frame = QFrame()
        form_layout = QFormLayout(form_frame)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_layout.setFormAlignment(Qt.AlignmentFlag.AlignCenter)

        # Class ID
        self.class_id_input = QLineEdit()
        self.class_id_input.setPlaceholderText("Enter unique class ID")
        form_layout.addRow("Class ID:", self.class_id_input)

        # Class Name
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter class name")
        form_layout.addRow("Class Name:", self.name_input)

        # Subject
        self.subject_input = QLineEdit()
        self.subject_input.setPlaceholderText("Enter subject")
        form_layout.addRow("Subject:", self.subject_input)

        # Teacher
        self.teacher_input = QLineEdit()
        self.teacher_input.setPlaceholderText("Enter teacher name")
        form_layout.addRow("Teacher:", self.teacher_input)

        # Room
        self.room_input = QLineEdit()
        self.room_input.setPlaceholderText("Enter room number")
        form_layout.addRow("Room:", self.room_input)

        # Class Type Dropdown
        self.class_type_combo = QComboBox()
        self.class_type_combo.addItems(
            [
                "Select Class Type",
                "Lecture",
                "Lab",
                "Seminar",
                "Workshop",
                "Online",
                "Hybrid",
            ]
        )
        form_layout.addRow("Class Type:", self.class_type_combo)

        # Buttons Layout
        button_layout = QHBoxLayout()

        # Save Button
        save_btn = QPushButton("Save Class")
        save_btn.setIcon(QIcon(str(ICONS_DIR / "save.png")))
        save_btn.clicked.connect(self.save_class)
        button_layout.addWidget(save_btn)

        # Clear Button
        clear_btn = QPushButton("Clear")
        clear_btn.setIcon(QIcon(str(ICONS_DIR / "clear.png")))
        clear_btn.clicked.connect(self.clear_form)
        button_layout.addWidget(clear_btn)

        form_layout.addRow(button_layout)
        registration_layout.addWidget(form_frame)

        # Class List Tab
        class_list_tab = QWidget()
        list_layout = QVBoxLayout(class_list_tab)

        # Table for class list
        self.class_table = QTableWidget()
        self.class_table.setColumnCount(5)
        self.class_table.setHorizontalHeaderLabels(
            ["Class ID", "Name", "Subject", "Teacher", "Actions"]
        )
        self.class_table.horizontalHeader().setStretchLastSection(True)

        # Refresh button for class list
        refresh_btn = QPushButton("Refresh Class List")
        refresh_btn.setIcon(QIcon(str(ICONS_DIR / "refresh.png")))
        refresh_btn.clicked.connect(self.load_classes)

        list_layout.addWidget(refresh_btn)
        list_layout.addWidget(self.class_table)

        # Add tabs to tab widget
        tab_widget.addTab(class_registration_tab, "Class Registration")
        tab_widget.addTab(class_list_tab, "Class List")

        main_layout.addWidget(tab_widget)

        # Load classes on startup
        self.load_classes()

    def save_class(self):
        """Save class information to the database."""
        # Validate inputs
        class_id = self.class_id_input.text().strip()
        name = self.name_input.text().strip()
        subject = self.subject_input.text().strip()
        teacher = self.teacher_input.text().strip()
        room = self.room_input.text().strip()
        class_type = self.class_type_combo.currentText()

        if not class_id or not name or not subject or not teacher:
            QMessageBox.warning(
                self,
                "Validation Error",
                "Class ID, Name, Subject, and Teacher are required.",
            )
            return

        try:
            # Save to database
            self.db.add_class(
                class_id=class_id,
                name=name,
                subject=subject,
                teacher=teacher,
                room=room,
                class_type=class_type,
            )

            QMessageBox.information(self, "Success", "Class added successfully!")
            self.clear_form()
            self.load_classes()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save class: {str(e)}")

    def clear_form(self):
        """Clear all input fields."""
        self.class_id_input.clear()
        self.name_input.clear()
        self.subject_input.clear()
        self.teacher_input.clear()
        self.room_input.clear()
        self.class_type_combo.setCurrentIndex(0)

    def load_classes(self):
        """Load classes from the database and populate the table."""
        try:
            # Clear existing rows
            self.class_table.setRowCount(0)

            # Execute query to get all classes
            cursor = self.db.connection.cursor()
            cursor.execute(
                "SELECT class_id, name, subject, teacher FROM classes ORDER BY name"
            )
            classes = cursor.fetchall()

            # Set row count
            self.class_table.setRowCount(len(classes))

            # Populate table
            for row, class_data in enumerate(classes):
                # Class ID
                id_item = QTableWidgetItem(str(class_data[0]))
                id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.class_table.setItem(row, 0, id_item)

                # Name
                name_item = QTableWidgetItem(str(class_data[1]))
                name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.class_table.setItem(row, 1, name_item)

                # Subject
                subject_item = QTableWidgetItem(str(class_data[2]))
                subject_item.setFlags(
                    subject_item.flags() & ~Qt.ItemFlag.ItemIsEditable
                )
                self.class_table.setItem(row, 2, subject_item)

                # Teacher
                teacher_item = QTableWidgetItem(str(class_data[3]))
                teacher_item.setFlags(
                    teacher_item.flags() & ~Qt.ItemFlag.ItemIsEditable
                )
                self.class_table.setItem(row, 3, teacher_item)

                # Actions (placeholder for future functionality)
                actions_item = QTableWidgetItem("View | Edit | Delete")
                actions_item.setFlags(
                    actions_item.flags() & ~Qt.ItemFlag.ItemIsEditable
                )
                self.class_table.setItem(row, 4, actions_item)

            # Resize columns to content
            self.class_table.resizeColumnsToContents()

        except Exception as e:
            QMessageBox.critical(
                self, "Database Error", f"Could not load classes: {str(e)}"
            )
