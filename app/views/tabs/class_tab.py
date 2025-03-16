from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QFormLayout,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QDialog,
    QDialogButtonBox,
    QTextEdit,
    QComboBox,
    QHeaderView,
    QGridLayout,
    QGroupBox,
    QCheckBox,
    QTimeEdit,
    QSpinBox,
    QMessageBox,
    QSplitter,
    QAbstractItemView,
)
from PyQt6.QtCore import Qt, QDate, QTime, QDateTime
from PyQt6.QtGui import QFont, QIcon

from app.models.database import Database
from app.utils.config import ICONS_DIR
import json
import uuid
import pathlib
import logging
import sqlite3


class TimePickerWidget(QWidget):
    """
    Custom time picker widget with hour and minute spinboxes
    and AM/PM selection for more intuitive time input.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Main layout
        layout = QHBoxLayout()

        # Hour Spinbox
        self.hour_spinbox = QSpinBox()
        self.hour_spinbox.setRange(1, 12)  # 12-hour format
        self.hour_spinbox.setValue(8)  # Default to 8

        # Minute Spinbox
        self.minute_spinbox = QSpinBox()
        self.minute_spinbox.setRange(0, 59)
        self.minute_spinbox.setValue(0)
        self.minute_spinbox.setSpecialValueText("00")

        # AM/PM Combo
        self.ampm_combo = QComboBox()
        self.ampm_combo.addItems(["AM", "PM"])

        # Add to layout
        layout.addWidget(QLabel("Hour:"))
        layout.addWidget(self.hour_spinbox)
        layout.addWidget(QLabel("Minute:"))
        layout.addWidget(self.minute_spinbox)
        layout.addWidget(self.ampm_combo)

        # Set layout
        self.setLayout(layout)

    def time(self):
        """
        Convert selected time to 24-hour format string.

        :return: Time as string in HH:mm format
        """
        hour = self.hour_spinbox.value()
        minute = self.minute_spinbox.value()
        ampm = self.ampm_combo.currentText()

        # Convert to 24-hour format
        if ampm == "PM" and hour != 12:
            hour += 12
        elif ampm == "AM" and hour == 12:
            hour = 0

        return f"{hour:02d}:{minute:02d}"

    def setTime(self, time_str):
        """
        Set time from a 24-hour format string.

        :param time_str: Time in HH:mm format
        """
        try:
            hour, minute = map(int, time_str.split(":"))

            # Convert to 12-hour format
            if hour == 0:
                display_hour = 12
                ampm = "AM"
            elif hour < 12:
                display_hour = hour
                ampm = "AM"
            elif hour == 12:
                display_hour = 12
                ampm = "PM"
            else:
                display_hour = hour - 12
                ampm = "PM"

            self.hour_spinbox.setValue(display_hour)
            self.minute_spinbox.setValue(minute)
            self.ampm_combo.setCurrentText(ampm)

        except (ValueError, IndexError):
            # Default to 8:00 AM if parsing fails
            self.hour_spinbox.setValue(8)
            self.minute_spinbox.setValue(0)
            self.ampm_combo.setCurrentText("AM")


class MultiDayScheduleWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.class_id = None

    def setup_ui(self):
        layout = QVBoxLayout()

        # Days of Week Checkboxes
        days_layout = QHBoxLayout()
        self.days_checkboxes = {}
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for day in days:
            checkbox = QCheckBox(day)
            days_layout.addWidget(checkbox)
            self.days_checkboxes[day] = checkbox
        layout.addLayout(days_layout)

        # Time Selection
        time_layout = QHBoxLayout()

        # Start Time
        start_time_label = QLabel("Start Time:")
        self.start_time_input = QTimeEdit()
        self.start_time_input.setDisplayFormat("HH:mm")
        time_layout.addWidget(start_time_label)
        time_layout.addWidget(self.start_time_input)

        # End Time
        end_time_label = QLabel("End Time:")
        self.end_time_input = QTimeEdit()
        self.end_time_input.setDisplayFormat("HH:mm")
        time_layout.addWidget(end_time_label)
        time_layout.addWidget(self.end_time_input)

        layout.addLayout(time_layout)

        # Schedules Table
        self.schedules_table = QTableWidget()
        self.schedules_table.setColumnCount(4)
        self.schedules_table.setHorizontalHeaderLabels(
            ["Days", "Start Time", "End Time", "Actions"]
        )
        layout.addWidget(self.schedules_table)

        # Add Schedule Button
        self.add_schedule_btn = QPushButton("Add Schedule")
        self.add_schedule_btn.clicked.connect(self.add_schedule)
        layout.addWidget(self.add_schedule_btn)

        self.setLayout(layout)

    def add_schedule(self):
        """Add a new schedule to the table and database."""
        # Get selected days
        selected_days = [
            day
            for day, checkbox in self.days_checkboxes.items()
            if checkbox.isChecked()
        ]

        if not selected_days:
            QMessageBox.warning(self, "Invalid Input", "Please select at least one day")
            return

        # Get start and end times
        start_time = self.start_time_input.time().toString("HH:mm")
        end_time = self.end_time_input.time().toString("HH:mm")

        # Validate times
        if start_time >= end_time:
            QMessageBox.warning(
                self, "Invalid Time", "Start time must be before end time"
            )
            return

        # Add to table
        row = self.schedules_table.rowCount()
        self.schedules_table.insertRow(row)
        self.schedules_table.setItem(row, 0, QTableWidgetItem(", ".join(selected_days)))
        self.schedules_table.setItem(row, 1, QTableWidgetItem(start_time))
        self.schedules_table.setItem(row, 2, QTableWidgetItem(end_time))

        # Add delete button
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(lambda: self.delete_schedule(row))
        self.schedules_table.setCellWidget(row, 3, delete_btn)

    def delete_schedule(self, row):
        """Delete a schedule from the table."""
        self.schedules_table.removeRow(row)

    def get_schedules(self):
        """Retrieve all schedules from the table."""
        schedules = []
        for row in range(self.schedules_table.rowCount()):
            days = self.schedules_table.item(row, 0).text()
            start_time = self.schedules_table.item(row, 1).text()
            end_time = self.schedules_table.item(row, 2).text()
            schedules.append(
                {"days": days, "start_time": start_time, "end_time": end_time}
            )
        return schedules

    def reset(self):
        """Reset the schedule widget."""
        # Uncheck all day checkboxes
        for checkbox in self.days_checkboxes.values():
            checkbox.setChecked(False)

        # Reset time inputs to current time
        current_time = QTime.currentTime()
        self.start_time_input.setTime(current_time)
        self.end_time_input.setTime(current_time)

        # Clear schedules table
        self.schedules_table.setRowCount(0)


class ClassManagementTab(QWidget):
    def __init__(self):
        super().__init__()

        # Main layout
        main_layout = QVBoxLayout()

        # Create tab widget
        self.tab_widget = QTabWidget()

        # Create sub-tabs
        self.class_list_tab = ClassListTab()
        self.class_registration_tab = ClassRegistrationTab()

        # Add tabs to tab widget
        self.tab_widget.addTab(self.class_list_tab, "Class List")
        self.tab_widget.addTab(self.class_registration_tab, "Class Registration")

        # Add tab widget to main layout
        main_layout.addWidget(self.tab_widget)

        # Set main layout
        self.setLayout(main_layout)


class ClassListTab(QWidget):
    def __init__(self):
        super().__init__()

        # Database connection
        self.db = Database()

        # Main layout
        layout = QVBoxLayout(self)

        # Class Table
        self.class_table = QTableWidget()
        self.class_table.setColumnCount(5)
        self.class_table.setHorizontalHeaderLabels(
            ["Class ID", "Name", "Subject", "Teacher", "Actions"]
        )
        self.class_table.horizontalHeader().setStretchLastSection(True)

        # Load Classes Button
        load_button = QPushButton("Refresh Class List")
        load_button.clicked.connect(self.load_classes)

        # Action Buttons
        action_layout = QHBoxLayout()
        action_buttons = [
            ("view", "View Details", "view.png"),
            ("edit", "Edit", "edit.png"),
            ("delete", "Delete", "delete.png"),
        ]

        # Add buttons to layout
        layout.addWidget(load_button)
        layout.addWidget(self.class_table)

        # Connect table double-click to view details
        self.class_table.doubleClicked.connect(self.view_class_details)

        # Initial load of classes
        self.load_classes()

    def load_classes(self):
        """Load classes from the database and populate the table."""
        try:
            # Clear existing rows
            self.class_table.setRowCount(0)

            # Execute query to fetch all classes
            cursor = self.db.connection.cursor()
            cursor.execute(
                """
                SELECT
                    class_id,
                    name,
                    subject,
                    teacher
                FROM classes
                ORDER BY created_at DESC
            """
            )
            classes = cursor.fetchall()

            # Log raw database results for debugging
            logging.info(f"Raw classes data: {classes}")
            logging.info(f"Number of classes retrieved: {len(classes)}")

            # Populate table
            for row, class_data in enumerate(classes):
                # Detailed logging for each class data
                logging.info(f"Processing class data: {class_data}")
                logging.info(f"Class data type: {type(class_data)}")

                self.class_table.insertRow(row)

                # Robust data conversion with type checking and logging
                try:
                    # Convert to list first to ensure mutability
                    class_data_list = list(class_data)

                    # Ensure each item is a string, with type logging
                    processed_data = []
                    for item in class_data_list:
                        if item is None:
                            processed_data.append("")
                        elif isinstance(item, (int, float)):
                            processed_data.append(str(item))
                        elif isinstance(item, str):
                            processed_data.append(item)
                        else:
                            logging.warning(
                                f"Unexpected data type: {type(item)} for item {item}"
                            )
                            processed_data.append(str(item))

                    # Convert to tuple for consistency
                    class_data = tuple(processed_data)

                    # Logging processed data
                    logging.info(f"Processed class data: {class_data}")
                    logging.info(
                        f"Processed data types: {[type(x) for x in class_data]}"
                    )

                except Exception as conversion_error:
                    logging.error(f"Error converting class data: {conversion_error}")
                    logging.error(f"Problematic data: {class_data}")
                    continue

                # Safely add items to table
                for col, value in enumerate(class_data[:4]):  # Limit to first 4 columns
                    item = QTableWidgetItem(str(value))
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.class_table.setItem(row, col, item)

                # Actions column
                actions_item = QTableWidgetItem("View | Edit | Delete")
                actions_item.setFlags(
                    actions_item.flags() & ~Qt.ItemFlag.ItemIsEditable
                )
                self.class_table.setItem(row, 4, actions_item)

            # Resize columns to content
            self.class_table.resizeColumnsToContents()

        except Exception as e:
            error_message = f"Failed to load classes: {str(e)}"
            logging.error(error_message, exc_info=True)  # Log full traceback
            QMessageBox.critical(self, "Database Error", error_message)

    def view_class_details(self, index=None):
        """View details of a selected class."""
        try:
            # Get selected class
            if index is not None:
                # If called from table row selection
                row = index.row()
                class_id_item = self.class_table.item(row, 0)
            else:
                # If called from button or other method
                selected_items = self.class_table.selectedItems()
                if not selected_items:
                    raise ValueError("No class selected")
                class_id_item = selected_items[0]

            if not class_id_item:
                raise ValueError("No valid class ID found")

            class_id = class_id_item.text()
            logging.info(f"Attempting to view details for class ID: {class_id}")

            # Fetch full class details
            cursor = self.db.connection.cursor()
            cursor.execute(
                """
                SELECT
                    class_id, name, subject, teacher,
                    room, class_type, description, max_capacity
                FROM classes
                WHERE class_id = ?
            """,
                (class_id,),
            )

            class_data = cursor.fetchone()

            if not class_data:
                logging.warning(f"No class details found for class ID: {class_id}")
                QMessageBox.warning(
                    self, "Not Found", f"No details found for class {class_id}"
                )
                return

            # Fetch schedules for this class
            cursor.execute(
                """
                SELECT days, start_time, end_time
                FROM class_schedules
                WHERE class_id = ?
            """,
                (class_id,),
            )

            schedule_results = cursor.fetchall()
            logging.info(
                f"Found {len(schedule_results)} schedules for class {class_id}"
            )

            # Convert to dictionary for dialog
            class_details = {
                "class_id": class_data[0],
                "name": class_data[1],
                "subject": class_data[2],
                "teacher": class_data[3],
                "room": class_data[4],
                "class_type": class_data[5],
                "description": class_data[6],
                "max_capacity": class_data[7],
                "schedules": [
                    {
                        "days": schedule[0],
                        "start_time": schedule[1],
                        "end_time": schedule[2],
                    }
                    for schedule in schedule_results
                ],
            }

            # Open class details dialog
            details_dialog = ClassDetailsDialog(class_details, self)
            details_dialog.exec()

        except Exception as e:
            error_message = f"Could not fetch class details: {str(e)}"
            logging.error(error_message, exc_info=True)
            print(error_message)  # Log to console
            QMessageBox.critical(self, "Fetch Error", error_message)


class ClassRegistrationTab(QWidget):
    def __init__(self):
        super().__init__()

        # Database connection
        self.db = Database()

        # Main layout
        layout = QVBoxLayout(self)

        # Form layout
        form_layout = QFormLayout()

        # Input fields
        self.class_id = QLineEdit()
        self.class_id.setReadOnly(True)

        # Generate unique class ID on initialization
        self.generate_class_id()

        self.name = QLineEdit()
        self.name.setPlaceholderText("Enter class name")

        self.subject = QLineEdit()
        self.subject.setPlaceholderText("Enter subject")

        self.teacher = QLineEdit()
        self.teacher.setPlaceholderText("Enter teacher name")

        self.room = QLineEdit()
        self.room.setPlaceholderText("Enter room number")

        self.class_type = QComboBox()
        self.class_type.addItems(["Regular", "Workshop", "Seminar", "Online"])

        # Max Capacity input
        self.max_capacity_input = QSpinBox()
        self.max_capacity_input.setRange(1, 100)
        self.max_capacity_input.setValue(30)

        # Multiple Day Schedule Widget
        self.schedule_widget = MultiDayScheduleWidget()

        self.description = QTextEdit()
        self.description.setPlaceholderText("Enter class description")

        # Add fields to form layout
        form_layout.addRow("Class ID:", self.class_id)
        form_layout.addRow("Class Name:", self.name)
        form_layout.addRow("Subject:", self.subject)
        form_layout.addRow("Teacher:", self.teacher)
        form_layout.addRow("Room:", self.room)
        form_layout.addRow("Class Type:", self.class_type)
        form_layout.addRow("Max Capacity:", self.max_capacity_input)
        form_layout.addRow("Schedule:", self.schedule_widget)
        form_layout.addRow("Description:", self.description)

        # Add form layout to main layout
        layout.addLayout(form_layout)

        # Buttons
        button_layout = QHBoxLayout()

        register_button = QPushButton("Register Class")
        register_button.clicked.connect(self.register_class)

        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self.clear_form)

        button_layout.addWidget(register_button)
        button_layout.addWidget(clear_button)

        layout.addLayout(button_layout)

    def generate_class_id(self):
        """Generate a unique class ID."""
        unique_id = str(uuid.uuid4())[:8].upper()
        self.class_id.setText(f"CLASS-{unique_id}")

        # Update schedule widget's class ID
        if hasattr(self, "schedule_widget"):
            self.schedule_widget.class_id = self.class_id.text()

    def register_class(self):
        """Register a new class in the database."""
        try:
            # Validate inputs
            class_id = self.class_id.text().strip()
            name = self.name.text().strip()
            subject = self.subject.text().strip()
            teacher = self.teacher.text().strip()

            # Comprehensive input validation
            if not class_id:
                QMessageBox.warning(self, "Validation Error", "Class ID is missing")
                return

            if not name:
                QMessageBox.warning(self, "Validation Error", "Class name is required")
                return

            if not subject:
                QMessageBox.warning(self, "Validation Error", "Subject is required")
                return

            if not teacher:
                QMessageBox.warning(
                    self, "Validation Error", "Teacher name is required"
                )
                return

            # Prepare class data
            class_data = {
                "class_id": class_id,
                "name": name,
                "subject": subject,
                "teacher": teacher,
                "room": self.room.text().strip(),
                "class_type": self.class_type.currentText(),
                "description": self.description.toPlainText().strip(),
                "max_capacity": self.max_capacity_input.value(),
            }

            # Start database transaction
            cursor = self.db.connection.cursor()

            try:
                # Begin explicit transaction
                cursor.execute("BEGIN TRANSACTION")

                # Insert class details
                cursor.execute(
                    """
                    INSERT INTO classes (
                        class_id, name, subject, teacher,
                        room, class_type, description, max_capacity,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                    (
                        class_data["class_id"],
                        class_data["name"],
                        class_data["subject"],
                        class_data["teacher"],
                        class_data["room"],
                        class_data["class_type"],
                        class_data["description"],
                        class_data["max_capacity"],
                    ),
                )

                # Get schedules
                try:
                    schedules = self.schedule_widget.get_schedules()
                except ValueError as ve:
                    # No schedules is not an error, just log it
                    logging.info(f"No schedules to add: {ve}")
                    schedules = []

                # Insert schedules if available
                for schedule in schedules:
                    # Validate schedule data
                    days = schedule.get("days", "").strip()
                    start_time = schedule.get("start_time", "").strip()
                    end_time = schedule.get("end_time", "").strip()

                    if not days or not start_time or not end_time:
                        logging.warning(f"Skipping invalid schedule: {schedule}")
                        continue

                    # Insert schedule
                    cursor.execute(
                        """
                        INSERT INTO class_schedules (
                            class_id, days, start_time, end_time
                        ) VALUES (?, ?, ?, ?)
                    """,
                        (class_data["class_id"], days, start_time, end_time),
                    )

                # Commit transaction
                self.db.connection.commit()

                # Update schedule widget's class ID
                self.schedule_widget.class_id = class_data["class_id"]

                # Show success message
                QMessageBox.information(
                    self,
                    "Success",
                    f"Class {class_data['name']} registered successfully with {len(schedules)} schedule(s)!",
                )

                # Clear form after successful registration
                self.clear_form()

            except sqlite3.IntegrityError as ie:
                # Rollback transaction on integrity error
                self.db.connection.rollback()

                # Log the specific error
                logging.error(f"Class registration integrity error: {ie}")

                # Show detailed error message
                QMessageBox.critical(
                    self,
                    "Integrity Error",
                    f"Could not register class. Possible duplicate or constraint violation: {str(ie)}",
                )

            except Exception as inner_error:
                # Rollback transaction on any error
                self.db.connection.rollback()

                # Log the specific error
                logging.error(f"Class registration error: {inner_error}")

                # Show detailed error message
                QMessageBox.critical(
                    self,
                    "Registration Error",
                    f"Could not register class. Error: {str(inner_error)}",
                )

        except Exception as outer_error:
            # Handle any unexpected errors
            logging.error(f"Unexpected class registration error: {outer_error}")
            QMessageBox.critical(
                self,
                "Unexpected Error",
                f"An unexpected error occurred: {str(outer_error)}",
            )

    def clear_form(self):
        """Clear all form fields."""
        # Generate new unique class ID
        self.generate_class_id()

        # Clear other fields
        self.name.clear()
        self.subject.clear()
        self.teacher.clear()
        self.room.clear()
        self.class_type.setCurrentIndex(0)
        self.description.clear()
        self.max_capacity_input.setValue(30)

        # Clear schedules
        self.schedule_widget.reset()


class ClassDetailsDialog(QDialog):
    def __init__(self, class_data=None, parent=None):
        """
        Initialize the Class Details Dialog

        :param class_data: Dictionary containing existing class data
        :param parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Class Details")
        self.class_data = class_data or {}
        self.db = Database()  # Add database connection

        # Increase dialog size with better proportions
        self.resize(1000, 700)  # Slightly reduced height

        # Main layout
        main_layout = QVBoxLayout(self)

        # Create splitter for better layout management
        main_splitter = QSplitter(Qt.Orientation.Vertical)

        # Top section for class details
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)

        # Left side for class information
        left_form_layout = QFormLayout()

        # Class ID (auto-generated if not provided)
        self.class_id = QLineEdit()
        self.class_id.setPlaceholderText("Auto-generated if left blank")

        # Class Name
        self.name = QLineEdit()
        self.name.setPlaceholderText("Enter class name")

        # Subject
        self.subject = QLineEdit()
        self.subject.setPlaceholderText("Enter subject")

        # Teacher
        self.teacher = QLineEdit()
        self.teacher.setPlaceholderText("Enter teacher name")

        # Room
        self.room = QLineEdit()
        self.room.setPlaceholderText("Enter room number")

        # Class Type
        self.class_type = QComboBox()
        self.class_type.addItems(
            ["Lecture", "Lab", "Seminar", "Workshop", "Online", "Hybrid"]
        )

        # Max Capacity
        self.max_capacity_input = QSpinBox()
        self.max_capacity_input.setRange(1, 200)
        self.max_capacity_input.setValue(30)

        # Description
        self.description = QTextEdit()
        self.description.setPlaceholderText("Enter class description")

        # Add fields to left form layout
        left_form_layout.addRow("Class ID:", self.class_id)
        left_form_layout.addRow("Class Name:", self.name)
        left_form_layout.addRow("Subject:", self.subject)
        left_form_layout.addRow("Teacher:", self.teacher)
        left_form_layout.addRow("Room:", self.room)
        left_form_layout.addRow("Class Type:", self.class_type)
        left_form_layout.addRow("Max Capacity:", self.max_capacity_input)

        # Right side for schedule
        right_schedule_layout = QVBoxLayout()

        # Schedule Widget with larger size
        self.schedule_widget = MultiDayScheduleWidget()
        self.schedule_widget.setMinimumHeight(200)  # Reduced height
        right_schedule_layout.addWidget(QLabel("Class Schedule:"))
        right_schedule_layout.addWidget(self.schedule_widget)

        # Description section
        right_schedule_layout.addWidget(QLabel("Description:"))
        right_schedule_layout.addWidget(self.description)

        # Add layouts to top section
        top_layout.addLayout(left_form_layout, 1)
        top_layout.addLayout(right_schedule_layout, 2)

        # Add top widget to splitter
        main_splitter.addWidget(top_widget)

        # Bottom section for students list
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)

        # Students List Widget with improved size and readability
        self.students_list = QTableWidget()
        self.students_list.setColumnCount(3)
        self.students_list.setHorizontalHeaderLabels(["Student ID", "Name", "Actions"])
        self.students_list.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.students_list.setMinimumHeight(200)  # Reduced height

        # Add students button
        add_student_btn = QPushButton("Add Student")
        add_student_btn.clicked.connect(self.add_student)

        # Add students section to bottom layout
        bottom_layout.addWidget(QLabel("Enrolled Students:"))
        bottom_layout.addWidget(self.students_list)
        bottom_layout.addWidget(add_student_btn)

        # Add bottom widget to splitter
        main_splitter.addWidget(bottom_widget)

        # Set splitter sizes to distribute space
        main_splitter.setSizes([400, 200])

        # Add splitter to main layout
        main_layout.addWidget(main_splitter)

        # Buttons - use a horizontal layout to spread them out
        button_layout = QHBoxLayout()
        button_layout.addStretch()  # Push buttons to the right

        # Create buttons
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_class_details)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        # Add buttons to layout
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)

        # Add button layout to main layout
        main_layout.addLayout(button_layout)

        # Populate existing data if provided
        if class_data:
            self.populate_existing_data(class_data)

        # Populate students list
        self.load_enrolled_students()

    def populate_existing_data(self, class_data):
        """
        Populate dialog fields with existing class data

        :param class_data: Dictionary of existing class details
        """
        # Set class ID (read-only for existing classes)
        self.class_id.setText(str(class_data.get("class_id", "")))
        self.class_id.setReadOnly(True)

        # Populate other fields
        self.name.setText(str(class_data.get("name", "")))
        self.subject.setText(str(class_data.get("subject", "")))
        self.teacher.setText(str(class_data.get("teacher", "")))
        self.room.setText(str(class_data.get("room", "")))
        self.class_type.setCurrentText(str(class_data.get("class_type", "Lecture")))
        self.max_capacity_input.setValue(int(class_data.get("max_capacity", 30)))
        self.description.setText(str(class_data.get("description", "")))

        # Populate schedules
        existing_schedules = class_data.get("schedules", [])
        if existing_schedules:
            # Reset existing schedules
            self.schedule_widget.schedules_table.setRowCount(0)

            # Add each existing schedule
            for schedule in existing_schedules:
                row = self.schedule_widget.schedules_table.rowCount()
                self.schedule_widget.schedules_table.insertRow(row)

                # Set days, start time, and end time
                days = schedule.get("days", "")
                start_time = schedule.get("start_time", "")
                end_time = schedule.get("end_time", "")

                self.schedule_widget.schedules_table.setItem(
                    row, 0, QTableWidgetItem(days)
                )
                self.schedule_widget.schedules_table.setItem(
                    row, 1, QTableWidgetItem(start_time)
                )
                self.schedule_widget.schedules_table.setItem(
                    row, 2, QTableWidgetItem(end_time)
                )

                # Add delete button
                delete_btn = QPushButton("Delete")
                delete_btn.clicked.connect(
                    lambda _, r=row: self.schedule_widget.delete_schedule(r)
                )
                self.schedule_widget.schedules_table.setCellWidget(row, 3, delete_btn)

    def load_enrolled_students(self):
        """
        Load students enrolled in this class
        """
        try:
            # Clear existing rows
            self.students_list.setRowCount(0)

            # Only proceed if we have a class ID
            if not self.class_id.text():
                return

            # Fetch enrolled students
            cursor = self.db.connection.cursor()
            cursor.execute(
                """
                SELECT s.student_id, s.first_name || ' ' || s.last_name as full_name
                FROM students s
                JOIN class_enrollments ce ON s.student_id = ce.student_id
                WHERE ce.class_id = ?
            """,
                (self.class_id.text(),),
            )

            students = cursor.fetchall()

            # Populate students list
            for row, (student_id, full_name) in enumerate(students):
                self.students_list.insertRow(row)
                self.students_list.setItem(row, 0, QTableWidgetItem(student_id))
                self.students_list.setItem(row, 1, QTableWidgetItem(full_name))

                # Remove student button
                remove_btn = QPushButton("Remove")
                remove_btn.clicked.connect(
                    lambda _, sid=student_id: self.remove_student(sid)
                )
                self.students_list.setCellWidget(row, 2, remove_btn)

        except sqlite3.Error as e:
            logging.error(f"Error loading enrolled students: {e}")
            QMessageBox.critical(self, "Database Error", str(e))

    def add_student(self):
        """Add student(s) to the class."""
        try:
            # Verify class ID exists
            if not self.class_id.text():
                QMessageBox.warning(
                    self, "Error", "No class selected. Please select a class first."
                )
                return

            # Get current enrolled students
            cursor = self.db.connection.cursor()
            cursor.execute(
                """
                SELECT student_id FROM class_enrollments
                WHERE class_id = ?
            """,
                (self.class_id.text(),),
            )
            existing_students = [s[0] for s in cursor.fetchall()]

            # Create selection dialog
            dialog = StudentSelectionDialog(
                existing_students=existing_students, parent=self
            )

            # Execute dialog
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Get selected students
                selected_students = dialog.get_selected_students()

                if not selected_students:
                    QMessageBox.warning(
                        self,
                        "No Students Selected",
                        "Please select at least one student to add.",
                    )
                    return

                # Enroll selected students
                added_count = 0
                for student_id in selected_students:
                    try:
                        cursor.execute(
                            """
                            INSERT INTO class_enrollments (student_id, class_id)
                            VALUES (?, ?)
                        """,
                            (student_id, self.class_id.text()),
                        )
                        added_count += 1
                    except sqlite3.IntegrityError:
                        # Skip if student is already enrolled
                        continue

                # Commit changes
                self.db.connection.commit()

                # Refresh students list
                self.load_enrolled_students()

                # Show success message
                if added_count > 0:
                    QMessageBox.information(
                        self, "Success", f"{added_count} student(s) added to class"
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "No Students Added",
                        "All selected students are already enrolled in this class.",
                    )

        except sqlite3.Error as e:
            logging.error(f"Error adding student: {e}")
            QMessageBox.critical(self, "Database Error", str(e))

    def remove_student(self, student_id):
        """
        Remove a student from the class

        :param student_id: ID of the student to remove
        """
        try:
            # Confirm removal
            reply = QMessageBox.question(
                self,
                "Confirm Removal",
                "Are you sure you want to remove this student from the class?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            # Proceed only if user confirms
            if reply == QMessageBox.StandardButton.Yes:
                # Remove student from class enrollments
                cursor = self.db.connection.cursor()
                cursor.execute(
                    """
                    DELETE FROM class_enrollments
                    WHERE student_id = ? AND class_id = ?
                """,
                    (student_id, self.class_id.text()),
                )

                # Commit changes
                self.db.connection.commit()

                # Refresh students list
                self.load_enrolled_students()

                # Show success message
                QMessageBox.information(
                    self,
                    "Student Removed",
                    "Student successfully removed from the class.",
                )

        except sqlite3.Error as e:
            # Handle database errors
            logging.error(f"Error removing student: {e}")
            QMessageBox.critical(self, "Database Error", str(e))

    def save_class_details(self):
        """
        Save class details to the database
        """
        try:
            # Validate required fields
            if not self.name.text().strip():
                QMessageBox.warning(self, "Validation Error", "Class name is required")
                return

            if not self.teacher.text().strip():
                QMessageBox.warning(
                    self, "Validation Error", "Teacher name is required"
                )
                return

            # Prepare class data
            class_data = {
                "class_id": self.class_id.text().strip(),
                "name": self.name.text().strip(),
                "subject": self.subject.text().strip(),
                "teacher": self.teacher.text().strip(),
                "room": self.room.text().strip(),
                "class_type": self.class_type.currentText(),
                "description": self.description.toPlainText().strip(),
                "max_capacity": self.max_capacity_input.value(),
                "schedules": self.schedule_widget.get_schedules(),
            }

            # Start database transaction
            cursor = self.db.connection.cursor()
            cursor.execute("BEGIN TRANSACTION")

            # Update class details
            cursor.execute(
                """
                UPDATE classes
                SET
                    name = ?,
                    subject = ?,
                    teacher = ?,
                    room = ?,
                    class_type = ?,
                    description = ?,
                    max_capacity = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE class_id = ?
            """,
                (
                    class_data["name"],
                    class_data["subject"],
                    class_data["teacher"],
                    class_data["room"],
                    class_data["class_type"],
                    class_data["description"],
                    class_data["max_capacity"],
                    class_data["class_id"],
                ),
            )

            # Remove existing schedules
            cursor.execute(
                """
                DELETE FROM class_schedules
                WHERE class_id = ?
            """,
                (class_data["class_id"],),
            )

            # Insert new schedules
            for schedule in class_data["schedules"]:
                cursor.execute(
                    """
                    INSERT INTO class_schedules (
                        class_id, days, start_time, end_time
                    ) VALUES (?, ?, ?, ?)
                """,
                    (
                        class_data["class_id"],
                        schedule.get("days", ""),
                        schedule.get("start_time", ""),
                        schedule.get("end_time", ""),
                    ),
                )

            # Commit transaction
            self.db.connection.commit()

            # Close dialog
            QMessageBox.information(
                self, "Success", "Class details updated successfully!"
            )
            self.accept()

        except sqlite3.Error as e:
            # Rollback transaction
            self.db.connection.rollback()

            logging.error(f"Error saving class details: {e}")
            QMessageBox.critical(self, "Database Error", str(e))


class StudentSelectionDialog(QDialog):
    def __init__(self, existing_students=None, parent=None):
        """
        Dialog for selecting multiple students to add to a class.

        :param existing_students: List of students already in the class
        :param parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Add Students to Class")
        self.resize(1000, 700)  # Large dialog size

        # Main layout
        main_layout = QVBoxLayout(self)

        # Database connection
        self.db = Database()

        # Existing students to exclude
        self.existing_students = existing_students or []

        # Search and filter section
        search_layout = QHBoxLayout()

        # Search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search students by name, ID, or email")
        self.search_input.textChanged.connect(self.filter_students)
        search_layout.addWidget(QLabel("Search:"))
        search_layout.addWidget(self.search_input)

        # Filter by gender
        self.gender_filter = QComboBox()
        self.gender_filter.addItems(["All Genders", "Male", "Female", "Other"])
        self.gender_filter.currentTextChanged.connect(self.filter_students)
        search_layout.addWidget(QLabel("Gender:"))
        search_layout.addWidget(self.gender_filter)

        main_layout.addLayout(search_layout)

        # Students table with checkboxes
        self.students_table = QTableWidget()
        self.students_table.setColumnCount(5)
        self.students_table.setHorizontalHeaderLabels(
            ["", "Student ID", "Name", "Email", "Gender"]
        )

        # Make first column a checkbox
        self.students_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.students_table.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )

        main_layout.addWidget(self.students_table)

        # Buttons
        button_layout = QHBoxLayout()

        # Select All checkbox
        self.select_all_checkbox = QCheckBox("Select All")
        self.select_all_checkbox.stateChanged.connect(self.toggle_all_students)
        button_layout.addWidget(self.select_all_checkbox)

        button_layout.addStretch()

        # Add and Cancel buttons
        add_button = QPushButton("Add Selected Students")
        add_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(add_button)
        button_layout.addWidget(cancel_button)

        main_layout.addLayout(button_layout)

        # Load students
        self.load_students()

    def load_students(self):
        """Load all students into the table."""
        # Get all students
        students = self.db.get_students()

        # Set table rows
        self.students_table.setRowCount(len(students))

        for row, student in enumerate(students):
            # Checkbox column
            checkbox = QCheckBox()
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            self.students_table.setCellWidget(row, 0, checkbox_widget)

            # Disable checkbox for existing students
            student_id = student.get("student_id", "")
            if student_id in self.existing_students:
                checkbox.setEnabled(False)
                checkbox.setToolTip("Already in class")

            # Student ID
            self.students_table.setItem(row, 1, QTableWidgetItem(student_id))

            # Name
            full_name = (
                student.get("name")
                or f"{student.get('first_name', '')} {student.get('last_name', '')}".strip()
            )
            self.students_table.setItem(row, 2, QTableWidgetItem(full_name))

            # Email
            self.students_table.setItem(
                row, 3, QTableWidgetItem(student.get("email", ""))
            )

            # Gender
            self.students_table.setItem(
                row, 4, QTableWidgetItem(student.get("gender", ""))
            )

    def filter_students(self):
        """Filter students based on search and gender."""
        search_term = self.search_input.text().lower()
        gender_filter = self.gender_filter.currentText()

        for row in range(self.students_table.rowCount()):
            # Get row data
            student_id = self.students_table.item(row, 1).text().lower()
            name = self.students_table.item(row, 2).text().lower()
            email = self.students_table.item(row, 3).text().lower()
            gender = self.students_table.item(row, 4).text()

            # Check search conditions
            search_match = (
                search_term in student_id or search_term in name or search_term in email
            )

            # Check gender filter
            gender_match = gender_filter == "All Genders" or gender_filter == gender

            # Show/hide row
            self.students_table.setRowHidden(row, not (search_match and gender_match))

    def toggle_all_students(self, state):
        """Toggle selection of all students."""
        for row in range(self.students_table.rowCount()):
            checkbox_widget = self.students_table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox and checkbox.isEnabled():
                    checkbox.setChecked(state == Qt.CheckState.Checked)

    def get_selected_students(self):
        """
        Get list of selected student IDs.

        :return: List of selected student IDs
        """
        selected_students = []
        for row in range(self.students_table.rowCount()):
            checkbox_widget = self.students_table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    student_id = self.students_table.item(row, 1).text()
                    selected_students.append(student_id)
        return selected_students
