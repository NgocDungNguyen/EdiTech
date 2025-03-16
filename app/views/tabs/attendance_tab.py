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
        """Perform continuous face recognition-based check-in"""
        try:
            # Get the selected class
            class_index = self.class_selector.currentIndex()
            if class_index <= 0:  # 0 is the "Select Class" item
                QMessageBox.warning(self, "No Class Selected", "Please select a class first")
                return
        
            class_id = self.class_selector.itemData(class_index)
            class_name = self.class_selector.currentText().split(' - ')[1] if ' - ' in self.class_selector.currentText() else ""
        
            # Check if camera is already running
            if hasattr(self, 'camera_running') and self.camera_running:
                self.stop_face_check_in()
                return
            
            # Initialize camera
            import cv2
            self.cap = cv2.VideoCapture(0)
        
            if not self.cap.isOpened():
                QMessageBox.critical(self, "Camera Error", "Could not open camera. Please check camera connection.")
                return
        
            # Update button text to "Stop Camera"
            self.face_check_in_btn.setText("Stop Camera")
            self.face_check_in_btn.setStyleSheet("background-color: #e74c3c; color: white;")
        
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
                if isinstance(self.layout().itemAt(i).layout(), QHBoxLayout) and \
                    self.layout().itemAt(i).layout().count() > 0 and \
                    isinstance(self.layout().itemAt(i).layout().itemAt(0).widget(), QPushButton):
                    # Found buttons layout, insert camera after it
                    self.layout().insertLayout(i+1, camera_layout)
                    break
        
            # Set flag
            self.camera_running = True
        
            # Create timer for processing frames
            self.camera_timer = QTimer(self)
            self.camera_timer.timeout.connect(lambda: self.process_camera_frame(class_id, class_name))
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
            if hasattr(self, 'camera_timer') and self.camera_timer:
                self.camera_timer.stop()
            
            if hasattr(self, 'cap') and self.cap:
                self.cap.release()
            
            # Remove camera frame from layout
            if hasattr(self, 'camera_frame'):
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
            q_img = QImage(frame.data, width, height, bytes_per_line, QImage.Format.Format_RGB888).rgbSwapped()
        
            # Display in label
            self.camera_frame.setPixmap(QPixmap.fromImage(q_img).scaled(
                self.camera_frame.width(), 
                self.camera_frame.height(),
                Qt.AspectRatioMode.KeepAspectRatio
            ))
        
            # Only process for face recognition every 1 second (10 frames at 100ms)
            if not hasattr(self, 'frame_counter'):
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
                            face_path = student.get('face_image_path', '')
                            student_id_val = student.get('student_id', 'unknown')
                        elif isinstance(student, sqlite3.Row):
                            # Try column name first
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
                        
                        if not face_path or not os.path.exists(face_path):
                            continue
                        
                        # Check if we already processed this face image
                        if not hasattr(self, 'face_encodings_cache'):
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
                        matches = face_recognition.compare_faces([known_encoding], face_encoding, tolerance=0.6)
                    
                        if matches and matches[0]:
                            # Calculate face distance (lower is better)
                            face_distance = face_recognition.face_distance([known_encoding], face_encoding)[0]
                            current_confidence = 1 - face_distance
                        
                            # If better match than previous, update
                            if current_confidence > best_confidence:
                                best_confidence = current_confidence
                            
                                # Get student details safely
                                if isinstance(student, dict):
                                    best_match_id = student.get('student_id', '')
                                    best_match_name = f"{student.get('first_name', '')} {student.get('last_name', '')}"
                                elif isinstance(student, sqlite3.Row):
                                    try:
                                        best_match_id = student['student_id']
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
                        attendance_records = self.db.get_attendance_records(class_id, today)
                    
                        # Check if student is already present
                        for record in attendance_records:
                            if isinstance(record, dict) and record.get('student_id') == best_match_id:
                                already_present = True
                                break
                            elif hasattr(record, '__getitem__') and record[1] == best_match_id:  # Assuming student_id is second column
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
                                confidence=best_confidence
                            )
                        
                            # Draw green rectangle around recognized face
                            top, right, bottom, left = face_locations[0]
                            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                        
                            # Display recognized student name
                            cv2.putText(
                                frame, 
                                f"{best_match_name} ({best_match_id})", 
                                (left, top - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 
                                0.5, 
                                (0, 255, 0), 
                                2
                            )
                        
                            # Update frame display
                            q_img = QImage(frame.data, width, height, bytes_per_line, QImage.Format.Format_RGB888).rgbSwapped()
                            self.camera_frame.setPixmap(QPixmap.fromImage(q_img).scaled(
                                self.camera_frame.width(), 
                                self.camera_frame.height(),
                                Qt.AspectRatioMode.KeepAspectRatio
                            ))
                
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
            check_in_btn.clicked.connect(lambda: self.process_attendance_check_in(
                student_id=student_id_input.text(), 
                class_id=class_id
            ))
            check_in_btn.clicked.connect(dialog.accept)
            cancel_btn.clicked.connect(dialog.reject)
        
            # Show dialog
            dialog.exec()
        
        except Exception as e:
            logging.error(f"Manual check-in error: {e}")
            QMessageBox.critical(self, "Error", f"Failed to open manual check-in: {str(e)}")
            
    def process_attendance_check_in(self, student_id, class_id, check_in_time=None, is_face_recognition=False, confidence=None):
        """Process attendance check-in with lateness detection and note handling"""
        try:
            if not student_id or not class_id:
                QMessageBox.warning(self, "Error", "Please provide both student ID and class ID")
                return

            # Get current date and time if not provided
            from datetime import datetime
            if not check_in_time:
                check_in_time = datetime.now()
            
            check_in_time_str = check_in_time.strftime("%Y-%m-%d %H:%M:%S")
        
            # Get class schedule to determine if student is late
            class_schedules = self.db.get_class_schedules(class_id)
            is_late = False
            late_minutes = 0
        
            if class_schedules:
                # Find today's schedule
                today_weekday = check_in_time.strftime("%A")  # Monday, Tuesday, etc.
                today_schedule = None
            
                for schedule in class_schedules:
                    if schedule.get('day_of_week') == today_weekday:
                        today_schedule = schedule
                        break
            
                if today_schedule:
                    # Check if student is late
                    start_time_str = today_schedule.get('start_time')
                    if start_time_str:
                        # Parse schedule start time
                        schedule_time = datetime.strptime(start_time_str, "%H:%M").time()
                        class_start = datetime.combine(check_in_time.date(), schedule_time)
                    
                        # Calculate minutes late
                        if check_in_time > class_start:
                            time_diff = check_in_time - class_start
                            late_minutes = time_diff.seconds // 60
                            if late_minutes > 5:  # More than 5 minutes late is considered "Late"
                                is_late = True
                            
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
                    QLineEdit.EchoMode.Normal
                )
            
                if ok and reason:
                    notes = f"Late by {late_minutes} minutes. Reason: {reason}" + (f" {notes}" if notes else "")
                else:
                    notes = f"Late by {late_minutes} minutes." + (f" {notes}" if notes else "")
        
            # Mark attendance in database
            self.db.mark_attendance(
                class_id=class_id,
                student_id=student_id,
                status=status,
                check_in_time=check_in_time_str,
                notes=notes
            )
        
            # Show success message
            QMessageBox.information(
                self, 
                "Success", 
                f"Attendance for student {student_id} marked as {status}" + 
                (f" ({late_minutes} minutes late)" if is_late else "")
            )
        
            # Refresh attendance records
            self.load_attendance_records()
    
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to process check-in: {str(e)}")
            logging.error(f"Attendance check-in error: {e}")
