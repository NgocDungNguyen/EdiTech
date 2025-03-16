import os
import cv2
import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, 
    QTableWidgetItem, QPushButton, QComboBox, QDateEdit, 
    QMessageBox, QGroupBox, QGridLayout, QLineEdit, QDialog
)
from PyQt6.QtGui import QFont, QColor, QIcon
from PyQt6.QtCore import Qt, QDate, QTimer

from app.models.database import Database
from app.utils.face_recognition import FaceRecognitionManager
from app.utils.config import DATA_DIR, ICONS_DIR
import logging
import sqlite3

class AttendanceTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Database and face recognition
        self.db = Database()
        self.face_recognition_manager = FaceRecognitionManager(
            os.path.join(DATA_DIR, 'edison_vision.db')
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

        main_layout.addLayout(actions_layout)

        # Add status label
        self.status_label = QLabel("No records loaded")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-style: italic; color: #666;")
        main_layout.addWidget(self.status_label)

        # Attendance Table
        self.attendance_table = QTableWidget()
        self.attendance_table.setColumnCount(6)
        self.attendance_table.setHorizontalHeaderLabels([
            "Student ID", "Name", "Check-in Time", "Status", "Location", "Notes"
        ])
        self.attendance_table.horizontalHeader().setStretchLastSection(True)
        self.attendance_table.setAlternatingRowColors(True)

        main_layout.addWidget(self.attendance_table)

        self.setLayout(main_layout)

        # Style and Theme
        self.setStyleSheet("""
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
        """)
        
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
                        class_id = cls['class_id']
                        class_name = cls['name']
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

            # Populate table
            self.attendance_table.setRowCount(len(records))
            for row, record in enumerate(records):
                # Convert record to string format for display
                self.attendance_table.setItem(row, 0, QTableWidgetItem(record['student_id']))
                self.attendance_table.setItem(row, 1, QTableWidgetItem(record['name']))

                # Format check-in time
                check_in_time = record.get('check_in_time', '')
                if check_in_time and len(check_in_time) > 16:  # If full timestamp
                    check_in_time = check_in_time[11:16]  # Extract just the time HH:MM
                self.attendance_table.setItem(row, 2, QTableWidgetItem(check_in_time))

                # Status with color coding
                status = record.get('status', 'Unknown')
                status_item = QTableWidgetItem(status)
                if status == 'Present':
                    status_item.setBackground(QColor(200, 255, 200))  # Light green
                elif status == 'Absent':
                    status_item.setBackground(QColor(255, 200, 200))  # Light red
                elif status == 'Late':
                    status_item.setBackground(QColor(255, 255, 200))  # Light yellow
                self.attendance_table.setItem(row, 3, status_item)

                # Notes
                if record.get('notes'):
                    notes_item = QTableWidgetItem(record['notes'])
                    self.attendance_table.setItem(row, 4, notes_item)

            # Update status label
            self.status_label.setText(f"Showing {len(records)} attendance records")

        except Exception as e:
            logging.error(f"Error loading attendance records: {e}")
            # Use a safer approach to update status
            if hasattr(self, 'status_label'):
                self.status_label.setText(f"Error: {str(e)}")
            else:
                logging.error("status_label not found in AttendanceTab")

    def perform_face_check_in(self):
        """Perform face recognition-based check-in"""
        try:
            # Get the selected class
            class_index = self.class_selector.currentIndex()
            if class_index <= 0:  # 0 is the "Select Class" item
                QMessageBox.warning(self, "No Class Selected", "Please select a class first")
                return

            class_id = self.class_selector.itemData(class_index)
            class_name = self.class_selector.currentText().split(' - ')[1] if ' - ' in self.class_selector.currentText() else ""

            # Initialize camera
            import cv2
            cap = cv2.VideoCapture(0)

            if not cap.isOpened():
                QMessageBox.critical(self, "Camera Error", "Could not open camera. Please check camera connection.")
                return

            # Display camera setup message
            QMessageBox.information(self, "Camera Setup", 
                                   "Camera will now activate for face recognition.\n"
                                   "Please position your face in front of the camera.")

            # Take multiple frames to allow camera to adjust
            for i in range(5):
                ret, frame = cap.read()
                if not ret:
                    break
                # Don't use cv2.waitKey() which is causing issues
                # Use QTimer.singleShot instead to delay
                from PyQt6.QtCore import QTimer
                timer = QTimer()
                timer.singleShot(100, lambda: None)  # 100ms delay
                timer.start()

            # Capture a frame for face recognition
            ret, frame = cap.read()
            if not ret:
                cap.release()
                QMessageBox.critical(self, "Camera Error", "Could not read camera frame")
                return

            # Save frame temporarily
            temp_frame_path = os.path.join(DATA_DIR, "temp_frame.jpg")
            cv2.imwrite(temp_frame_path, frame)

            # Release camera
            cap.release()

            # Create progress dialog
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText("Recognizing face...")
            msg.setWindowTitle("Face Recognition")
            msg.setStandardButtons(QMessageBox.StandardButton.NoButton)
            msg.show()

            # Process using a separate method to avoid UI freezing
            from PyQt6.QtWidgets import QApplication
            QApplication.processEvents()

            try:
                # Perform face recognition
                import face_recognition
                import sqlite3

                # Load the image and find faces
                image = face_recognition.load_image_file(temp_frame_path)
                face_locations = face_recognition.face_locations(image)

                if not face_locations:
                    msg.close()
                    QMessageBox.warning(self, "No Face Detected", 
                                    "No face was detected in the camera frame. Please try again.")
                    return

                # Get face encodings
                face_encodings = face_recognition.face_encodings(image, face_locations)

                if not face_encodings:
                    msg.close()
                    QMessageBox.warning(self, "Encoding Failed", 
                                    "Failed to encode detected face. Please try again.")
                    return

                # Compare with known faces
                student_id = None
                confidence = 0
                student_name = ""

                # Get students with face images for comparison
                students = self.db.get_students()

                # Log the student records for debugging
                logging.info(f"Retrieved {len(students)} students for face comparison")

                # Loop through students and check for face matches
                for student in students:
                    # Skip student if no face image path
                    face_path = None

                    try:
                        if isinstance(student, dict):
                            face_path = student.get('face_image_path', '')
                            student_id_val = student.get('student_id', 'unknown')
                        elif isinstance(student, sqlite3.Row):
                            # Try to access by column name first
                            try:
                                face_path = student['face_image_path']
                                student_id_val = student['student_id']
                            except (IndexError, KeyError):
                                # Fallback to column index
                                face_path = student[8] if len(student) > 8 else None
                                student_id_val = student[0] if len(student) > 0 else 'unknown'
                        else:
                            # Try tuple access
                            face_path = student[8] if len(student) > 8 else None
                            student_id_val = student[0] if len(student) > 0 else 'unknown'

                        # Log the face path for debugging
                        logging.info(f"Checking student {student_id_val}, face path: {face_path}")

                        if not face_path or not os.path.exists(face_path):
                            logging.info(f"No valid face image path for student {student_id_val}")
                            continue

                        # Load stored face image
                        known_image = face_recognition.load_image_file(face_path)
                        known_faces = face_recognition.face_encodings(known_image)

                        if not known_faces:
                            logging.warning(f"Could not extract face encoding from {face_path}")
                            continue

                        known_encoding = known_faces[0]

                        # Compare faces
                        matches = face_recognition.compare_faces([known_encoding], face_encodings[0])

                        if matches and matches[0]:
                            # Calculate face distance (lower is better)
                            face_distance = face_recognition.face_distance([known_encoding], face_encodings[0])[0]
                            current_confidence = 1 - face_distance
                            logging.info(f"Match found for student {student_id_val} with confidence {current_confidence:.2f}")

                            # If better match than previous, update
                            if current_confidence > confidence:
                                confidence = current_confidence

                                # Get student details safely
                                if isinstance(student, dict):
                                    student_id = student.get('student_id', '')
                                    student_name = f"{student.get('first_name', '')} {student.get('last_name', '')}"
                                elif isinstance(student, sqlite3.Row):
                                    try:
                                        student_id = student['student_id']
                                        student_name = f"{student['first_name']} {student['last_name']}"
                                    except (IndexError, KeyError):
                                        student_id = student[0]
                                        student_name = f"{student[1] if len(student) > 1 else ''} {student[2] if len(student) > 2 else ''}"
                                else:
                                    student_id = student[0]
                                    student_name = f"{student[1] if len(student) > 1 else ''} {student[2] if len(student) > 2 else ''}"
                    except Exception as face_error:
                        logging.error(f"Error processing face for student: {face_error}")
                        continue

                # Close progress dialog
                msg.close()

                # Check if a student was recognized
                if student_id and confidence > 0.5:  # 0.5 is the confidence threshold
                    # Record attendance
                    from datetime import datetime
                    check_in_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    notes = f"Face recognition (confidence: {confidence:.1%})"

                    self.db.mark_attendance(
                        student_id=student_id,
                        class_id=class_id,
                        status="Present",
                        check_in_time=check_in_time,
                        notes=notes
                    )

                    # Show success message
                    QMessageBox.information(self, "Check-in Successful", 
                                          f"Welcome, {student_name}!\n"
                                          f"You have been checked in to {class_name}\n"
                                          f"Confidence: {confidence:.1%}")

                    # Refresh attendance list
                    self.load_attendance_records()
                else:
                    QMessageBox.warning(self, "Not Recognized", 
                                      "Face not recognized or confidence too low.\n"
                                      "Please try again or use manual check-in.")

            except Exception as rec_error:
                msg.close()
                logging.error(f"Face recognition error: {rec_error}")
                QMessageBox.critical(self, "Check-in Error", 
                                   f"Error during face recognition: {str(rec_error)}")

            # Clean up temp file
            try:
                if os.path.exists(temp_frame_path):
                    os.remove(temp_frame_path)
            except:
                pass

        except Exception as e:
            logging.error(f"Face check-in error: {e}")
            QMessageBox.critical(self, "Check-in Error", str(e))

    def manual_check_in(self):
        """Open dialog for manual student check-in"""
        try:
            # Get the selected class
            class_index = self.class_selector.currentIndex()
            if class_index <= 0:  # 0 is the "Select Class" item
                QMessageBox.warning(self, "No Class Selected", "Please select a class first")
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
            check_in_btn.clicked.connect(lambda: self.process_manual_check_in(student_id_input.text(), class_id))
            check_in_btn.clicked.connect(dialog.accept)
            cancel_btn.clicked.connect(dialog.reject)

            # Show dialog
            dialog.exec()

        except Exception as e:
            logging.error(f"Manual check-in error: {e}")
            QMessageBox.critical(self, "Error", f"Failed to open manual check-in: {str(e)}")
