from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QComboBox, QFileDialog, QFrame,
                               QMessageBox, QScrollArea, QGraphicsScene,
                               QGraphicsView, QLineEdit)
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QFont, QImage, QPixmap, QPen, QColor
import cv2
import numpy as np
import json
import os
from pathlib import Path
from datetime import datetime

from app.models.database import Database
from app.utils.config import DATA_DIR

class DrawableGraphicsScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.points = []
        self.drawing = False

    def mousePressEvent(self, event):
        """Handle mouse press events for point placement."""
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.scenePos()
            # Add point to scene
            self.addEllipse(pos.x() - 2, pos.y() - 2, 4, 4, 
                          QPen(QColor(255, 0, 0)), QColor(255, 0, 0))
            self.points.append((pos.x(), pos.y()))

    def clear_points(self):
        """Clear all points from the scene."""
        self.points = []
        self.clear()

class TrainingTab(QWidget):
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.current_image_path = None
        self.init_ui()

    def init_ui(self):
        """Initialize the training interface UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # Training Controls
        control_frame = QFrame()
        control_frame.setObjectName("controlFrame")
        control_layout = QVBoxLayout(control_frame)

        # Behavior Type Selection
        type_layout = QHBoxLayout()
        type_label = QLabel("Behavior Type:")
        type_label.setFont(QFont("Arial", 12))
        self.type_combo = QComboBox()
        self.type_combo.addItems([
            "Action", "Sign Language"
        ])
        type_layout.addWidget(type_label)
        type_layout.addWidget(self.type_combo)
        control_layout.addLayout(type_layout)

        # Behavior Label
        label_layout = QHBoxLayout()
        label_text = QLabel("Behavior Label:")
        label_text.setFont(QFont("Arial", 12))
        self.label_input = QLineEdit()
        self.label_input.setPlaceholderText("Enter behavior label (e.g., 'hand_raising')")
        label_layout.addWidget(label_text)
        label_layout.addWidget(self.label_input)
        control_layout.addLayout(label_layout)

        # Image Controls
        image_controls = QHBoxLayout()
        
        self.load_image_btn = QPushButton("Load Image")
        self.load_image_btn.clicked.connect(self.load_image)
        image_controls.addWidget(self.load_image_btn)
        
        self.clear_points_btn = QPushButton("Clear Points")
        self.clear_points_btn.clicked.connect(self.clear_points)
        self.clear_points_btn.setEnabled(False)
        image_controls.addWidget(self.clear_points_btn)
        
        self.save_training_btn = QPushButton("Save Training Data")
        self.save_training_btn.clicked.connect(self.save_training_data)
        self.save_training_btn.setEnabled(False)
        image_controls.addWidget(self.save_training_btn)
        
        control_layout.addLayout(image_controls)
        layout.addWidget(control_frame)

        # Image Display Area
        display_frame = QFrame()
        display_frame.setObjectName("displayFrame")
        display_layout = QVBoxLayout(display_frame)

        # Create graphics scene and view
        self.scene = DrawableGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setMinimumSize(800, 600)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        display_layout.addWidget(self.view)

        self.instruction_label = QLabel(
            "Load an image and click to place points marking important pose features."
        )
        self.instruction_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        display_layout.addWidget(self.instruction_label)

        layout.addWidget(display_frame)

        # Testing Section
        test_frame = QFrame()
        test_frame.setObjectName("testFrame")
        test_layout = QVBoxLayout(test_frame)

        test_label = QLabel("Model Testing")
        test_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        test_layout.addWidget(test_label)

        test_controls = QHBoxLayout()
        
        self.test_image_btn = QPushButton("Test with Image")
        self.test_image_btn.clicked.connect(self.test_with_image)
        test_controls.addWidget(self.test_image_btn)
        
        self.test_video_btn = QPushButton("Test with Video")
        self.test_video_btn.clicked.connect(self.test_with_video)
        test_controls.addWidget(self.test_video_btn)
        
        test_layout.addLayout(test_controls)

        self.test_result_label = QLabel("Test results will appear here")
        self.test_result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        test_layout.addWidget(self.test_result_label)

        layout.addWidget(test_frame)

        # Styling
        self.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 10px;
                padding: 15px;
            }
            QComboBox, QLineEdit {
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
                min-width: 200px;
            }
            QPushButton {
                background-color: #1a73e8;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
                font-size: 14px;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
            QGraphicsView {
                border: 1px solid #ddd;
                background-color: #f8f9fa;
            }
            #displayFrame {
                background-color: #f8f9fa;
            }
        """)

    def load_image(self):
        """Load an image for training."""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Select Training Image",
            "",
            "Images (*.png *.jpg *.jpeg)"
        )

        if file_name:
            try:
                # Create training images directory if it doesn't exist
                training_dir = DATA_DIR / "training_images"
                training_dir.mkdir(parents=True, exist_ok=True)

                # Copy image to training directory with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                image_name = f"training_{timestamp}{Path(file_name).suffix}"
                new_path = training_dir / image_name

                # Copy and load image
                cv2.imwrite(str(new_path), cv2.imread(file_name))
                self.current_image_path = str(new_path)

                # Display image in graphics scene
                self.scene.clear_points()
                pixmap = QPixmap(self.current_image_path)
                self.scene.addPixmap(pixmap)
                self.view.setSceneRect(QRectF(pixmap.rect()))
                self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

                # Enable controls
                self.clear_points_btn.setEnabled(True)
                self.save_training_btn.setEnabled(True)

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load image: {str(e)}")

    def clear_points(self):
        """Clear all marked points from the current image."""
        if self.current_image_path:
            # Reload the image
            self.scene.clear_points()
            pixmap = QPixmap(self.current_image_path)
            self.scene.addPixmap(pixmap)

    def save_training_data(self):
        """Save the training data to the database."""
        if not self.current_image_path or not self.scene.points:
            QMessageBox.warning(self, "Warning", "Please load an image and mark points first!")
            return

        behavior_type = self.type_combo.currentText().lower()
        behavior_label = self.label_input.text().strip()

        if not behavior_label:
            QMessageBox.warning(self, "Warning", "Please enter a behavior label!")
            return

        try:
            # Save to database
            cursor = self.db.connection.cursor()
            query = """
                INSERT INTO training_data 
                (behavior_type, label, image_path, points)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(query, (
                behavior_type,
                behavior_label,
                self.current_image_path,
                json.dumps(self.scene.points)
            ))
            self.db.connection.commit()

            # Clear form
            self.scene.clear_points()
            self.current_image_path = None
            self.label_input.clear()
            self.clear_points_btn.setEnabled(False)
            self.save_training_btn.setEnabled(False)
            self.view.setScene(QGraphicsScene())  # Clear view
            
            QMessageBox.information(
                self, 
                "Success", 
                "Training data saved successfully!"
            )

        except Exception as e:
            QMessageBox.critical(
                self, 
                "Error", 
                f"Failed to save training data: {str(e)}"
            )

    def test_with_image(self):
        """Test behavior detection with a single image."""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Select Test Image",
            "",
            "Images (*.png *.jpg *.jpeg)"
        )

        if file_name:
            try:
                # Load and process test image
                # This is a placeholder - implement actual behavior detection
                self.test_result_label.setText("Testing with image...")
                
                # Here you would:
                # 1. Load the test image
                # 2. Extract pose points
                # 3. Compare with trained models
                # 4. Display results

                QMessageBox.information(
                    self, 
                    "Test Complete", 
                    "Image testing completed. Implement actual behavior detection logic."
                )

            except Exception as e:
                QMessageBox.critical(
                    self, 
                    "Error", 
                    f"Failed to process test image: {str(e)}"
                )

    def test_with_video(self):
        """Test behavior detection with a video file."""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Select Test Video",
            "",
            "Videos (*.mp4 *.avi *.mov)"
        )

        if file_name:
            try:
                # Load and process test video
                # This is a placeholder - implement actual behavior detection
                self.test_result_label.setText("Testing with video...")
                
                # Here you would:
                # 1. Load the test video
                # 2. Process frame by frame
                # 3. Detect behaviors
                # 4. Display results

                QMessageBox.information(
                    self, 
                    "Test Complete", 
                    "Video testing completed. Implement actual behavior detection logic."
                )

            except Exception as e:
                QMessageBox.critical(
                    self, 
                    "Error", 
                    f"Failed to process test video: {str(e)}"
                )

    def resizeEvent(self, event):
        """Handle widget resize events."""
        super().resizeEvent(event)
        if self.current_image_path:
            self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
