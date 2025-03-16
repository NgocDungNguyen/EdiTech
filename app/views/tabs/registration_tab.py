import os
import sys
import logging
import sqlite3
import pickle
import cv2
import json
import numpy as np
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QDateEdit, QMessageBox, QFrame, QFormLayout, 
    QTableWidget, QTableWidgetItem, QTabWidget, QDialog, 
    QDialogButtonBox, QTextEdit, QComboBox, QHeaderView, QGridLayout,
    QGroupBox
)
from PyQt6.QtCore import Qt, QDate, QTimer, QSize, QEvent
from PyQt6.QtGui import QImage, QPixmap, QFont, QIcon, QColor

from app.models.database import Database
from app.utils.config import DATA_DIR, ICONS_DIR, DATABASE_PATH
from app.utils.face_recognition import FaceRecognitionManager

class StudentDetailDialog(QDialog):
    def __init__(self, student_dict, parent=None):
        super().__init__(parent)
        self.student_dict = student_dict
        self.setWindowTitle("Student Details")
        self.setModal(True)
        
        # Main layout
        layout = QVBoxLayout()
        
        # Details form
        details_layout = QFormLayout()
        
        # Add details to form
        details_fields = [
            ("Student ID", student_dict.get('student_id', '')),
            ("Name", student_dict.get('name', '')),
            ("Email", student_dict.get('email', '')),
            ("Phone", student_dict.get('phone', '')),
            ("Date of Birth", student_dict.get('date_of_birth', '')),
            ("Gender", student_dict.get('gender', ''))
        ]
        
        for label, value in details_fields:
            details_layout.addRow(f"{label}:", QLabel(str(value)))
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        # Add layouts to main layout
        layout.addLayout(details_layout)
        layout.addWidget(button_box)
        
        # Set dialog layout
        self.setLayout(layout)
        
        # Resize dialog
        self.resize(400, 300)  # Adjust size as needed

class StudentRegistrationForm(QWidget):
    def __init__(self, database, parent=None):
        super().__init__(parent)
        self.database = database
        self.face_recognition_manager = FaceRecognitionManager(
            os.path.join(DATA_DIR, 'edison_vision.db')
        )

        # Face capture variables
        self.capture_timer = QTimer(self)
        self.capture_timer.timeout.connect(self.update_face_capture)
        self.video_capture = None
        self.face_image_path = None

        # Initialize face cascade
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )

        self.init_ui()

    def init_ui(self):
        # Main layout
        main_layout = QVBoxLayout()

        # Student Information Form
        form_layout = QFormLayout()

        # Student ID
        self.student_id_input = QLineEdit()
        form_layout.addRow("Student ID:", self.student_id_input)

        # First Name
        self.first_name_input = QLineEdit()
        form_layout.addRow("First Name:", self.first_name_input)

        # Last Name
        self.last_name_input = QLineEdit()
        form_layout.addRow("Last Name:", self.last_name_input)

        # Email
        self.email_input = QLineEdit()
        form_layout.addRow("Email:", self.email_input)

        # Phone
        self.phone_input = QLineEdit()
        form_layout.addRow("Phone:", self.phone_input)

        # Date of Birth
        self.date_of_birth_input = QDateEdit()
        self.date_of_birth_input.setDisplayFormat("yyyy-MM-dd")
        self.date_of_birth_input.setDate(QDate.currentDate())
        form_layout.addRow("Date of Birth:", self.date_of_birth_input)

        # Gender
        self.gender_input = QComboBox()
        self.gender_input.addItems(["", "Male", "Female", "Other"])
        form_layout.addRow("Gender:", self.gender_input)

        # Face Capture Section
        face_layout = QVBoxLayout()

        # Face Capture Label
        self.face_capture_label = QLabel("Face Capture")
        face_layout.addWidget(self.face_capture_label)

        # Capture Button
        self.capture_button = QPushButton("Capture Face")
        self.capture_button.clicked.connect(self.start_face_capture)
        face_layout.addWidget(self.capture_button)

        # Face Preview
        self.face_preview_label = QLabel()
        self.face_preview_label.setFixedSize(300, 300)
        self.face_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        face_layout.addWidget(self.face_preview_label)

        # Submit Button
        self.submit_button = QPushButton("Register Student")
        self.submit_button.clicked.connect(self.register_student)

        # Combine layouts
        main_layout.addLayout(form_layout)
        main_layout.addLayout(face_layout)
        main_layout.addWidget(self.submit_button)

        self.setLayout(main_layout)

    def start_face_capture(self):
        """
        Start face capture process using webcam
        """
        try:
            # Open webcam
            self.video_capture = cv2.VideoCapture(0)

            if not self.video_capture.isOpened():
                QMessageBox.warning(self, "Error", "Could not open webcam")
                return

            # Verify face cascade is loaded
            if self.face_cascade.empty():
                QMessageBox.warning(self, "Error", "Face detection classifier failed to load")
                return

            # Start timer to update face capture
            self.capture_timer.start(50)  # 50 ms interval
            self.capture_button.setEnabled(False)
            self.capture_button.setText("Capturing...")

        except Exception as e:
            QMessageBox.critical(self, "Capture Error", str(e))

    def update_face_capture(self):
        """
        Continuously update face capture preview
        """
        try:
            # Check if video capture is open
            if not self.video_capture or not self.video_capture.isOpened():
                QMessageBox.warning(self, "Camera Error", "Camera not available")
                self.stop_face_capture()
                return

            # Capture frame
            ret, frame = self.video_capture.read()

            if not ret:
                QMessageBox.warning(self, "Camera Error", "Could not read camera frame")
                self.stop_face_capture()
                return

            # Convert frame to grayscale for face detection
            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Detect faces
            faces = self.face_cascade.detectMultiScale(
                gray_frame, 
                scaleFactor=1.1, 
                minNeighbors=5, 
                minSize=(30, 30)
            )

            # Convert frame to RGB for display
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Draw rectangles around faces
            for (x, y, w, h) in faces:
                cv2.rectangle(rgb_frame, (x, y), (x+w, y+h), (0, 255, 0), 2)

            # Convert to QImage
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            qt_image = QImage(
                rgb_frame.data, 
                w, 
                h, 
                bytes_per_line, 
                QImage.Format.Format_RGB888
            )

            # Update preview
            pixmap = QPixmap.fromImage(qt_image)
            self.face_preview_label.setPixmap(
                pixmap.scaled(
                    300, 
                    300, 
                    Qt.AspectRatioMode.KeepAspectRatio
                )
            )

            # If a face is detected, capture and stop
            if len(faces) > 0:
                self.stop_face_capture(frame)

        except Exception as e:
            QMessageBox.critical(self, "Face Capture Error", str(e))
            self.stop_face_capture()

    def stop_face_capture(self, frame=None):
        """
        Stop face capture and save the image
        """
        # Stop timer
        self.capture_timer.stop()

        # Release webcam
        if self.video_capture:
            self.video_capture.release()
            self.video_capture = None

        # Reset button
        self.capture_button.setEnabled(True)
        self.capture_button.setText("Capture Face")

        # Save face image
        if frame is not None:
            # Create directory if not exists
            os.makedirs(os.path.join(DATA_DIR, 'student_faces'), exist_ok=True)

            # Generate unique filename
            student_id = self.student_id_input.text()
            self.face_image_path = os.path.join(
                DATA_DIR, 
                'student_faces', 
                f'{student_id}_face.jpg'
            )

            # Save image
            cv2.imwrite(self.face_image_path, frame)

    def register_student(self):
        """Register a new student."""
        try:
            # Get form data
            student_id = self.student_id_input.text().strip()

            # Get name information
            first_name = self.first_name_input.text().strip()
            last_name = self.last_name_input.text().strip()

            email = self.email_input.text().strip()
            phone = self.phone_input.text().strip()
            date_of_birth = self.date_of_birth_input.date().toString("yyyy-MM-dd")
            gender = self.gender_input.currentText()

            # Validate required fields
            if not first_name:
                QMessageBox.warning(self, "Validation Error", "First name is required")
                return

            if not last_name:
                QMessageBox.warning(self, "Validation Error", "Last name is required")
                return

            if not email:
                QMessageBox.warning(self, "Validation Error", "Email is required")
                return

            if not phone:
                QMessageBox.warning(self, "Validation Error", "Phone number is required")
                return

            if not gender:
                QMessageBox.warning(self, "Validation Error", "Gender is required")
                return

            # Check for face image
            face_image_path = ""
            if hasattr(self, 'captured_image') and self.captured_image:
                face_image_path = self.captured_image
            else:
                reply = QMessageBox.question(
                    self, 
                    "Missing Face Image", 
                    "No face image captured. Do you want to proceed without a face image?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    return

            # Set default student ID if none provided
            if not student_id:
                import uuid
                student_id = f"STU-{str(uuid.uuid4())[:8].upper()}"

            # Gather student information
            student_dict = {
                'student_id': student_id,
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'phone': phone,
                'date_of_birth': date_of_birth,
                'gender': gender,
                'face_image_path': face_image_path
           }

            # Use the database method to add student
            try:
                new_student_id = self.db.add_student(student_dict)

                # Reset form after successful registration
                self.clear_form()

                # Refresh students table immediately
                self.load_students_table()

                # Show success message
                QMessageBox.information(self, "Success", f"Student {first_name} {last_name} registered successfully!")
            except Exception as db_error:
                QMessageBox.warning(self, "Database Error", f"Could not register student: {str(db_error)}")
                logging.error(f"Database error adding student: {str(db_error)}")

        except Exception as e:
            QMessageBox.warning(self, "Registration Error", str(e))
            logging.error(f"Student registration error: {str(e)}")

    def clear_form(self):
        """Clear all input fields."""
        self.student_id_input.clear()
        self.first_name_input.clear()  # Use first_name_input instead of name_input
        self.last_name_input.clear()   # Use last_name_input instead of name_input
        self.email_input.clear()
        self.phone_input.clear()
        self.gender_input.setCurrentIndex(0)
        self.date_of_birth_input.setDate(QDate.currentDate())
    
        # Reset face capture
        self.captured_image = None

class RegistrationTab(QWidget):
    def __init__(self, parent=None):
        """Initialize the registration tab."""
        super().__init__(parent)
        
        # Database and logging
        self.db = Database()
        
        # Initialize face cascade
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        
        if self.face_cascade.empty():
            logging.error("Failed to load face detection classifier")
            QMessageBox.critical(self, "Error", "Face detection classifier failed to load")
        
        # Initialize UI
        self.init_ui()
        self.load_students_table()

    def init_ui(self):
        """Initialize the student registration UI."""
        main_layout = QHBoxLayout(self)
    
        # Left Column - Form
        left_column = QFrame()
        form_layout = QFormLayout(left_column)
    
        # Student ID
        self.student_id_input = QLineEdit()
        form_layout.addRow("Student ID:", self.student_id_input)
    
        # First Name & Last Name (replacing the single Name field)
        self.first_name_input = QLineEdit()
        form_layout.addRow("First Name:", self.first_name_input)
    
        self.last_name_input = QLineEdit()
        form_layout.addRow("Last Name:", self.last_name_input)
    
        # Date of Birth
        self.date_of_birth_input = QDateEdit()
        self.date_of_birth_input.setDisplayFormat("yyyy-MM-dd")
        self.date_of_birth_input.setDate(QDate.currentDate())
        form_layout.addRow("Date of Birth:", self.date_of_birth_input)
    
        # Email
        self.email_input = QLineEdit()
        form_layout.addRow("Email:", self.email_input)
    
        # Phone
        self.phone_input = QLineEdit()
        form_layout.addRow("Phone:", self.phone_input)
    
        # Gender
        self.gender_input = QComboBox()
        self.gender_input.addItems(["", "Male", "Female", "Other"])
        form_layout.addRow("Gender:", self.gender_input)
    
        # Face Recognition Section
        face_section = QGroupBox("Face Recognition")
        face_layout = QVBoxLayout(face_section)
    
        # Camera View
        self.camera_label = QLabel("Camera Feed")
        self.camera_label.setFixedSize(320, 240)
        self.camera_label.setStyleSheet("border: 1px solid black;")
    
        # Camera Control Buttons
        camera_button_layout = QHBoxLayout()
    
        # Turn On Camera Button
        self.turn_on_camera_btn = QPushButton("Turn On Camera")
        self.turn_on_camera_btn.clicked.connect(self.start_camera)
        camera_button_layout.addWidget(self.turn_on_camera_btn)
    
        # Stop Camera Button
        self.stop_camera_btn = QPushButton("Stop Camera")
        self.stop_camera_btn.clicked.connect(self.stop_camera)
        self.stop_camera_btn.setEnabled(False)
        camera_button_layout.addWidget(self.stop_camera_btn)
    
        # Capture Face Button
        self.capture_btn = QPushButton("Capture Face")
        self.capture_btn.clicked.connect(self.capture_face)
        camera_button_layout.addWidget(self.capture_btn)
    
        # Add to face section
        face_layout.addWidget(self.camera_label)
        face_layout.addLayout(camera_button_layout)
    
        # Face Detection Overlay
        self.face_overlay_label = QLabel()
        self.face_overlay_label.setFixedSize(320, 240)
        self.face_overlay_label.setStyleSheet("background-color: transparent;")
        face_layout.addWidget(self.face_overlay_label)
    
        # Add warning if face recognition is unavailable
        self.face_recognition_warning = QLabel()
        face_layout.addWidget(self.face_recognition_warning)
    
        # Buttons
        button_layout = QHBoxLayout()
    
        # Register Button
        self.register_btn = QPushButton("Register Student")
        self.register_btn.clicked.connect(self.register_student)
    
        # Clear Button
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_form)
    
        button_layout.addWidget(self.register_btn)
        button_layout.addWidget(self.clear_btn)
    
        # Add buttons to form layout
        form_layout.addRow(button_layout)
    
        # Right Column - Student List
        right_column = QFrame()
        right_layout = QVBoxLayout(right_column)
    
        # Students Table
        self.students_table = QTableWidget()
        self.students_table.setColumnCount(7)
        self.students_table.setHorizontalHeaderLabels(
            ["Student ID", "Name", "Email", "Phone", "Date of Birth", "Gender", "Actions"]
        )
        self.students_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    
        # Actions column buttons
        self.students_table.setColumnWidth(6, 100)
    
        # Add buttons to layout
        right_layout.addWidget(self.students_table)
    
        # Main Layout Arrangement
        main_layout.addWidget(left_column, 1)
        main_layout.addWidget(face_section, 1)
        main_layout.addWidget(right_column, 2)
    
        # Setup camera timer
        self.camera_timer = QTimer(self)
        self.camera_timer.timeout.connect(self.update_camera_frame)
    
        # Start camera
        self.start_camera()

    def start_camera(self):
        """Initialize and start the camera."""
        try:
            # Try multiple camera indices
            camera_indices = [0, 1, -1]
            camera_opened = False
            
            for index in camera_indices:
                self.capture = cv2.VideoCapture(index, cv2.CAP_DSHOW)
                if self.capture.isOpened():
                    camera_opened = True
                    break
            
            if not camera_opened:
                QMessageBox.warning(self, "Camera Error", "Could not open camera. No available camera found.")
                self.camera_label.setText("Camera Not Available")
                
                # Update button states
                self.turn_on_camera_btn.setEnabled(True)
                self.stop_camera_btn.setEnabled(False)
                self.capture_btn.setEnabled(False)
                
                return
            
            # Set camera properties for better compatibility
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            
            # Start timer to update camera feed
            self.camera_timer.start(30)  # 30 ms interval
            
            # Update camera state
            self.is_camera_running = True
            
            # Update button states
            self.turn_on_camera_btn.setEnabled(False)
            self.stop_camera_btn.setEnabled(True)
            self.capture_btn.setEnabled(True)
            
            # Clear previous camera label text
            self.camera_label.setText("Camera Feed")
        except Exception as e:
            QMessageBox.warning(self, "Camera Error", f"Could not start camera: {str(e)}")
            self.camera_label.setText("Camera Initialization Failed")
            
            # Update button states
            self.turn_on_camera_btn.setEnabled(True)
            self.stop_camera_btn.setEnabled(False)
            self.capture_btn.setEnabled(False)

    def stop_camera(self):
        """Stop the camera."""
        try:
            # Stop timer
            self.camera_timer.stop()
            
            # Release camera
            if hasattr(self, 'capture'):
                self.capture.release()
            
            # Clear camera label
            self.camera_label.clear()
            self.camera_label.setText("Camera Feed")
            
            # Update camera state
            self.is_camera_running = False
            
            # Update button states
            self.turn_on_camera_btn.setEnabled(True)
            self.stop_camera_btn.setEnabled(False)
            self.capture_btn.setEnabled(False)
        except Exception as e:
            QMessageBox.warning(self, "Camera Error", f"Could not stop camera: {str(e)}")

    def update_camera_frame(self):
        """Update camera frame in the UI with face detection."""
        try:
            ret, frame = self.capture.read()
            
            if not ret:
                # If frame reading fails, stop the camera
                self.stop_camera()
                QMessageBox.warning(self, "Camera Error", "Could not read camera frame")
                return
            
            # Convert frame to grayscale for face detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detect faces
            faces = self.face_cascade.detectMultiScale(
                gray, 
                scaleFactor=1.1, 
                minNeighbors=5, 
                minSize=(30, 30)
            )
            
            # Draw rectangles around detected faces
            for (x, y, w, h) in faces:
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            
            # Convert frame to RGB for display
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Convert to QImage
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            
            # Scale image to fit label
            scaled_image = qt_image.scaled(
                self.camera_label.size(), 
                Qt.AspectRatioMode.KeepAspectRatio
            )
            
            # Set image
            self.camera_label.setPixmap(QPixmap.fromImage(scaled_image))
            
            # Update face count overlay
            face_count_text = f"Faces Detected: {len(faces)}"
            self.face_overlay_label.setText(face_count_text)
            self.face_overlay_label.setStyleSheet("""
                color: green;
                font-weight: bold;
                background-color: rgba(255, 255, 255, 100);
                padding: 5px;
            """)
        
        except Exception as e:
            # Stop camera if any error occurs during frame update
            self.stop_camera()
            QMessageBox.warning(self, "Camera Error", f"Camera frame update failed: {str(e)}")

    def capture_face(self):
        """Capture face from camera."""
        try:
            ret, frame = self.capture.read()
        
            if not ret:
                QMessageBox.warning(self, "Camera Error", "Could not read camera frame")
                return
            
            # Convert frame to grayscale for face detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
            # Detect faces
            faces = self.face_cascade.detectMultiScale(
                gray, 
                scaleFactor=1.1, 
                minNeighbors=5, 
                minSize=(100, 100)
            )
        
            if len(faces) == 0:
                QMessageBox.warning(self, "Face Capture", "No clear face detected. Please adjust position.")
                return
            elif len(faces) > 1:
                QMessageBox.warning(self, "Face Capture", "Multiple faces detected. Please capture only one face.")
                return
        
            # Get the first (and only) face
            (x, y, w, h) = faces[0]
        
            # Extract face region with some margin
            face_img = frame[y:y+h, x:x+w]
        
            # Create capture directory if it doesn't exist
            capture_dir = Path(DATA_DIR) / "student_captures"
            capture_dir.mkdir(parents=True, exist_ok=True)
        
            # Generate unique filename
            current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
        
            # Use student ID if available, otherwise use timestamp
            student_id = self.student_id_input.text().strip()
            if student_id:
                filename = f"{student_id}_{current_time}.png"
            else:
                filename = f"face_capture_{current_time}.png"
            
            capture_path = capture_dir / filename
        
            # Save image
            cv2.imwrite(str(capture_path), face_img)
        
            # Store the path for later use in registration
            self.captured_image = str(capture_path)
        
            # Log successful capture
            logging.info(f"Face captured successfully: {self.captured_image}")
        
            # Show captured face in a dialog
            captured_pixmap = QPixmap(str(capture_path))
            captured_dialog = QDialog(self)
            captured_dialog.setWindowTitle("Captured Face")
            dialog_layout = QVBoxLayout(captured_dialog)
        
            face_label = QLabel()
            face_label.setPixmap(captured_pixmap.scaled(
                320, 240, 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            ))
            dialog_layout.addWidget(face_label)
        
            confirm_btn = QPushButton("Confirm")
            confirm_btn.clicked.connect(captured_dialog.accept)
            dialog_layout.addWidget(confirm_btn)
        
            captured_dialog.exec()
        
            # Show success message
            QMessageBox.information(self, "Face Capture", "Face captured successfully")
    
        except Exception as e:
            QMessageBox.critical(self, "Face Capture Error", str(e))
            logging.error(f"Face capture error: {str(e)}")

    def register_student(self):
        """Register a new student."""
        try:
            # Get form data
            student_id = self.student_id_input.text().strip()
        
            # Get name information
            first_name = self.first_name_input.text().strip()
            last_name = self.last_name_input.text().strip()
        
            email = self.email_input.text().strip()
            phone = self.phone_input.text().strip()
            date_of_birth = self.date_of_birth_input.date().toString("yyyy-MM-dd")
            gender = self.gender_input.currentText()
        
            # Validate required fields
            if not first_name:
                QMessageBox.warning(self, "Validation Error", "First name is required")
                return
        
            if not last_name:
                QMessageBox.warning(self, "Validation Error", "Last name is required")
                return
        
            if not email:
                QMessageBox.warning(self, "Validation Error", "Email is required")
                return
        
            if not phone:
                QMessageBox.warning(self, "Validation Error", "Phone number is required")
                return
        
            if not gender:
                QMessageBox.warning(self, "Validation Error", "Gender is required")
                return
        
            # Check for face image
            face_image_path = ""
            if hasattr(self, 'captured_image') and self.captured_image:
                face_image_path = self.captured_image
            else:
                reply = QMessageBox.question(
                    self, 
                    "Missing Face Image", 
                    "No face image captured. Do you want to proceed without a face image?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    return
        
            # Set default student ID if none provided
            if not student_id:
                import uuid
                student_id = f"STU-{str(uuid.uuid4())[:8].upper()}"
        
            # Gather student information
            student_dict = {
                'student_id': student_id,
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'phone': phone,
                'date_of_birth': date_of_birth,
                'gender': gender,
                'face_image_path': face_image_path
            }
        
            # Use the database method to add student
            new_student_id = self.db.add_student(student_dict)
        
            # Reset form after successful registration
            self.clear_form()
        
            # Refresh students table immediately
            self.load_students_table()
        
            # Show success message
            QMessageBox.information(self, "Success", f"Student {first_name} {last_name} registered successfully!")
        
        except Exception as e:
            QMessageBox.warning(self, "Registration Error", str(e))
            logging.error(f"Student registration error: {str(e)}")
    
    def load_students_table(self):
        """Load students from database into the table."""
        try:
            # Clear existing rows
            self.students_table.setRowCount(0)
            
            # Connect to database
            students = self.db.get_students()
            
            # Populate table
            self.students_table.setRowCount(len(students))
            for row, student in enumerate(students):
                # Combine first and last name if name is not present
                full_name = student.get('name') or f"{student.get('first_name', '')} {student.get('last_name', '')}".strip()
                
                # Add student details
                self.students_table.setItem(row, 0, QTableWidgetItem(student.get('student_id', '')))
                self.students_table.setItem(row, 1, QTableWidgetItem(full_name))
                self.students_table.setItem(row, 2, QTableWidgetItem(student.get('email', '')))
                self.students_table.setItem(row, 3, QTableWidgetItem(student.get('phone', '')))
                self.students_table.setItem(row, 4, QTableWidgetItem(student.get('date_of_birth', '')))
                self.students_table.setItem(row, 5, QTableWidgetItem(student.get('gender', '')))
                
                # Add action buttons
                action_widget = QWidget()
                action_layout = QHBoxLayout(action_widget)
                
                # Edit Button
                edit_btn = QPushButton("Edit")
                edit_btn.clicked.connect(lambda _, r=row: self.edit_student(r))
                action_layout.addWidget(edit_btn)
                
                # Delete Button
                delete_btn = QPushButton("Delete")
                delete_btn.clicked.connect(lambda _, r=row: self.delete_student(r))
                action_layout.addWidget(delete_btn)
                
                action_layout.setContentsMargins(0, 0, 0, 0)
                self.students_table.setCellWidget(row, 6, action_widget)
            
            # Resize columns
            self.students_table.resizeColumnsToContents()
        
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Could not load students: {str(e)}")

    def edit_student(self, row):
        """Edit a student's details."""
        # Get selected row
        current_row = row
        if current_row < 0:
            QMessageBox.warning(self, "Edit Error", "Please select a student to edit")
            return

        # Retrieve student details
        full_name = self.students_table.item(current_row, 1).text()
    
        # Split name into first and last names
        name_parts = full_name.split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        student_dict = {
            'student_id': self.students_table.item(current_row, 0).text(),
            'first_name': first_name,
            'last_name': last_name,
            'name': full_name,
            'email': self.students_table.item(current_row, 2).text(),
            'phone': self.students_table.item(current_row, 3).text(),
            'date_of_birth': self.students_table.item(current_row, 4).text(),
            'gender': self.students_table.item(current_row, 5).text()
        }

        # Populate form for editing
        self.student_id_input.setText(student_dict['student_id'])
        # Use first_name_input and last_name_input instead of name_input
        self.first_name_input.setText(first_name)
        self.last_name_input.setText(last_name)
        self.email_input.setText(student_dict['email'])
        self.phone_input.setText(student_dict['phone'])
        self.gender_input.setCurrentText(student_dict['gender'])
        self.date_of_birth_input.setDate(QDate.fromString(student_dict['date_of_birth'], "yyyy-MM-dd"))

    def delete_student(self, row):
        """Delete a student from the database."""
        # Get student ID from the table
        student_id = self.students_table.item(row, 0).text()
        student_name = self.students_table.item(row, 1).text()
        
        # Confirm deletion
        reply = QMessageBox.question(
            self, 
            "Confirm Deletion", 
            f"Are you sure you want to delete student {student_name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Connect to database
                self.db.delete_student(student_id)
                
                # Refresh table
                self.load_students_table()
                
                QMessageBox.information(self, "Deletion", 
                    f"Student {student_name} deleted successfully!")
            
            except Exception as e:
                QMessageBox.critical(self, "Deletion Error", f"Could not delete student: {str(e)}")

    def clear_form(self):
        """Clear all input fields."""
        self.student_id_input.clear()
        self.first_name_input.clear()  # Use first_name_input
        self.last_name_input.clear()   # Use last_name_input 
        self.email_input.clear()
        self.phone_input.clear()
        self.gender_input.setCurrentIndex(0)
        self.date_of_birth_input.setDate(QDate.currentDate())
    
        # Reset face capture
        self.captured_image = None
    
    def show_student_details(self, row):
        """Show details of a selected student."""
        try:
            # Retrieve student details from table
            student_dict = {
                'student_id': self.students_table.item(row, 0).text(),
                'name': self.students_table.item(row, 1).text(),
                'email': self.students_table.item(row, 2).text(),
                'phone': self.students_table.item(row, 3).text(),
                'date_of_birth': self.students_table.item(row, 4).text(),
                'gender': self.students_table.item(row, 5).text()
            }
            
            # Show details dialog
            details_dialog = StudentDetailDialog(student_dict, self)
            details_dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not show student details: {str(e)}")
        return None
