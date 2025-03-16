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
        self.load_classes()
        self.class_selector.currentIndexChanged.connect(self.load_attendance_records)
        
        class_layout.addWidget(self.class_selector)
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
    
    def load_classes(self):
        try:
            classes = self.db.get_classes()
            if not classes:
                QMessageBox.warning(self, "No Classes", "No classes found in database")
                return
            
            self.class_selector.clear()
            self.class_selector.addItem("Select Class")
            
            for cls in classes:
                self.class_selector.addItem(
                    f"{cls['class_id']} - {cls['name']}", 
                    cls['class_id']
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load classes: {str(e)}")
            logging.error(f"Error loading classes: {e}")
    
    def load_attendance_records(self):
        """Load attendance records for selected class and date"""
        try:
            class_id = self.class_selector.currentData()
            selected_date = self.date_selector.date().toString("yyyy-MM-dd")
            
            if not class_id:
                return
            
            records = self.db.get_attendance_records(class_id, selected_date)
            
            # Clear existing table
            self.attendance_table.setRowCount(0)
            
            # Populate table
            for record in records:
                row = self.attendance_table.rowCount()
                self.attendance_table.insertRow(row)
                
                # Add data to table
                self.attendance_table.setItem(row, 0, QTableWidgetItem(record['student_id']))
                self.attendance_table.setItem(row, 1, QTableWidgetItem(record['name']))
                self.attendance_table.setItem(row, 2, QTableWidgetItem(record['check_in_time']))
                self.attendance_table.setItem(row, 3, QTableWidgetItem(record['status']))
                self.attendance_table.setItem(row, 4, QTableWidgetItem(record.get('location', '')))
                self.attendance_table.setItem(row, 5, QTableWidgetItem(record.get('notes', '')))
        
        except Exception as e:
            QMessageBox.warning(self, "Load Attendance", f"Error loading attendance: {e}")
    
    def perform_face_check_in(self):
        """Perform face recognition check-in"""
        try:
            class_id = self.class_selector.currentData()
            
            if not class_id:
                QMessageBox.warning(self, "Check-in", "Please select a class first")
                return
            
            # Perform face recognition
            result = self.face_recognition_manager.capture_and_recognize_face(class_id)
            
            if result['success']:
                matches = result['matches']
                
                if matches:
                    for match in matches:
                        QMessageBox.information(
                            self, 
                            "Face Check-in", 
                            f"Student {match['student_id']} checked in with {match['confidence']:.2%} confidence"
                        )
                    
                    # Reload attendance records
                    self.load_attendance_records()
                else:
                    QMessageBox.warning(self, "Check-in", "No known faces detected")
            else:
                QMessageBox.warning(self, "Check-in Error", result.get('error', 'Unknown error'))
        
        except Exception as e:
            QMessageBox.critical(self, "Face Check-in Error", str(e))
    
    def manual_check_in(self):
        """Manual student check-in dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Manual Check-in")
        layout = QVBoxLayout()
        
        # Student ID input
        student_id_layout = QHBoxLayout()
        student_id_label = QLabel("Student ID:")
        self.student_id_input = QLineEdit()
        student_id_layout.addWidget(student_id_label)
        student_id_layout.addWidget(self.student_id_input)
        layout.addLayout(student_id_layout)
        
        # Check-in button
        check_in_btn = QPushButton("Check In")
        check_in_btn.clicked.connect(lambda: self.process_manual_check_in(
            self.student_id_input.text(), 
            self.class_selector.currentData()
        ))
        layout.addWidget(check_in_btn)
        
        dialog.setLayout(layout)
        dialog.exec()

    def process_manual_check_in(self, student_id, class_id):
        """Process manual check-in for a student"""
        try:
            if not student_id or not class_id:
                QMessageBox.warning(self, "Error", "Please provide both student ID and class ID")
                return
            
            # Get current date and time
            check_in_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Mark attendance in database
            self.db.mark_attendance(
                class_id=class_id,
                student_id=student_id,
                status="present",
                check_in_time=check_in_time
            )
            
            QMessageBox.information(self, "Success", "Attendance marked successfully!")
            self.load_attendance_records()
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to process check-in: {str(e)}")
            logging.error(f"Manual check-in error: {e}")
