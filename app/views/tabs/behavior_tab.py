import sys
import os
import cv2
import numpy as np
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QComboBox,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap

# Conditional import to handle moviepy and fer issues
try:
    from fer import FER
except ImportError:
    print("Warning: FER library import failed. Emotion detection will be disabled.")
    FER = None

from app.models.database import Database


class BehaviorTab(QWidget):
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.face_encodings = None
        self.captured_image = None
        self.emotion_detector = None

        # Try to initialize emotion detector
        try:
            if FER:
                self.emotion_detector = FER(mtcnn=True)
        except Exception as e:
            print(f"Error initializing emotion detector: {e}")

        self.init_ui()
        self.setup_camera()

    def init_ui(self):
        """Initialize the behavior monitoring UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # Camera Feed Frame
        camera_frame = QFrame()
        camera_frame.setObjectName("cameraFrame")
        camera_layout = QVBoxLayout(camera_frame)

        # Camera Label
        self.camera_label = QLabel("Camera Feed")
        self.camera_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        camera_layout.addWidget(self.camera_label)

        # Emotion Detection Controls
        emotion_layout = QHBoxLayout()

        # Emotion Detection Dropdown
        self.emotion_combo = QComboBox()
        emotion_items = [
            "Real-time Emotion Detection",
            "Positive Behavior Tracking",
            "Negative Behavior Tracking",
        ]

        # Disable emotion detection if FER is not available
        if not FER:
            emotion_items[0] += " (Unavailable)"

        self.emotion_combo.addItems(emotion_items)
        emotion_layout.addWidget(self.emotion_combo)

        # Start/Stop Buttons
        self.start_btn = QPushButton("Start Monitoring")
        self.start_btn.clicked.connect(self.toggle_monitoring)
        emotion_layout.addWidget(self.start_btn)

        camera_layout.addLayout(emotion_layout)

        # Results Display
        self.results_label = QLabel("Behavior Monitoring Results")
        self.results_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        camera_layout.addWidget(self.results_label)

        layout.addWidget(camera_frame)

        # Styling
        self.setStyleSheet(
            """
            QFrame {
                background-color: white;
                border-radius: 10px;
                padding: 20px;
            }
            QPushButton {
                background-color: #1a73e8;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1557b0;
            }
        """
        )

        # Camera and Monitoring Setup
        self.camera = None
        self.monitoring = False

    def setup_camera(self):
        """Initialize camera for monitoring."""
        try:
            # Try multiple camera indices
            camera_indices = [0, 1, 2]
            self.camera = None

            for index in camera_indices:
                try:
                    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
                    if not cap.isOpened():
                        cap.release()
                        continue

                    # Test if camera can actually capture a frame
                    ret, _ = cap.read()
                    if not ret:
                        cap.release()
                        continue

                    self.camera = cap
                    break
                except Exception as inner_e:
                    print(f"Error trying camera index {index}: {inner_e}")

            if not self.camera:
                QMessageBox.warning(
                    self,
                    "Camera Error",
                    "No working camera found. Please connect a camera.",
                )
                return False

            # Start timer to update camera preview
            self.camera_timer = QTimer(self)
            self.camera_timer.timeout.connect(self.update_camera_preview)
            self.camera_timer.start(30)  # Update every 30ms

            return True
        except Exception as e:
            QMessageBox.critical(
                self, "Camera Setup Error", f"Could not initialize camera: {str(e)}"
            )
            return False

    def update_camera_preview(self):
        """Update the camera preview."""
        if not self.camera or not self.camera.isOpened():
            return

        ret, frame = self.camera.read()
        if ret:
            # Convert frame to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Convert frame for display
            h, w, ch = frame.shape
            bytes_per_line = ch * w
            qt_image = QImage(
                frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888
            )
            pixmap = QPixmap.fromImage(qt_image)

            # Scale pixmap to fit label
            self.camera_label.setPixmap(
                pixmap.scaled(
                    640,
                    480,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

    def toggle_monitoring(self):
        """Toggle behavior monitoring on and off."""
        if not self.camera or not self.camera.isOpened():
            if not self.setup_camera():
                return

        self.monitoring = not self.monitoring

        if self.monitoring:
            # Check if emotion detection is available
            if not self.emotion_detector:
                QMessageBox.warning(
                    self, "Emotion Detection", "Emotion detection is not available."
                )

            self.start_btn.setText("Stop Monitoring")
            self.start_monitoring()
        else:
            self.start_btn.setText("Start Monitoring")
            self.stop_monitoring()

    def start_monitoring(self):
        """Start continuous behavior monitoring."""
        self.monitoring_timer = QTimer(self)
        self.monitoring_timer.timeout.connect(self.process_frame)
        self.monitoring_timer.start(100)  # Process every 100ms

    def stop_monitoring(self):
        """Stop behavior monitoring."""
        if hasattr(self, "monitoring_timer"):
            self.monitoring_timer.stop()

        # Release camera
        if self.camera:
            self.camera.release()

        # Clear display
        self.camera_label.clear()
        self.results_label.clear()

    def process_frame(self):
        """Capture and process camera frame for behavior detection."""
        if not self.camera or not self.camera.isOpened():
            return

        ret, frame = self.camera.read()
        if not ret:
            return

        # Convert frame to RGB for emotion detection
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Detect emotions if detector is available
        if self.emotion_detector:
            try:
                emotions = self.emotion_detector.detect_emotions(rgb_frame)

                if emotions:
                    # Get dominant emotion
                    dominant_emotion = max(
                        emotions[0]["emotions"], key=emotions[0]["emotions"].get
                    )
                    emotion_score = emotions[0]["emotions"][dominant_emotion]

                    # Update results label
                    result_text = f"Dominant Emotion: {dominant_emotion} (Confidence: {emotion_score:.2f})"
                    self.results_label.setText(result_text)

                    # Record behavior in database
                    self.record_behavior(dominant_emotion, emotion_score)
            except Exception as e:
                print(f"Emotion detection error: {e}")

        # Display frame
        self.display_frame(frame)

    def display_frame(self, frame):
        """Display camera frame in the UI."""
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        qt_image = QImage(
            rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888
        )
        pixmap = QPixmap.fromImage(qt_image)
        self.camera_label.setPixmap(
            pixmap.scaled(640, 480, Qt.AspectRatioMode.KeepAspectRatio)
        )

    def record_behavior(self, emotion, confidence):
        """Record student behavior in the database."""
        try:
            # In a real-world scenario, you'd associate this with a specific
            # student and class
            self.db.record_behavior(
                class_id=None,  # Replace with actual class ID
                student_id=None,  # Replace with actual student ID
                behavior_type="emotion",
                behavior_value=f"{emotion}:{confidence}",
            )
        except Exception as e:
            print(f"Error recording behavior: {e}")

    def closeEvent(self, event):
        """Handle tab closure, release camera resources."""
        self.stop_monitoring()
        event.accept()
