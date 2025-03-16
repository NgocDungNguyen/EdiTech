import os
import cv2
import logging
import sqlite3
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QComboBox,
    QDateEdit,
    QMessageBox,
    QGroupBox,
    QGridLayout,
    QLineEdit,
    QDialog,
    QInputDialog,
    QFormLayout,
    QSpinBox,
)
from PyQt6.QtGui import QFont, QColor, QIcon, QImage, QPixmap
from PyQt6.QtCore import Qt, QDate, QTimer

from app.models.database import Database
from app.utils.face_recognition import FaceRecognitionManager
from app.utils.config import DATA_DIR, ICONS_DIR


class AttendanceTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Database and face recognition
        self.db = Database()
        self.face_recognition_manager = FaceRecognitionManager(
            os.path.join(DATA_DIR, "edison_vision.db")
        )

        # Initialize UI
        self.init_ui()

    def init_ui(self):
        # Main layout
        main_layout = QVBoxLayout()

        # Top section with class and date selection
        top_section = QHBoxLayout()

        # Class Selection
        class_group = QGroupBox("Select Class")
        class_layout = QVBoxLayout()

        self.class_selector = QComboBox()
        self.class_selector.addItem("Select Class")
        self.class_selector.currentIndexChanged.connect(self.load_attendance_records)

        # Add refresh button for classes
        refresh_btn = QPushButton("↻")
        refresh_btn.setMaximumWidth(30)
        refresh_btn.clicked.connect(self.load_classes)
        refresh_btn.setToolTip("Refresh class list")

        class_layout.addWidget(self.class_selector)
        class_layout.addWidget(refresh_btn)
        class_group.setLayout(class_layout)
        top_section.addWidget(class_group)

        # Date Selection
        date_group = QGroupBox("Select Date")
        date_layout = QVBoxLayout()

        self.date_selector = QDateEdit()
        self.date_selector.setDate(QDate.currentDate())
        self.date_selector.setCalendarPopup(True)
        self.date_selector.dateChanged.connect(self.load_attendance_records)

        date_layout.addWidget(self.date_selector)
        date_group.setLayout(date_layout)
        top_section.addWidget(date_group)

        main_layout.addLayout(top_section)

        # Attendance Actions Section
        actions_layout = QHBoxLayout()

        # Face Recognition Check-in Button
        self.face_check_in_btn = QPushButton("Face Check-in")
        self.face_check_in_btn.setIcon(QIcon(str(ICONS_DIR / "face_recognition.png")))
        self.face_check_in_btn.clicked.connect(self.perform_face_check_in)
        actions_layout.addWidget(self.face_check_in_btn)

        # Manual Check-in Button
        self.manual_check_in_btn = QPushButton("Manual Check-in")
        self.manual_check_in_btn.setIcon(QIcon(str(ICONS_DIR / "manual_entry.png")))
        self.manual_check_in_btn.clicked.connect(self.manual_check_in)
        actions_layout.addWidget(self.manual_check_in_btn)

        # Pre-Check-In Button
        self.pre_checkin_btn = QPushButton("Set Pre-Check-In")
        self.pre_checkin_btn.setIcon(QIcon(str(ICONS_DIR / "clock.png")))
        self.pre_checkin_btn.clicked.connect(self.setup_pre_checkin)
        actions_layout.addWidget(self.pre_checkin_btn)

        main_layout.addLayout(actions_layout)

        # Add status label
        self.status_label = QLabel("No records loaded")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-style: italic; color: #666;")
        main_layout.addWidget(self.status_label)

        # Attendance Table
        self.attendance_table = QTableWidget()
        self.attendance_table.setColumnCount(6)
        self.attendance_table.setHorizontalHeaderLabels(
            ["Student ID", "Name", "Check-in Time", "Status", "Location", "Notes"]
        )
        self.attendance_table.horizontalHeader().setStretchLastSection(True)
        self.attendance_table.setAlternatingRowColors(True)

        # Make the Notes column editable
        self.attendance_table.setEditTriggers(
            QTableWidget.EditTrigger.DoubleClicked
            | QTableWidget.EditTrigger.EditKeyPressed
        )

        # Connect cell change signal to update notes in database
        self.attendance_table.cellChanged.connect(self.on_attendance_cell_changed)

        main_layout.addWidget(self.attendance_table)

        self.setLayout(main_layout)

        # Style and Theme
        self.setStyleSheet(
            """
            QGroupBox {
                border: 2px solid #e0e0e0;
                border-radius: 5px;
                margin-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QTableWidget {
                alternate-background-color: #f2f2f2;
                selection-background-color: #a6a6a6;
            }
        """
        )

        # Load classes at the end
        self.load_classes()

    def load_classes(self):
        try:
            # Log that we're trying to load classes
            logging.info("Loading classes into dropdown...")

            # Get classes from database
            classes = self.db.get_classes()

            # Clear existing items in dropdown
            self.class_selector.clear()
            self.class_selector.addItem("Select Class", None)

            if not classes or len(classes) == 0:
                logging.warning("No classes found in database")
                return

            # Add each class to dropdown
            class_count = 0
            for cls in classes:
                try:
                    # Try to get class_id and name safely
                    if isinstance(cls, sqlite3.Row):
                        class_id = cls["class_id"]
                        class_name = cls["name"]
                    else:
                        # Assume it's a tuple-like
                        class_id = cls[0]
                        class_name = cls[1]

                    # Log what we're adding
                    logging.info(f"Adding class to dropdown: {class_id} - {class_name}")

                    # Add to dropdown
                    self.class_selector.addItem(f"{class_id} - {class_name}", class_id)
                    class_count += 1
                except Exception as item_error:
                    logging.error(f"Error adding class to dropdown: {str(item_error)}")
                    continue

            logging.info(f"Added {class_count} classes to dropdown")

        except Exception as e:
            logging.error(f"Error in load_classes: {str(e)}")

    def load_attendance_records(self):
        """Load attendance records for the selected class and date"""
        try:
            # Get selected class ID
            class_index = self.class_selector.currentIndex()
            if class_index <= 0:  # First item is placeholder
                self.attendance_table.setRowCount(0)
                self.status_label.setText("Please select a class")
                return

            class_id = self.class_selector.itemData(class_index)

            # Get selected date
            date_str = self.date_selector.date().toString("yyyy-MM-dd")

            # Get attendance records
            records = self.db.get_attendance_records(class_id, date_str)

            # Clear existing table
            self.attendance_table.setRowCount(0)

            # If no records, show message
            if not records:
                self.status_label.setText(f"No attendance records for selected date")
                return

            # Temporarily disconnect the cellChanged signal to prevent
            # triggering it during loading
            try:
                self.attendance_table.cellChanged.disconnect(
                    self.on_attendance_cell_changed
                )
            except TypeError:
                # Signal was not connected
                pass

            # Populate table
            self.attendance_table.setRowCount(len(records))
            for row, record in enumerate(records):
                try:
                    # Convert record to string format for display
                    student_id_item = QTableWidgetItem(record.get("student_id", ""))
                    # Store the attendance ID as hidden data for later use when
                    # editing notes
                    student_id_item.setData(
                        Qt.ItemDataRole.UserRole, record.get("id", "")
                    )
                    self.attendance_table.setItem(row, 0, student_id_item)

                    # Student name
                    self.attendance_table.setItem(
                        row, 1, QTableWidgetItem(record.get("name", ""))
                    )

                    # Format check-in time
                    check_in_time = record.get("check_in_time", "")
                    time_display = check_in_time
                    if check_in_time and len(check_in_time) > 16:  # If full timestamp
                        # Extract date and time for display
                        date_part = check_in_time[:10]  # YYYY-MM-DD
                        time_part = check_in_time[11:16]  # HH:MM
                        if date_str == date_part:
                            # If same day as selected, just show time
                            time_display = time_part
                        else:
                            # If different day, show date and time
                            time_display = f"{date_part} {time_part}"

                    self.attendance_table.setItem(
                        row, 2, QTableWidgetItem(time_display)
                    )

                    # Status with color coding
                    status = record.get("status", "Unknown")
                    status_item = QTableWidgetItem(status)
                    if status == "Present":
                        status_item.setBackground(QColor(200, 255, 200))  # Light green
                    elif status == "Absent":
                        status_item.setBackground(QColor(255, 200, 200))  # Light red
                    elif status == "Late":
                        status_item.setBackground(QColor(255, 255, 200))  # Light yellow
                    self.attendance_table.setItem(row, 3, status_item)

                    # Location
                    location = record.get("location", "")
                    self.attendance_table.setItem(row, 4, QTableWidgetItem(location))

                    # Notes - make editable
                    notes = record.get("notes", "")
                    notes_item = QTableWidgetItem(notes)
                    self.attendance_table.setItem(row, 5, notes_item)

                except Exception as row_error:
                    logging.error(f"Error processing attendance row {row}: {row_error}")
                    continue

            # Reconnect the cellChanged signal
            try:
                self.attendance_table.cellChanged.connect(
                    self.on_attendance_cell_changed
                )
            except TypeError:
                # Signal was already connected
                pass

            # Resize columns to content
            self.attendance_table.resizeColumnsToContents()

            # Make sure Notes column is wide enough
            notes_column_width = self.attendance_table.columnWidth(5)
            if notes_column_width < 200:
                self.attendance_table.setColumnWidth(5, 200)

            # Update status label
            self.status_label.setText(f"Showing {len(records)} attendance records")

        except Exception as e:
            logging.error(f"Error loading attendance records: {e}")
            # Use a safer approach to update status
            if hasattr(self, "status_label"):
                self.status_label.setText(f"Error: {str(e)}")
            else:
                logging.error("status_label not found in AttendanceTab")

            # Make sure signal gets reconnected even after error
            try:
                self.attendance_table.cellChanged.connect(
                    self.on_attendance_cell_changed
                )
            except TypeError:
                # Signal was already connected
                pass

    def perform_face_check_in(self):
        """Perform continuous face recognition-based check-in"""
        try:
            # Get the selected class
            class_index = self.class_selector.currentIndex()
            if class_index <= 0:  # 0 is the "Select Class" item
                QMessageBox.warning(
                    self, "No Class Selected", "Please select a class first"
                )
                return

            class_id = self.class_selector.itemData(class_index)
            class_name = (
                self.class_selector.currentText().split(" - ")[1]
                if " - " in self.class_selector.currentText()
                else ""
            )

            # Check if camera is already running
            if hasattr(self, "camera_running") and self.camera_running:
                self.stop_face_check_in()
                return

            # Initialize camera
            import cv2

            self.cap = cv2.VideoCapture(0)

            if not self.cap.isOpened():
                QMessageBox.critical(
                    self,
                    "Camera Error",
                    "Could not open camera. Please check camera connection.",
                )
                return

            # Update button text to "Stop Camera"
            self.face_check_in_btn.setText("Stop Camera")
            self.face_check_in_btn.setStyleSheet(
                "background-color: #e74c3c; color: white;"
            )

            # Create frame for camera feed
            self.camera_frame = QLabel()
            self.camera_frame.setFixedSize(400, 300)
            self.camera_frame.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.camera_frame.setStyleSheet("border: 2px solid #ddd;")

            # Add to layout above attendance table
            camera_layout = QHBoxLayout()
            camera_layout.addStretch()
            camera_layout.addWidget(self.camera_frame)
            camera_layout.addStretch()

            # Insert camera layout at position 2 (after actions)
            layout_count = self.layout().count()
            for i in range(layout_count):
                if (
                    isinstance(self.layout().itemAt(i).layout(), QHBoxLayout)
                    and self.layout().itemAt(i).layout().count() > 0
                    and isinstance(
                        self.layout().itemAt(i).layout().itemAt(0).widget(), QPushButton
                    )
                ):
                    # Found buttons layout, insert camera after it
                    self.layout().insertLayout(i + 1, camera_layout)
                    break

            # Set flag
            self.camera_running = True

            # Create timer for processing frames
            self.camera_timer = QTimer(self)
            self.camera_timer.timeout.connect(
                lambda: self.process_camera_frame(class_id, class_name)
            )
            self.camera_timer.start(100)  # Process frames every 100ms

        except Exception as e:
            logging.error(f"Face check-in setup error: {e}")
            QMessageBox.critical(self, "Check-in Error", str(e))
            self.stop_face_check_in()

    def stop_face_check_in(self):
        """Stop the face recognition camera"""
        try:
            # Reset button
            self.face_check_in_btn.setText("Face Check-in")
            self.face_check_in_btn.setStyleSheet("")

            # Stop timer and release camera
            if hasattr(self, "camera_timer") and self.camera_timer:
                self.camera_timer.stop()

            if hasattr(self, "cap") and self.cap:
                self.cap.release()

            # Remove camera frame from layout
            if hasattr(self, "camera_frame"):
                self.camera_frame.setParent(None)
                self.camera_frame.deleteLater()

            # Reset flag
            self.camera_running = False

        except Exception as e:
            logging.error(f"Error stopping camera: {e}")

    def process_camera_frame(self, class_id, class_name):
        """Process a camera frame for face recognition"""
        try:
            # Read frame
            ret, frame = self.cap.read()
            if not ret:
                return

            # Convert frame to QImage for display
            height, width, channel = frame.shape
            bytes_per_line = 3 * width
            from PyQt6.QtGui import QImage, QPixmap

            q_img = QImage(
                frame.data, width, height, bytes_per_line, QImage.Format.Format_RGB888
            ).rgbSwapped()

            # Display in label
            self.camera_frame.setPixmap(
                QPixmap.fromImage(q_img).scaled(
                    self.camera_frame.width(),
                    self.camera_frame.height(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                )
            )

            # Only process for face recognition every 1 second (10 frames at
            # 100ms)
            if not hasattr(self, "frame_counter"):
                self.frame_counter = 0

            self.frame_counter += 1
            if self.frame_counter < 10:
                return

            self.frame_counter = 0

            # Process frame for face recognition
            import face_recognition
            import sqlite3
            import os

            # Convert frame to RGB for face_recognition
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Find faces
            face_locations = face_recognition.face_locations(rgb_frame)

            if not face_locations:
                # No faces detected
                return

            # Get face encodings
            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

            if not face_encodings:
                # No encodings possible
                return

            # Compare with known faces
            student_id = None
            confidence = 0
            student_name = ""

            # Get students with face images for comparison
            students = self.db.get_students()

            # Check all detected faces against database
            for face_encoding in face_encodings:
                # Reset for each face
                best_match_id = None
                best_match_name = ""
                best_confidence = 0

                # Check against all students
                for student in students:
                    # Extract face path safely
                    face_path = None
                    try:
                        if isinstance(student, dict):
                            face_path = student.get("face_image_path", "")
                            student_id_val = student.get("student_id", "unknown")
                        elif isinstance(student, sqlite3.Row):
                            # Try column name first
                            try:
                                face_path = student["face_image_path"]
                                student_id_val = student["student_id"]
                            except (IndexError, KeyError):
                                # Fallback to column index
                                face_path = student[8] if len(student) > 8 else None
                                student_id_val = (
                                    student[0] if len(student) > 0 else "unknown"
                                )
                        else:
                            # Try tuple access
                            face_path = student[8] if len(student) > 8 else None
                            student_id_val = (
                                student[0] if len(student) > 0 else "unknown"
                            )

                        if not face_path or not os.path.exists(face_path):
                            continue

                        # Check if we already processed this face image
                        if not hasattr(self, "face_encodings_cache"):
                            self.face_encodings_cache = {}

                        if face_path in self.face_encodings_cache:
                            known_encoding = self.face_encodings_cache[face_path]
                        else:
                            # Load and cache encoding
                            known_image = face_recognition.load_image_file(face_path)
                            known_faces = face_recognition.face_encodings(known_image)

                            if not known_faces:
                                continue

                            known_encoding = known_faces[0]
                            self.face_encodings_cache[face_path] = known_encoding

                        # Compare faces
                        matches = face_recognition.compare_faces(
                            [known_encoding], face_encoding, tolerance=0.6
                        )

                        if matches and matches[0]:
                            # Calculate face distance (lower is better)
                            face_distance = face_recognition.face_distance(
                                [known_encoding], face_encoding
                            )[0]
                            current_confidence = 1 - face_distance

                            # If better match than previous, update
                            if current_confidence > best_confidence:
                                best_confidence = current_confidence

                                # Get student details safely
                                if isinstance(student, dict):
                                    best_match_id = student.get("student_id", "")
                                    best_match_name = f"{student.get('first_name', '')} {student.get('last_name', '')}"
                                elif isinstance(student, sqlite3.Row):
                                    try:
                                        best_match_id = student["student_id"]
                                        best_match_name = f"{student['first_name']} {student['last_name']}"
                                    except (IndexError, KeyError):
                                        best_match_id = student[0]
                                        best_match_name = f"{student[1] if len(student) > 1 else ''} {student[2] if len(student) > 2 else ''}"
                                else:
                                    best_match_id = student[0]
                                    best_match_name = f"{student[1] if len(student) > 1 else ''} {student[2] if len(student) > 2 else ''}"

                    except Exception as face_error:
                        logging.error(f"Error processing face comparison: {face_error}")
                        continue

                # If we found a good match for this face, mark attendance
                if best_match_id and best_confidence > 0.6:  # 0.6 confidence threshold
                    # Check if this student was already marked present today
                    already_present = False

                    try:
                        from datetime import datetime

                        today = datetime.now().strftime("%Y-%m-%d")

                        # Get today's attendance records for this class
                        attendance_records = self.db.get_attendance_records(
                            class_id, today
                        )

                        # Check if student is already present
                        for record in attendance_records:
                            if (
                                isinstance(record, dict)
                                and record.get("student_id") == best_match_id
                            ):
                                already_present = True
                                break
                            elif (
                                hasattr(record, "__getitem__")
                                and record[1] == best_match_id
                            ):  # Assuming student_id is second column
                                already_present = True
                                break

                        # If not already marked present, mark attendance
                        if not already_present:
                            # Get current time for check-in
                            check_in_time = datetime.now()

                            # Process attendance
                            self.process_attendance_check_in(
                                student_id=best_match_id,
                                class_id=class_id,
                                check_in_time=check_in_time,
                                is_face_recognition=True,
                                confidence=best_confidence,
                            )

                            # Draw green rectangle around recognized face
                            top, right, bottom, left = face_locations[0]
                            cv2.rectangle(
                                frame, (left, top), (right, bottom), (0, 255, 0), 2
                            )

                            # Display recognized student name
                            cv2.putText(
                                frame,
                                f"{best_match_name} ({best_match_id})",
                                (left, top - 10),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.5,
                                (0, 255, 0),
                                2,
                            )

                            # Update frame display
                            q_img = QImage(
                                frame.data,
                                width,
                                height,
                                bytes_per_line,
                                QImage.Format.Format_RGB888,
                            ).rgbSwapped()
                            self.camera_frame.setPixmap(
                                QPixmap.fromImage(q_img).scaled(
                                    self.camera_frame.width(),
                                    self.camera_frame.height(),
                                    Qt.AspectRatioMode.KeepAspectRatio,
                                )
                            )

                    except Exception as record_error:
                        logging.error(f"Error recording attendance: {record_error}")

        except Exception as e:
            logging.error(f"Error processing camera frame: {e}")

    def manual_check_in(self):
        """Open dialog for manual student check-in"""
        try:
            # Get the selected class
            class_index = self.class_selector.currentIndex()
            if class_index <= 0:  # 0 is the "Select Class" item
                QMessageBox.warning(
                    self, "No Class Selected", "Please select a class first"
                )
                return

            class_id = self.class_selector.itemData(class_index)

            # Create manual check-in dialog
            dialog = QDialog(self)
            dialog.setWindowTitle("Manual Check-in")
            dialog.setMinimumWidth(300)

            # Dialog layout
            layout = QVBoxLayout(dialog)

            # Student ID input
            student_id_layout = QHBoxLayout()
            student_id_label = QLabel("Student ID:")
            student_id_input = QLineEdit()
            student_id_layout.addWidget(student_id_label)
            student_id_layout.addWidget(student_id_input)
            layout.addLayout(student_id_layout)

            # Buttons
            buttons_layout = QHBoxLayout()
            check_in_btn = QPushButton("Check In")
            cancel_btn = QPushButton("Cancel")
            buttons_layout.addWidget(check_in_btn)
            buttons_layout.addWidget(cancel_btn)
            layout.addLayout(buttons_layout)

            # Connect buttons
            check_in_btn.clicked.connect(
                lambda: self.process_attendance_check_in(
                    student_id=student_id_input.text(), class_id=class_id
                )
            )
            check_in_btn.clicked.connect(dialog.accept)
            cancel_btn.clicked.connect(dialog.reject)

            # Show dialog
            dialog.exec()

        except Exception as e:
            logging.error(f"Manual check-in error: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to open manual check-in: {str(e)}"
            )

    def process_attendance_check_in(
        self,
        student_id,
        class_id,
        check_in_time=None,
        is_face_recognition=False,
        confidence=None,
    ):
        """Process attendance check-in with lateness detection and note handling"""
        try:
            if not student_id or not class_id:
                QMessageBox.warning(
                    self, "Error", "Please provide both student ID and class ID"
                )
                return

            # Get current date and time if not provided
            from datetime import datetime

            if not check_in_time:
                check_in_time = datetime.now()

            check_in_time_str = check_in_time.strftime("%Y-%m-%d %H:%M:%S")

            # Check if we're in pre-check-in mode for this class
            is_late = False
            late_minutes = 0
            pre_checkin_active = False

            if (
                hasattr(self, "pre_checkin_config")
                and self.pre_checkin_config.get("class_id") == class_id
            ):
                pre_checkin_active = True
                config = self.pre_checkin_config

                # If check-in time is after the late threshold, mark as late
                if check_in_time > config["late_time"]:
                    is_late = True
                    late_minutes = int(
                        (check_in_time - config["class_start"]).total_seconds() // 60
                    )
            else:
                # Fall back to regular schedule check
                class_schedules = self.db.get_class_schedules(class_id)

                if class_schedules:
                    # Find today's schedule
                    today_weekday = check_in_time.strftime(
                        "%A"
                    )  # Monday, Tuesday, etc.
                    today_schedule = None

                    for schedule in class_schedules:
                        if schedule.get("day_of_week") == today_weekday:
                            today_schedule = schedule
                            break

                    if today_schedule:
                        # Check if student is late
                        start_time_str = today_schedule.get("start_time")
                        if start_time_str:
                            # Parse schedule start time
                            try:
                                schedule_time = datetime.strptime(
                                    start_time_str, "%H:%M"
                                ).time()
                                class_start = datetime.combine(
                                    check_in_time.date(), schedule_time
                                )

                                # Calculate minutes late
                                if check_in_time > class_start:
                                    time_diff = check_in_time - class_start
                                    late_minutes = time_diff.seconds // 60
                                    if (
                                        late_minutes > 5
                                    ):  # More than 5 minutes late is considered "Late"
                                        is_late = True
                            except Exception as time_error:
                                logging.error(f"Error parsing time: {time_error}")

            # Determine attendance status
            status = "Late" if is_late else "Present"

            # Prepare notes
            notes = ""
            if is_face_recognition and confidence:
                notes = f"Face recognition (confidence: {confidence:.1%})"

            # For late students, prompt for a reason
            if is_late:
                from PyQt6.QtWidgets import QInputDialog

                reason, ok = QInputDialog.getText(
                    self,
                    "Late Arrival",
                    f"Student is {late_minutes} minutes late. Please enter a reason:",
                    QLineEdit.EchoMode.Normal,
                )

                if ok and reason:
                    notes = f"Late by {late_minutes} minutes. Reason: {reason}" + (
                        f" {notes}" if notes else ""
                    )
                else:
                    notes = f"Late by {late_minutes} minutes." + (
                        f" {notes}" if notes else ""
                    )

            # Add pre-check-in information to notes if active
            if pre_checkin_active:
                pre_checkin_note = "Pre-check-in mode active. "
                if notes:
                    notes = pre_checkin_note + notes
                else:
                    notes = pre_checkin_note

            # Mark attendance in database
            self.db.mark_attendance(
                class_id=class_id,
                student_id=student_id,
                status=status,
                check_in_time=check_in_time_str,
                notes=notes,
            )

            # Show success message
            QMessageBox.information(
                self,
                "Success",
                f"Attendance for student {student_id} marked as {status}"
                + (f" ({late_minutes} minutes late)" if is_late else ""),
            )

            # Refresh attendance records
            self.load_attendance_records()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to process check-in: {str(e)}")
            logging.error(f"Attendance check-in error: {e}")

    def setup_pre_checkin(self):
        """Set up pre-check-in time window for the selected class"""
        try:
            # Get the selected class
            class_index = self.class_selector.currentIndex()
            if class_index <= 0:  # 0 is the "Select Class" item
                QMessageBox.warning(
                    self, "No Class Selected", "Please select a class first"
                )
                return

            class_id = self.class_selector.itemData(class_index)
            class_name = (
                self.class_selector.currentText().split(" - ")[1]
                if " - " in self.class_selector.currentText()
                else ""
            )

            # Create dialog
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Set Pre-Check-In Time for {class_name}")
            dialog.setMinimumWidth(400)

            # Dialog layout
            layout = QVBoxLayout(dialog)

            # Class start time
            form_layout = QFormLayout()

            # Get today's class schedule if it exists
            from datetime import datetime

            today_weekday = datetime.now().strftime("%A")
            class_schedules = self.db.get_class_schedules(class_id)
            today_schedule = None

            for schedule in class_schedules:
                if schedule.get("day_of_week") == today_weekday:
                    today_schedule = schedule
                    break

            # Start time input
            time_layout = QHBoxLayout()
            hours_label = QLabel("Hours:")
            self.hours_input = QSpinBox()
            self.hours_input.setRange(0, 23)
            self.hours_input.setValue(8)  # Default to 8:00 AM

            minutes_label = QLabel("Minutes:")
            self.minutes_input = QSpinBox()
            self.minutes_input.setRange(0, 59)
            self.minutes_input.setValue(0)

            if today_schedule and today_schedule.get("start_time"):
                try:
                    # Parse start time from schedule
                    start_time = datetime.strptime(
                        today_schedule.get("start_time"), "%H:%M"
                    ).time()
                    self.hours_input.setValue(start_time.hour)
                    self.minutes_input.setValue(start_time.minute)
                except BaseException:
                    logging.warning(
                        f"Could not parse start time: {today_schedule.get('start_time')}"
                    )

            time_layout.addWidget(hours_label)
            time_layout.addWidget(self.hours_input)
            time_layout.addWidget(minutes_label)
            time_layout.addWidget(self.minutes_input)

            form_layout.addRow("Class Start Time:", time_layout)

            # Pre-check-in window
            self.pre_checkin_window = QSpinBox()
            self.pre_checkin_window.setRange(1, 60)
            self.pre_checkin_window.setValue(5)  # Default to 5 minutes
            self.pre_checkin_window.setSuffix(" min")
            form_layout.addRow("Pre-Check-In Window:", self.pre_checkin_window)

            # Late threshold
            self.late_threshold = QSpinBox()
            self.late_threshold.setRange(1, 60)
            self.late_threshold.setValue(5)  # Default to 5 minutes
            self.late_threshold.setSuffix(" min")
            form_layout.addRow("Late Threshold After Start:", self.late_threshold)

            layout.addLayout(form_layout)

            # Current time info
            current_time = QLabel(
                f"Current time: {datetime.now().strftime('%H:%M:%S')}"
            )
            current_time.setStyleSheet("color: #666;")
            layout.addWidget(current_time)

            # Information text
            info_text = QLabel(
                "Setting pre-check-in time allows students to check in before class starts. "
                "Students arriving after class starts but within the late threshold will be marked as 'Present'. "
                "Students arriving after the late threshold will be marked as 'Late'."
            )
            info_text.setWordWrap(True)
            info_text.setStyleSheet("color: #666; font-style: italic;")
            layout.addWidget(info_text)

            # Buttons
            buttons_layout = QHBoxLayout()
            start_btn = QPushButton("Start Pre-Check-In")
            start_btn.setStyleSheet("background-color: #4CAF50; color: white;")
            cancel_btn = QPushButton("Cancel")
            buttons_layout.addWidget(start_btn)
            buttons_layout.addWidget(cancel_btn)
            layout.addLayout(buttons_layout)

            # Connect buttons
            start_btn.clicked.connect(
                lambda: self.start_pre_checkin(
                    class_id=class_id,
                    class_name=class_name,
                    hours=self.hours_input.value(),
                    minutes=self.minutes_input.value(),
                    pre_window=self.pre_checkin_window.value(),
                    late_threshold=self.late_threshold.value(),
                )
            )
            start_btn.clicked.connect(dialog.accept)
            cancel_btn.clicked.connect(dialog.reject)

            # Show dialog
            dialog.exec()

        except Exception as e:
            logging.error(f"Error setting up pre-check-in: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to set up pre-check-in: {str(e)}"
            )

    def start_pre_checkin(
        self, class_id, class_name, hours, minutes, pre_window, late_threshold
    ):
        """Start pre-check-in mode with specified parameters"""
        try:
            from datetime import datetime, timedelta

            # Calculate relevant times
            now = datetime.now()
            class_start_time = datetime(
                now.year, now.month, now.day, hour=hours, minute=minutes
            )
            pre_checkin_start = class_start_time - timedelta(minutes=pre_window)
            late_time = class_start_time + timedelta(minutes=late_threshold)

            # Store these values for use during check-in
            self.pre_checkin_config = {
                "class_id": class_id,
                "class_name": class_name,
                "class_start": class_start_time,
                "pre_checkin_start": pre_checkin_start,
                "late_time": late_time,
                "pre_window": pre_window,
                "late_threshold": late_threshold,
            }

            # Create status indicator
            if not hasattr(self, "pre_checkin_status"):
                self.pre_checkin_status = QLabel()
                self.layout().insertWidget(1, self.pre_checkin_status)

            # Update status
            self.update_pre_checkin_status()

            # Start timer to update status
            if not hasattr(self, "pre_checkin_timer"):
                self.pre_checkin_timer = QTimer(self)
                self.pre_checkin_timer.timeout.connect(self.update_pre_checkin_status)

            self.pre_checkin_timer.start(1000)  # Update every second

            # Show confirmation
            QMessageBox.information(
                self,
                "Pre-Check-In Started",
                f"Pre-check-in has started for {class_name}.\n\n"
                f"Class starts at: {class_start_time.strftime('%H:%M')}\n"
                f"Pre-check-in window: {pre_window} minutes before class\n"
                f"Late threshold: {late_threshold} minutes after class starts",
            )

        except Exception as e:
            logging.error(f"Error starting pre-check-in: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to start pre-check-in: {str(e)}"
            )

    def stop_pre_checkin(self):
        """Stop the pre-check-in timer and clear status"""
        try:
            if hasattr(self, "pre_checkin_timer") and self.pre_checkin_timer:
                self.pre_checkin_timer.stop()

            if hasattr(self, "pre_checkin_status"):
                self.pre_checkin_status.setParent(None)
                self.pre_checkin_status.deleteLater()
                delattr(self, "pre_checkin_status")

            if hasattr(self, "pre_checkin_config"):
                delattr(self, "pre_checkin_config")

        except Exception as e:
            logging.error(f"Error stopping pre-check-in: {e}")

    def update_pre_checkin_status(self):
        """Update the pre-check-in status display"""
        try:
            if not hasattr(self, "pre_checkin_config"):
                return

            from datetime import datetime

            now = datetime.now()
            config = self.pre_checkin_config

            # Calculate time remaining or elapsed
            if now < config["pre_checkin_start"]:
                # Before pre-check-in window
                time_diff = config["pre_checkin_start"] - now
                minutes = time_diff.seconds // 60
                seconds = time_diff.seconds % 60
                status_text = f"Pre-check-in starts in {minutes:02d}:{seconds:02d}"
                status_color = "orange"

            elif now < config["class_start"]:
                # During pre-check-in window
                time_diff = config["class_start"] - now
                minutes = time_diff.seconds // 60
                seconds = time_diff.seconds % 60
                status_text = (
                    f"PRE-CHECK-IN ACTIVE - Class starts in {minutes:02d}:{seconds:02d}"
                )
                status_color = "green"

            elif now < config["late_time"]:
                # After class start but before late threshold
                time_diff = config["late_time"] - now
                minutes = time_diff.seconds // 60
                seconds = time_diff.seconds % 60
                status_text = (
                    f"Class has started - Late threshold in {minutes:02d}:{seconds:02d}"
                )
                status_color = "blue"

            else:
                # After late threshold
                time_diff = now - config["late_time"]
                minutes = time_diff.seconds // 60
                status_text = (
                    f"Students are now LATE ({minutes} minutes after threshold)"
                )
                status_color = "red"

            # Update status display
            self.pre_checkin_status.setText(status_text)
            self.pre_checkin_status.setStyleSheet(
                f"background-color: {status_color}; color: white; "
                "padding: 10px; font-weight: bold; border-radius: 5px;"
            )
            self.pre_checkin_status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        except Exception as e:
            logging.error(f"Error updating pre-check-in status: {e}")

    def on_attendance_cell_changed(self, row, column):
        """Handle edits to attendance table cells"""
        try:
            # Only process changes to the Notes column (index 5)
            if column != 5:
                return

            # Get the attendance record ID from the hidden data
            attendance_id = self.attendance_table.item(row, 0).data(
                Qt.ItemDataRole.UserRole
            )
            if not attendance_id:
                return

            # Get the new note text
            notes_item = self.attendance_table.item(row, column)
            if not notes_item:
                return

            new_notes = notes_item.text()

            # Update the note in the database
            self.db.update_attendance_note(attendance_id, new_notes)

            # Log the update
            logging.info(f"Updated notes for attendance record {attendance_id}")

        except Exception as e:
            logging.error(f"Error updating attendance note: {e}")
            QMessageBox.warning(self, "Error", f"Could not update note: {str(e)}")
