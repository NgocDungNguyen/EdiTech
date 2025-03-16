import os
import logging
import cv2
import numpy as np
import json
from pathlib import Path
from datetime import datetime
import sqlite3

import time
import threading
import queue
import csv
from datetime import datetime


from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QFileDialog,
    QFrame,
    QMessageBox,
    QScrollArea,
    QGraphicsScene,
    QGraphicsView,
    QLineEdit,
    QGridLayout,
    QTabWidget,
    QListWidget,
    QFormLayout,
    QGroupBox,
    QSplitter,
    QRadioButton,
    QButtonGroup,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSpacerItem,
    QSizePolicy,
    QDialog,
    QInputDialog,
    QProgressDialog,
    QApplication,
    QSlider,
)
from PyQt6.QtCore import Qt, QPointF, QRectF, QTimer, QSize
from PyQt6.QtGui import QFont, QImage, QPixmap, QPen, QColor, QIcon, QPainter, QPainterPath, QRadialGradient, QBrush
from PyQt6.QtMultimedia import QCamera, QMediaCaptureSession, QImageCapture
from PyQt6.QtMultimediaWidgets import QVideoWidget
from app.models.database import Database
from app.utils.config import DATA_DIR, ICONS_DIR


class DrawableGraphicsScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.points = []
        self.outline_points = []
        self.heatmap_data = []
        self.drawing = False
        self.current_path_item = None
        self.mode = "keypoints"  # Default mode
        self.last_point = None
        self.heat_brush_size = 20
        self.heat_intensity = 0.7

    def set_mode(self, mode):
        """Set the drawing mode."""
        self.mode = mode
        self.drawing = False
        self.last_point = None

    def mousePressEvent(self, event):
        """Handle mouse press events for annotations."""
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.scenePos()

            if self.mode == "keypoints":
                # Add point to scene with label (existing functionality)
                point_index = len(self.points) + 1
                self.addEllipse(
                    pos.x() - 4,
                    pos.y() - 4,
                    8,
                    8,
                    QPen(QColor(255, 0, 0)),
                    QColor(255, 0, 0),
                )

                # Add point number label
                text = self.addText(str(point_index))
                text.setPos(pos.x() + 5, pos.y() + 5)
                text.setDefaultTextColor(QColor(255, 0, 0))

                # Store point coordinates
                self.points.append((pos.x(), pos.y()))

            elif self.mode == "outline":
                # Start drawing outline
                self.drawing = True
                if not self.outline_points:
                    # First point of a new outline
                    self.outline_points.append((pos.x(), pos.y()))
                    self.current_path_item = self.addPath(
                        QPainterPath(QPointF(pos.x(), pos.y())),
                        QPen(QColor(0, 200, 0, 180), 2, Qt.PenStyle.SolidLine),
                    )
                self.last_point = pos

            elif self.mode == "heatmap":
                # Add heat point
                gradient = QRadialGradient(pos, self.heat_brush_size)
                gradient.setColorAt(
                    0, QColor(255, 0, 0, int(255 * self.heat_intensity))
                )
                gradient.setColorAt(1, QColor(255, 0, 0, 0))

                brush = QBrush(gradient)
                self.addEllipse(
                    pos.x() - self.heat_brush_size,
                    pos.y() - self.heat_brush_size,
                    self.heat_brush_size * 2,
                    self.heat_brush_size * 2,
                    QPen(Qt.PenStyle.NoPen),
                    brush,
                )

                # Store heatmap point data
                self.heatmap_data.append(
                    {
                        "x": pos.x(),
                        "y": pos.y(),
                        "size": self.heat_brush_size,
                        "intensity": self.heat_intensity,
                    }
                )

    def mouseMoveEvent(self, event):
        """Handle mouse move events for drawing outlines and heatmaps."""
        if self.mode == "outline" and self.drawing and self.last_point:
            pos = event.scenePos()

            # Update the current path by adding a line to the new position
            path = self.current_path_item.path()
            path.lineTo(pos)
            self.current_path_item.setPath(path)

            # Store the point
            self.outline_points.append((pos.x(), pos.y()))
            self.last_point = pos

    def mouseReleaseEvent(self, event):
        """Handle mouse release events."""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.mode == "outline" and self.drawing:
                self.drawing = False

    def clear_annotations(self):
        """Clear all annotations from the scene."""
        self.points = []
        self.outline_points = []
        self.heatmap_data = []
        self.current_path_item = None
        self.last_point = None
        self.drawing = False

        # Clear all items except the background pixmap (which should be the first item)
        items = list(self.items())
        if len(items) > 1:  # Keep the first item (background pixmap) if it exists
            for item in items[1:]:
                self.removeItem(item)

    def get_annotation_data(self):
        """Get the annotation data in a unified format."""
        data = {
            "mode": self.mode,
            "keypoints": self.points,
            "outline": self.outline_points,
            "heatmap": self.heatmap_data,
        }
        return data


class TrainingTab(QWidget):
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.current_image_path = None
        self.training_data = []
        self.init_ui()

    def init_ui(self):
        """Initialize the training interface UI with a cleaner, more compact layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Remove title and description labels - cleaner UI

        # Tab widget to separate different functions
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Create the tabs
        self.create_data_collection_tab()
        self.create_training_management_tab()
        self.create_testing_tab()

        # Status bar at the bottom
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #666; font-style: italic;")
        main_layout.addWidget(self.status_label)

        # Load existing training data
        self.load_training_data()
        
    def wheelEvent(self, event):
        """Handle wheel events for zooming."""
        if self.current_image_path and event.angleDelta().y() != 0:
            # Get the view under the cursor
            if self.view.underMouse():
                # Calculate zoom factor based on wheel delta
                zoom_in = event.angleDelta().y() > 0
                factor = 1.15 if zoom_in else 1/1.15
                
                # Apply zoom
                self.view.scale(factor, factor)
                self.zoom_factor *= factor
                
                # Update status
                self.update_image_status()
                
                # Accept the event
                event.accept()
                return
                
        # Call the parent implementation for other wheel events
        super().wheelEvent(event)
        
    def zoom_in(self):
        """Zoom in on the image."""
        if hasattr(self, 'current_image_path') and self.current_image_path:
            self.zoom_factor *= 1.2
            self.view.scale(1.2, 1.2)
            self.update_image_status()

    def zoom_out(self):
        """Zoom out on the image."""
        if hasattr(self, 'current_image_path') and self.current_image_path:
            self.zoom_factor /= 1.2
            self.view.scale(1/1.2, 1/1.2)
            self.update_image_status()

    def zoom_reset(self):
        """Reset zoom to fit the image in the view."""
        if hasattr(self, 'current_image_path') and self.current_image_path:
            if not self.scene.sceneRect().isEmpty():
                self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
                self.zoom_factor = 1.0
                self.update_image_status()

    def update_image_status(self):
        """Update image status with zoom information."""
        if hasattr(self, 'current_image_path') and self.current_image_path:
            filename = os.path.basename(self.current_image_path)
            zoom_percent = int(self.zoom_factor * 100)
            self.image_status.setText(f"{filename} (Zoom: {zoom_percent}%)")

    def create_data_collection_tab(self):
        """Create the data collection tab with improved spacing and layout."""
        data_collection_tab = QWidget()
        layout = QVBoxLayout(data_collection_tab)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Header section with annotation method selection - more compact
        header_layout = QHBoxLayout()  # Changed to horizontal layout for compactness
        
        # Add annotation method selection with better styling
        method_group = QGroupBox("Annotation Method")
        method_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        method_layout = QHBoxLayout()
        method_layout.setSpacing(10)  # Reduced spacing
        method_layout.setContentsMargins(10, 10, 10, 10)  # Reduced padding
        
        self.method_group = QButtonGroup()
        self.keypoints_radio = QRadioButton("Key Points")
        self.outline_radio = QRadioButton("Object Outline")
        self.heatmap_radio = QRadioButton("Heat Map")
        
        # Make radio buttons more compact but still readable
        radio_style = """
        QRadioButton {
            font-size: 12px;
            padding: 3px;
        }
        QRadioButton::indicator {
            width: 16px;
            height: 16px;
        }
        """
        self.keypoints_radio.setStyleSheet(radio_style)
        self.outline_radio.setStyleSheet(radio_style)
        self.heatmap_radio.setStyleSheet(radio_style)
        
        self.keypoints_radio.setChecked(True)
        self.method_group.addButton(self.keypoints_radio)
        self.method_group.addButton(self.outline_radio)
        self.method_group.addButton(self.heatmap_radio)
        
        # Add tooltips to explain each method
        self.keypoints_radio.setToolTip("Mark specific points on the subject (joints, face features, etc.)")
        self.outline_radio.setToolTip("Draw an outline around the subject to capture shape and boundaries")
        self.heatmap_radio.setToolTip("Create heat maps to indicate areas of importance")
        
        method_layout.addWidget(self.keypoints_radio)
        method_layout.addWidget(self.outline_radio)
        method_layout.addWidget(self.heatmap_radio)
        method_group.setLayout(method_layout)
        
        # Connect method change to update the interface
        self.keypoints_radio.toggled.connect(self.update_annotation_ui)
        self.outline_radio.toggled.connect(self.update_annotation_ui)
        self.heatmap_radio.toggled.connect(self.update_annotation_ui)
        
        header_layout.addWidget(method_group, 2)  # Give it more space
        
        # Heat map controls in header for more compact layout
        self.heatmap_controls = QGroupBox("Heat Map Settings")
        self.heatmap_controls.setStyleSheet("QGroupBox { font-weight: bold; }")
        heatmap_layout = QFormLayout()
        heatmap_layout.setSpacing(5)  # Reduced spacing
        heatmap_layout.setContentsMargins(10, 10, 10, 10)  # Reduced padding

        # Brush size slider with better labeling - more compact
        size_layout = QHBoxLayout()
        size_label = QLabel("S")  # Shorter label
        size_label.setFixedWidth(10)
        size_layout.addWidget(size_label)
        
        self.brush_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.brush_size_slider.setRange(5, 50)
        self.brush_size_slider.setValue(20)
        self.brush_size_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brush_size_slider.setTickInterval(10)  # Less ticks
        self.brush_size_slider.valueChanged.connect(self.update_heatmap_settings)
        size_layout.addWidget(self.brush_size_slider)
        
        large_label = QLabel("L")  # Shorter label
        large_label.setFixedWidth(10)
        size_layout.addWidget(large_label)
        
        heatmap_layout.addRow("Size:", size_layout)

        # Intensity slider with better labeling - more compact
        intensity_layout = QHBoxLayout()
        light_label = QLabel("-")  # Shorter label
        light_label.setFixedWidth(10)
        intensity_layout.addWidget(light_label)
        
        self.intensity_slider = QSlider(Qt.Orientation.Horizontal)
        self.intensity_slider.setRange(1, 10)
        self.intensity_slider.setValue(7)  # 0.7 intensity
        self.intensity_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.intensity_slider.setTickInterval(2)  # Less ticks
        self.intensity_slider.valueChanged.connect(self.update_heatmap_settings)
        intensity_layout.addWidget(self.intensity_slider)
        
        intense_label = QLabel("+")  # Shorter label
        intense_label.setFixedWidth(10)
        intensity_layout.addWidget(intense_label)
        
        heatmap_layout.addRow("Intensity:", intensity_layout)

        self.heatmap_controls.setLayout(heatmap_layout)
        self.heatmap_controls.setVisible(False)  # Initially hidden
        header_layout.addWidget(self.heatmap_controls, 1)
        
        layout.addLayout(header_layout)

        # Main content area with better proportions
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)  # Prevent sections from being collapsed completely
        
        # Left panel - controls with improved spacing - more compact
        control_panel = QWidget()
        control_layout = QVBoxLayout(control_panel)
        control_layout.setContentsMargins(0, 0, 5, 0)  # Reduced margins
        control_layout.setSpacing(8)  # Reduced spacing
        
        # Form group for data entry - more compact
        form_group = QGroupBox("Training Data Details")
        form_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        form_layout = QFormLayout()
        form_layout.setSpacing(6)  # Reduced spacing
        form_layout.setContentsMargins(10, 10, 10, 10)  # Reduced padding

        # Behavior Type Selection
        self.type_combo = QComboBox()
        self.type_combo.setMinimumHeight(25)  # Smaller height
        self.type_combo.addItems(
            [
                "Select Type",
                "Hand Raising",
                "Head Position",
                "Attention",
                "Engagement",
                "Distraction",
                "Sign Language",
                "Custom",
            ]
        )
        form_layout.addRow("Type:", self.type_combo)  # Shorter label

        # Add spacing between rows
        form_layout.setVerticalSpacing(6)  # Reduced spacing

        # Custom behavior type option
        self.custom_type_input = QLineEdit()
        self.custom_type_input.setMinimumHeight(25)  # Smaller height
        self.custom_type_input.setPlaceholderText("Enter custom behavior type")
        self.custom_type_input.setEnabled(False)
        form_layout.addRow("Custom:", self.custom_type_input)  # Shorter label

        # Connect type selection to enable/disable custom input
        self.type_combo.currentTextChanged.connect(self.on_type_changed)

        # Behavior Label with better spacing
        self.label_input = QLineEdit()
        self.label_input.setMinimumHeight(25)  # Smaller height
        self.label_input.setPlaceholderText(
            "E.g., 'attentive', 'distracted', 'hand_raised'"
        )
        form_layout.addRow("Label:", self.label_input)  # Shorter label

        # Activity options - radio buttons with better spacing - more compact
        activity_group = QGroupBox("Activity Type")
        activity_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        activity_layout = QHBoxLayout()  # Changed to horizontal
        activity_layout.setSpacing(10)  # Reduced spacing
        activity_layout.setContentsMargins(10, 10, 10, 10)  # Reduced padding

        self.activity_group = QButtonGroup()
        self.positive_radio = QRadioButton("Positive")  # Shorter text
        self.negative_radio = QRadioButton("Negative")  # Shorter text
        self.positive_radio.setStyleSheet(radio_style)
        self.negative_radio.setStyleSheet(radio_style)
        self.positive_radio.setChecked(True)

        self.activity_group.addButton(self.positive_radio)
        self.activity_group.addButton(self.negative_radio)

        activity_layout.addWidget(self.positive_radio)
        activity_layout.addWidget(self.negative_radio)
        activity_group.setLayout(activity_layout)
        form_layout.addRow(activity_group)

        # Notes field
        self.notes_input = QLineEdit()
        self.notes_input.setMinimumHeight(25)  # Smaller height
        self.notes_input.setPlaceholderText("Additional notes about this sample")
        form_layout.addRow("Notes:", self.notes_input)  # Shorter label

        form_group.setLayout(form_layout)
        control_layout.addWidget(form_group)

        # Image controls group with better spacing - more compact
        image_control_group = QGroupBox("Image Controls")
        image_control_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        image_control_layout = QVBoxLayout()
        image_control_layout.setSpacing(8)  # Reduced spacing
        image_control_layout.setContentsMargins(10, 10, 10, 10)  # Reduced padding

        # Button layout for load and capture
        button_layout = QHBoxLayout()
        
        # Load image button - more compact
        self.load_image_btn = QPushButton("Load")  # Shorter text
        self.load_image_btn.setIcon(QIcon(str(ICONS_DIR / "open.png")))
        self.load_image_btn.setMinimumHeight(30)  # Smaller height
        self.load_image_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                padding: 5px;
                border-radius: 3px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """
        )
        self.load_image_btn.clicked.connect(self.load_image)
        button_layout.addWidget(self.load_image_btn)

        # Camera capture option - more compact
        self.capture_image_btn = QPushButton("Camera")  # Shorter text
        self.capture_image_btn.setIcon(QIcon(str(ICONS_DIR / "camera.png")))
        self.capture_image_btn.setMinimumHeight(30)  # Smaller height
        self.capture_image_btn.clicked.connect(self.capture_from_camera)
        button_layout.addWidget(self.capture_image_btn)
        
        image_control_layout.addLayout(button_layout)

        # Action buttons in a grid - more compact
        action_layout = QGridLayout()
        action_layout.setSpacing(6)  # Reduced spacing

        self.clear_points_btn = QPushButton("Clear")  # Shorter text
        self.clear_points_btn.setIcon(QIcon(str(ICONS_DIR / "clear.png")))
        self.clear_points_btn.setMinimumHeight(30)  # Smaller height
        self.clear_points_btn.setEnabled(False)
        self.clear_points_btn.clicked.connect(self.clear_points)
        action_layout.addWidget(self.clear_points_btn, 0, 0)

        self.save_training_btn = QPushButton("Save")  # Shorter text
        self.save_training_btn.setIcon(QIcon(str(ICONS_DIR / "save.png")))
        self.save_training_btn.setMinimumHeight(30)  # Smaller height
        self.save_training_btn.setEnabled(False)
        self.save_training_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 5px;
                border-radius: 3px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #388E3C;
            }
            QPushButton:disabled {
                background-color: #A5D6A7;
                color: #E8F5E9;
            }
        """
        )
        self.save_training_btn.clicked.connect(self.save_training_data)
        action_layout.addWidget(self.save_training_btn, 0, 1)

        image_control_layout.addLayout(action_layout)

        # Instructions with better styling - more compact
        instruction_label = QLabel(
            "1. Select type/label  2. Load image  3. Mark annotations  4. Save"
        )  # Single line, more compact
        instruction_label.setStyleSheet("font-style: italic; color: #666; padding: 5px; font-size: 11px;")
        image_control_layout.addWidget(instruction_label)

        # Add a spacer to push everything up
        image_control_layout.addSpacerItem(
            QSpacerItem(
                20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
            )
        )

        image_control_group.setLayout(image_control_layout)
        control_layout.addWidget(image_control_group)

        # Set a fixed width for the control panel to prevent it from being too small
        control_panel.setMinimumWidth(250)  # Smaller minimum width
        control_panel.setMaximumWidth(300)  # Smaller maximum width
        splitter.addWidget(control_panel)

        # Right panel - image display with improvements
        image_panel = QWidget()
        image_layout = QVBoxLayout(image_panel)
        image_layout.setContentsMargins(5, 0, 0, 0)  # Reduced margins

        # Instruction label - more compact
        self.image_instruction_label = QLabel("Click to mark key points on the image")
        self.image_instruction_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_instruction_label.setStyleSheet(
            "font-style: italic; color: #666; padding: 3px; background-color: #f8f8f8; border-radius: 2px; font-size: 11px;"
        )
        self.image_instruction_label.setMinimumHeight(20)  # Smaller height
        
        # Create a layout for instruction and zoom controls
        header_controls = QHBoxLayout()
        header_controls.addWidget(self.image_instruction_label)
        
        # Add zoom controls
        zoom_controls = QHBoxLayout()
        zoom_controls.setSpacing(2)  # Very compact
        
        self.zoom_out_btn = QPushButton()
        self.zoom_out_btn.setIcon(QIcon(str(ICONS_DIR / "zoom-out.png")))
        self.zoom_out_btn.setToolTip("Zoom Out")
        self.zoom_out_btn.setMaximumSize(24, 24)  # Small square button
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        zoom_controls.addWidget(self.zoom_out_btn)
        
        self.zoom_reset_btn = QPushButton()
        self.zoom_reset_btn.setIcon(QIcon(str(ICONS_DIR / "zoom-reset.png")))
        self.zoom_reset_btn.setToolTip("Reset Zoom (Fit to View)")
        self.zoom_reset_btn.setMaximumSize(24, 24)  # Small square button
        self.zoom_reset_btn.clicked.connect(self.zoom_reset)
        zoom_controls.addWidget(self.zoom_reset_btn)
        
        self.zoom_in_btn = QPushButton()
        self.zoom_in_btn.setIcon(QIcon(str(ICONS_DIR / "zoom-in.png")))
        self.zoom_in_btn.setToolTip("Zoom In")
        self.zoom_in_btn.setMaximumSize(24, 24)  # Small square button
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        zoom_controls.addWidget(self.zoom_in_btn)
        
        header_controls.addLayout(zoom_controls)
        image_layout.addLayout(header_controls)

        # Create graphics scene and view with better visibility
        self.scene = DrawableGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setMinimumSize(600, 400)  # Slightly smaller minimum
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.view.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        self.view.setStyleSheet("background-color: #f0f0f0;")  # Light gray background
        
        # Setup scaling
        self.view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.view.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.zoom_factor = 1.0

        # Create a frame for the image view
        view_frame = QFrame()
        view_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        view_frame.setStyleSheet("background-color: white; border: 1px solid #ddd;")
        view_layout = QVBoxLayout(view_frame)
        view_layout.setContentsMargins(3, 3, 3, 3)  # Smaller margins
        view_layout.addWidget(self.view)

        image_layout.addWidget(view_frame, 1)  # Give image view a stretch factor of 1
        
        # Status display below the image - more compact
        status_layout = QHBoxLayout()
        status_label = QLabel("Status:")
        status_label.setFixedWidth(40)  # Smaller width
        status_label.setStyleSheet("font-size: 11px;")  # Smaller font
        self.image_status = QLabel("No image loaded")
        self.image_status.setStyleSheet("color: #666; font-style: italic; font-size: 11px;")  # Smaller font
        status_layout.addWidget(status_label)
        status_layout.addWidget(self.image_status)
        image_layout.addLayout(status_layout)

        splitter.addWidget(image_panel)

        # Set initial splitter sizes - give more space to the image panel
        splitter.setSizes([250, 750])  # More space for image
        layout.addWidget(splitter, 1)  # Give splitter a stretch factor of 1

        # Add the tab
        self.tab_widget.addTab(data_collection_tab, "Data Collection")

    def create_training_management_tab(self):
        """Create the training data management tab."""
        management_tab = QWidget()
        layout = QVBoxLayout(management_tab)

        # Table for showing all training data
        self.training_table = QTableWidget()
        self.training_table.setColumnCount(6)
        self.training_table.setHorizontalHeaderLabels(
            ["Type", "Label", "Points", "Date", "Status", "Actions"]
        )

        # Enable sorting
        self.training_table.setSortingEnabled(True)

        # Set column widths
        self.training_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.training_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )

        layout.addWidget(self.training_table)

        # Action buttons
        button_layout = QHBoxLayout()

        self.refresh_data_btn = QPushButton("Refresh Data")
        self.refresh_data_btn.setIcon(QIcon(str(ICONS_DIR / "refresh.png")))
        self.refresh_data_btn.clicked.connect(self.load_training_data)
        button_layout.addWidget(self.refresh_data_btn)

        self.export_data_btn = QPushButton("Export Data")
        self.export_data_btn.setIcon(QIcon(str(ICONS_DIR / "export.png")))
        self.export_data_btn.clicked.connect(self.export_training_data)
        button_layout.addWidget(self.export_data_btn)

        self.delete_all_btn = QPushButton("Delete All")
        self.delete_all_btn.setIcon(QIcon(str(ICONS_DIR / "delete.png")))
        self.delete_all_btn.setStyleSheet("background-color: #F44336; color: white;")
        self.delete_all_btn.clicked.connect(self.delete_all_training_data)
        button_layout.addWidget(self.delete_all_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # Add the tab
        self.tab_widget.addTab(management_tab, "Training Data Management")

    def create_testing_tab(self):
        """Create the testing tab."""
        testing_tab = QWidget()
        layout = QVBoxLayout(testing_tab)

        # Testing options in a grid
        grid_layout = QGridLayout()

        # Image testing
        image_group = QGroupBox("Test with Image")
        image_layout = QVBoxLayout()

        self.test_image_btn = QPushButton("Select Test Image")
        self.test_image_btn.setIcon(QIcon(str(ICONS_DIR / "image.png")))
        self.test_image_btn.clicked.connect(self.test_with_image)
        image_layout.addWidget(self.test_image_btn)

        image_layout.addWidget(QLabel("Upload an image to test behavior detection"))
        image_group.setLayout(image_layout)
        grid_layout.addWidget(image_group, 0, 0)

        # Camera testing
        camera_group = QGroupBox("Test with Camera")
        camera_layout = QVBoxLayout()

        self.test_camera_btn = QPushButton("Start Camera Test")
        self.test_camera_btn.setIcon(QIcon(str(ICONS_DIR / "camera.png")))
        self.test_camera_btn.clicked.connect(self.test_with_camera)
        camera_layout.addWidget(self.test_camera_btn)

        camera_layout.addWidget(QLabel("Use webcam for real-time behavior detection"))
        camera_group.setLayout(camera_layout)
        grid_layout.addWidget(camera_group, 0, 1)

        # Video testing
        video_group = QGroupBox("Test with Video")
        video_layout = QVBoxLayout()

        self.test_video_btn = QPushButton("Select Test Video")
        self.test_video_btn.setIcon(QIcon(str(ICONS_DIR / "video.png")))
        self.test_video_btn.clicked.connect(self.test_with_video)
        video_layout.addWidget(self.test_video_btn)

        video_layout.addWidget(QLabel("Upload a video to test behavior detection"))
        video_group.setLayout(video_layout)
        grid_layout.addWidget(video_group, 1, 0)

        # Batch testing
        batch_group = QGroupBox("Batch Testing")
        batch_layout = QVBoxLayout()

        self.test_batch_btn = QPushButton("Run Batch Test")
        self.test_batch_btn.setIcon(QIcon(str(ICONS_DIR / "batch.png")))
        self.test_batch_btn.clicked.connect(self.test_batch)
        batch_layout.addWidget(self.test_batch_btn)

        batch_layout.addWidget(QLabel("Test multiple samples at once"))
        batch_group.setLayout(batch_layout)
        grid_layout.addWidget(batch_group, 1, 1)

        layout.addLayout(grid_layout)

        # Test results area - modified for multiple test results
        results_group = QGroupBox("Test Results")
        results_layout = QVBoxLayout()

        # Add test count display and clear button
        test_header_layout = QHBoxLayout()
        self.test_count_label = QLabel("No tests run")
        test_header_layout.addWidget(self.test_count_label)

        clear_results_btn = QPushButton("Clear Results")
        clear_results_btn.setIcon(QIcon(str(ICONS_DIR / "clear.png")))
        clear_results_btn.clicked.connect(self.clear_test_results)
        test_header_layout.addWidget(clear_results_btn)

        results_layout.addLayout(test_header_layout)

        # Results table that can hold multiple test results
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)  # Added Test ID and Image columns
        self.results_table.setHorizontalHeaderLabels(
            ["Test ID", "Image/Source", "Behavior Type", "Label", "Confidence"]
        )

        # Set column widths
        self.results_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.results_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )

        results_layout.addWidget(self.results_table)

        # Visual results area - for displaying detected behaviors on images
        visual_results_layout = QHBoxLayout()

        self.result_image_label = QLabel("No test image")
        self.result_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_image_label.setMinimumHeight(200)
        self.result_image_label.setStyleSheet(
            "border: 1px solid #ddd; background-color: #f5f5f5;"
        )
        visual_results_layout.addWidget(self.result_image_label)

        results_layout.addLayout(visual_results_layout)

        # Status label for results
        self.test_result_label = QLabel("Run a test to see results")
        self.test_result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.test_result_label.setStyleSheet("font-style: italic; color: #666;")
        results_layout.addWidget(self.test_result_label)

        results_group.setLayout(results_layout)
        layout.addWidget(results_group)

        # Initialize test results storage
        self.test_results = []
        self.test_counter = 0

        # Add the tab
        self.tab_widget.addTab(testing_tab, "Testing & Evaluation")

    def on_type_changed(self, text):
        """Enable custom type input if 'Custom' is selected."""
        if text == "Custom":
            self.custom_type_input.setEnabled(True)
        else:
            self.custom_type_input.setEnabled(False)
            self.custom_type_input.clear()

    def load_image(self):
        """Load an image for training."""
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Select Training Image", "", "Images (*.png *.jpg *.jpeg)"
        )

        if file_name:
            self.process_image(file_name)

    def capture_from_camera(self):
        """Capture an image from the camera using Qt's camera support."""
        try:
            from PyQt6.QtMultimedia import QCamera, QMediaCaptureSession, QImageCapture
            from PyQt6.QtMultimediaWidgets import QVideoWidget

            # Create directory for captures if it doesn't exist
            captures_dir = DATA_DIR / "camera_captures"
            captures_dir.mkdir(parents=True, exist_ok=True)

            # Create a dialog to display camera feed
            camera_dialog = QDialog(self)
            camera_dialog.setWindowTitle("Camera Capture")
            camera_dialog.resize(800, 600)

            # Setup dialog layout
            layout = QVBoxLayout(camera_dialog)

            # Create video widget for camera preview
            viewfinder = QVideoWidget()
            layout.addWidget(viewfinder)

            # Setup camera
            self.camera = QCamera()
            self.capture_session = QMediaCaptureSession()
            self.capture_session.setCamera(self.camera)
            self.capture_session.setVideoOutput(viewfinder)

            # Setup image capture
            self.image_capture = QImageCapture()
            self.capture_session.setImageCapture(self.image_capture)

            # Path for saving captured image
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.capture_path = str(captures_dir / f"capture_{timestamp}.jpg")

            # Create capture button
            button_layout = QHBoxLayout()
            capture_btn = QPushButton("Capture")
            capture_btn.setIcon(QIcon(str(ICONS_DIR / "camera.png")))
            capture_btn.clicked.connect(self.on_capture_clicked)

            cancel_btn = QPushButton("Cancel")
            cancel_btn.clicked.connect(camera_dialog.reject)

            button_layout.addWidget(capture_btn)
            button_layout.addWidget(cancel_btn)
            layout.addLayout(button_layout)

            # Connect image saved signal
            self.image_capture.imageSaved.connect(self.on_image_saved)
            self.image_capture.errorOccurred.connect(self.on_capture_error)

            # Store dialog reference and show
            self.camera_dialog = camera_dialog

            # Start camera
            self.camera.start()

            # Show dialog
            result = camera_dialog.exec()

            # Cleanup
            self.camera.stop()
            self.status_label.setText("Camera capture completed.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Camera capture failed: {str(e)}")
            self.status_label.setText("Camera capture failed.")
            logging.error(f"Camera capture error: {e}")

    def on_capture_clicked(self):
        """Handle camera capture button click."""
        try:
            self.status_label.setText("Capturing image...")
            self.image_capture.captureToFile(self.capture_path)
        except Exception as e:
            logging.error(f"Error during capture: {e}")
            QMessageBox.critical(self, "Error", f"Failed to capture image: {str(e)}")

    def on_image_saved(self, id, path):
        """Handle saved image after capture."""
        try:
            self.process_image(path)
            self.camera_dialog.accept()
        except Exception as e:
            logging.error(f"Error processing captured image: {e}")
            QMessageBox.critical(self, "Error", f"Failed to process captured image: {str(e)}")

    def on_capture_error(self, id, error, message):
        """Handle image capture errors."""
        logging.error(f"Image capture error: {error}, {message}")
        QMessageBox.critical(self, "Error", f"Image capture failed: {message}")

    def update_heatmap_settings(self):
        """Update heat map brush size and intensity."""
        if hasattr(self, 'scene'):
            self.scene.heat_brush_size = self.brush_size_slider.value()
            self.scene.heat_intensity = self.intensity_slider.value() / 10.0
            
    def update_annotation_ui(self):
        """Update UI based on selected annotation method."""
        if self.keypoints_radio.isChecked():
            self.scene.set_mode("keypoints")
            self.image_instruction_label.setText("Click to mark key points on the image (in order)")
        elif self.outline_radio.isChecked():
            self.scene.set_mode("outline")
            self.image_instruction_label.setText("Click and drag to draw an outline around the subject")
        elif self.heatmap_radio.isChecked():
            self.scene.set_mode("heatmap")
            self.image_instruction_label.setText("Click to create heat map areas of importance")
        
        # Show/hide heatmap controls
        if hasattr(self, 'heatmap_controls') and self.heatmap_controls is not None:
            self.heatmap_controls.setVisible(self.heatmap_radio.isChecked())

    def process_image(self, file_path):
        """Process an image for training data collection."""
        try:
            # Create training images directory if it doesn't exist
            training_dir = DATA_DIR / "training_images"
            training_dir.mkdir(parents=True, exist_ok=True)

            # Copy image to training directory with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            image_name = f"training_{timestamp}{Path(file_path).suffix}"
            new_path = training_dir / image_name

            # Copy and load image
            img = cv2.imread(file_path)
            if img is None:
                raise ValueError(f"Could not read image from {file_path}")

            # Resize if too large for display
            h, w = img.shape[:2]
            if h > 800 or w > 1200:
                scale = min(800 / h, 1200 / w)
                img = cv2.resize(img, (int(w * scale), int(h * scale)))

            cv2.imwrite(str(new_path), img)
            self.current_image_path = str(new_path)

            # Reset the scene completely
            if hasattr(self, 'scene') and self.scene:
                old_scene = self.scene
                self.scene = DrawableGraphicsScene()
                # Set the mode based on current selection
                if hasattr(self, 'keypoints_radio') and self.keypoints_radio.isChecked():
                    self.scene.set_mode("keypoints")
                elif hasattr(self, 'outline_radio') and self.outline_radio.isChecked():
                    self.scene.set_mode("outline")
                elif hasattr(self, 'heatmap_radio') and self.heatmap_radio.isChecked():
                    self.scene.set_mode("heatmap")
                    
                self.view.setScene(self.scene)
                old_scene.deleteLater()
            else:
                self.scene = DrawableGraphicsScene()
                self.view.setScene(self.scene)

            # Display image in graphics scene
            pixmap = QPixmap(self.current_image_path)
            self.scene.addPixmap(pixmap)
            self.view.setSceneRect(QRectF(pixmap.rect()))
            self.view.fitInView(
                self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
            )

            # Enable controls
            self.clear_points_btn.setEnabled(True)
            self.save_training_btn.setEnabled(True)

            # Update status
            self.status_label.setText(f"Image loaded: {image_name}")
            self.update_annotation_ui()  # Update instruction based on current method

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to process image: {str(e)}")
            self.status_label.setText("Error processing image.")
            logging.error(f"Error processing image: {e}")

    def clear_points(self):
        """Clear all annotations from the current image and reset for a new annotation method."""
        if self.current_image_path:
            try:
                # Use proper method to clear all annotation types
                if hasattr(self, 'scene') and self.scene:
                    # Clear annotations but keep the background image
                    self.scene.clear_annotations()
                    
                    # Reset the scene's drawing mode based on the currently selected method
                    if hasattr(self, 'keypoints_radio') and self.keypoints_radio.isChecked():
                        self.scene.set_mode("keypoints")
                    elif hasattr(self, 'outline_radio') and self.outline_radio.isChecked():
                        self.scene.set_mode("outline")
                    elif hasattr(self, 'heatmap_radio') and self.heatmap_radio.isChecked():
                        self.scene.set_mode("heatmap")
                        
                    # Update UI instructions based on selected method
                    self.update_annotation_ui()
                    
                    # Update status
                    self.status_label.setText("Annotations cleared. Ready for new annotations.")
                else:
                    self.status_label.setText("No scene to clear.")
                    
            except Exception as e:
                logging.error(f"Error clearing annotations: {e}")
                QMessageBox.critical(self, "Error", f"Failed to clear annotations: {str(e)}")
        else:
            QMessageBox.information(self, "Information", "No image loaded to clear annotations from.")

    def save_training_data(self):
        """Save the training data to the database with enhanced annotation options."""
        if not self.current_image_path:
            QMessageBox.warning(self, "Warning", "Please load an image first!")
            return

        # Check if we have any annotations
        annotation_data = self.scene.get_annotation_data()
        has_data = (
            annotation_data["mode"] == "keypoints" and len(annotation_data["keypoints"]) > 0 or
            annotation_data["mode"] == "outline" and len(annotation_data["outline"]) > 0 or
            annotation_data["mode"] == "heatmap" and len(annotation_data["heatmap"]) > 0
        )
        
        if not has_data:
            QMessageBox.warning(
                self, "Warning", f"Please add some {annotation_data['mode']} annotations to the image!"
            )
            return

        # Get behavior type
        behavior_type = self.type_combo.currentText()
        if behavior_type == "Select Type":
            QMessageBox.warning(self, "Warning", "Please select a behavior type!")
            return

        if behavior_type == "Custom":
            behavior_type = self.custom_type_input.text().strip()
            if not behavior_type:
                QMessageBox.warning(
                    self, "Warning", "Please enter a custom behavior type!"
                )
                return

        # Get behavior label
        behavior_label = self.label_input.text().strip()
        if not behavior_label:
            QMessageBox.warning(self, "Warning", "Please enter a behavior label!")
            return

        # Get activity type
        activity_type = "positive" if self.positive_radio.isChecked() else "negative"

        # Get notes
        notes = self.notes_input.text().strip()

        try:
            # Save to database
            annotation_json = json.dumps(annotation_data)

            cursor = self.db.connection.cursor()
            cursor.execute(
                """
                INSERT INTO training_data
                (behavior_type, label, image_path, points, notes, is_positive, annotation_type, annotation_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    behavior_type,
                    behavior_label,
                    self.current_image_path,
                    json.dumps(annotation_data["keypoints"]),  # Keep points for backward compatibility
                    notes,
                    1 if activity_type == "positive" else 0,
                    annotation_data["mode"],
                    annotation_json
                ),
            )
            self.db.connection.commit()

            # Refresh training data table
            self.load_training_data()

            # Clear form for next entry
            self.scene.clear_annotations()
            pixmap = None  # Explicitly set to None
            self.current_image_path = None
            self.label_input.clear()
            self.notes_input.clear()
            self.clear_points_btn.setEnabled(False)
            self.save_training_btn.setEnabled(False)

            # IMPORTANT: Create a brand new scene instead of just clearing
            old_scene = self.scene
            self.scene = DrawableGraphicsScene()
            self.view.setScene(self.scene)
            old_scene.deleteLater()  # Properly clean up the old scene

            # Reset type to default
            self.type_combo.setCurrentIndex(0)
            self.custom_type_input.clear()
            self.custom_type_input.setEnabled(False)
            self.positive_radio.setChecked(True)

            QMessageBox.information(
                self, "Success", "Training data saved successfully!"
            )

            self.status_label.setText("Training data saved successfully.")

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to save training data: {str(e)}"
            )
            self.status_label.setText("Error saving training data.")
            logging.error(f"Error saving training data: {e}")

    def load_training_data(self):
        """Load existing training data from the database."""
        try:
            # Clear existing data
            self.training_table.setRowCount(0)

            # Query database
            cursor = self.db.connection.cursor()
            cursor.execute(
                """
                SELECT
                    id, behavior_type, label, image_path, points,
                    timestamp, notes, is_positive
                FROM training_data
                ORDER BY timestamp DESC
                """
            )

            # Convert rows to dictionaries for easier access
            training_data = []
            for row in cursor.fetchall():
                if isinstance(row, sqlite3.Row):
                    data = {}
                    for key in row.keys():
                        data[key] = row[key]
                else:
                    data = {
                        "id": row[0],
                        "behavior_type": row[1],
                        "label": row[2],
                        "image_path": row[3],
                        "points": row[4],
                        "timestamp": row[5],
                        "notes": row[6],
                        "is_positive": row[7],
                    }
                training_data.append(data)

            # Store for later use
            self.training_data = training_data

            # Populate table
            self.training_table.setRowCount(len(training_data))
            for row, data in enumerate(training_data):
                # Behavior type
                type_item = QTableWidgetItem(data.get("behavior_type", ""))
                self.training_table.setItem(row, 0, type_item)

                # Label
                label_item = QTableWidgetItem(data.get("label", ""))
                self.training_table.setItem(row, 1, label_item)

                # Points count
                points = json.loads(data.get("points", "[]"))
                points_item = QTableWidgetItem(f"{len(points)} points marked")
                self.training_table.setItem(row, 2, points_item)

                # Date
                timestamp = data.get("timestamp", "")
                if timestamp:
                    try:
                        # Format timestamp for display
                        date_obj = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                        formatted_date = date_obj.strftime("%Y-%m-%d %H:%M")
                    except BaseException:
                        formatted_date = timestamp
                else:
                    formatted_date = "Unknown"
                date_item = QTableWidgetItem(formatted_date)
                self.training_table.setItem(row, 3, date_item)

                # Status
                is_positive = data.get("is_positive", 0)
                status_text = "Positive Example" if is_positive else "Negative Example"
                status_item = QTableWidgetItem(status_text)
                status_item.setBackground(
                    QColor("#E8F5E9" if is_positive else "#FFEBEE")
                )
                self.training_table.setItem(row, 4, status_item)

                # Action buttons
                action_widget = QWidget()
                action_layout = QHBoxLayout(action_widget)
                action_layout.setContentsMargins(4, 0, 4, 0)

                # View button
                view_btn = QPushButton("View")
                view_btn.setStyleSheet("background-color: #2196F3; color: white;")
                view_btn.clicked.connect(
                    lambda _, id=data.get("id"): self.view_training_data(id)
                )
                action_layout.addWidget(view_btn)

                # Delete button
                delete_btn = QPushButton("Delete")
                delete_btn.setStyleSheet("background-color: #F44336; color: white;")
                delete_btn.clicked.connect(
                    lambda _, id=data.get("id"): self.delete_training_data(id)
                )
                action_layout.addWidget(delete_btn)

                self.training_table.setCellWidget(row, 5, action_widget)

            # Update status
            self.status_label.setText(f"Loaded {len(training_data)} training samples.")

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to load training data: {str(e)}"
            )
            self.status_label.setText("Error loading training data.")
            logging.error(f"Error loading training data: {e}")

    def view_training_data(self, data_id):
        """View details of a specific training data entry with support for all annotation types."""
        try:
            # Find the data
            data = next((d for d in self.training_data if d.get("id") == data_id), None)
            if not data:
                QMessageBox.warning(
                    self, "Not Found", f"Training data with ID {data_id} not found."
                )
                return

            # Create dialog
            dialog = QDialog(self)
            dialog.setWindowTitle("Training Data Details")
            dialog.setMinimumWidth(800)
            dialog.setMinimumHeight(600)

            # Main layout
            layout = QVBoxLayout(dialog)

            # Create a splitter for details and image
            splitter = QSplitter(Qt.Orientation.Horizontal)

            # Left side - details
            details_widget = QWidget()
            details_layout = QVBoxLayout(details_widget)

            # Form layout for details
            form_group = QGroupBox("Training Data Details")
            form_layout = QFormLayout()

            # ID
            id_label = QLabel(str(data.get("id", "")))
            form_layout.addRow("ID:", id_label)

            # Type
            type_label = QLabel(data.get("behavior_type", ""))
            form_layout.addRow("Behavior Type:", type_label)

            # Label
            label_label = QLabel(data.get("label", ""))
            form_layout.addRow("Behavior Label:", label_label)
            
            # Annotation Type
            annotation_type = data.get("annotation_type", "keypoints")
            annotation_label = QLabel(annotation_type)
            annotation_label.setStyleSheet("font-weight: bold;")
            form_layout.addRow("Annotation Type:", annotation_label)

            # Points count
            points = json.loads(data.get("points", "[]"))
            points_label = QLabel(f"{len(points)} points marked")
            form_layout.addRow("Key Points:", points_label)

            # Status
            is_positive = data.get("is_positive", 0)
            status_text = "Positive Example" if is_positive else "Negative Example"
            status_label = QLabel(status_text)
            status_label.setStyleSheet(
                f"color: {'green' if is_positive else 'red'}; font-weight: bold;"
            )
            form_layout.addRow("Status:", status_label)

            # Date
            timestamp = data.get("timestamp", "")
            if timestamp:
                try:
                    # Format timestamp for display
                    date_obj = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                    formatted_date = date_obj.strftime("%Y-%m-%d %H:%M")
                except BaseException:
                    formatted_date = timestamp
            else:
                formatted_date = "Unknown"
            date_label = QLabel(formatted_date)
            form_layout.addRow("Created:", date_label)

            # Notes
            notes_label = QLabel(data.get("notes", ""))
            notes_label.setWordWrap(True)
            form_layout.addRow("Notes:", notes_label)

            # Image path
            path_label = QLabel(data.get("image_path", ""))
            path_label.setWordWrap(True)
            path_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            form_layout.addRow("Image Path:", path_label)

            form_group.setLayout(form_layout)
            details_layout.addWidget(form_group)

            # Add a spacer to push everything up
            details_layout.addStretch()

            # Right side - image with annotations
            image_widget = QWidget()
            image_layout = QVBoxLayout(image_widget)

            # Create graphics scene and view for the image
            scene = QGraphicsScene()
            view = QGraphicsView(scene)
            view.setRenderHint(QPainter.RenderHint.Antialiasing)
            view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

            # Load image if available
            image_path = data.get("image_path", "")
            if image_path and os.path.exists(image_path):
                pixmap = QPixmap(image_path)
                scene.addPixmap(pixmap)

                # Get annotation data
                try:
                    # Try to get the full annotation data if it exists
                    annotation_data_str = data.get("annotation_data")
                    if annotation_data_str:
                        annotation_data = json.loads(annotation_data_str)
                        annotation_type = annotation_data.get("mode", "keypoints")
                    else:
                        # Fallback to legacy points only
                        annotation_data = {
                            "mode": "keypoints",
                            "keypoints": points,
                            "outline": [],
                            "heatmap": []
                        }
                        annotation_type = "keypoints"
                    
                    # Render the appropriate annotation type
                    if annotation_type == "keypoints":
                        # Add keypoints from stored data
                        for i, point in enumerate(annotation_data.get("keypoints", [])):
                            try:
                                x, y = point
                                # Draw point
                                scene.addEllipse(
                                    x - 4,
                                    y - 4,
                                    8,
                                    8,
                                    QPen(QColor(255, 0, 0)),
                                    QColor(255, 0, 0),
                                )

                                # Add point number label
                                text = scene.addText(str(i + 1))
                                text.setPos(x + 5, y + 5)
                                text.setDefaultTextColor(QColor(255, 0, 0))
                            except Exception as e:
                                logging.warning(f"Error displaying point {i}: {e}")
                                continue
                    
                    elif annotation_type == "outline":
                        # Draw outline from stored data
                        outline_points = annotation_data.get("outline", [])
                        if outline_points and len(outline_points) >= 2:
                            path = QPainterPath(QPointF(outline_points[0][0], outline_points[0][1]))
                            for point in outline_points[1:]:
                                path.lineTo(QPointF(point[0], point[1]))
                            
                            scene.addPath(
                                path, 
                                QPen(QColor(0, 200, 0, 180), 2, Qt.PenStyle.SolidLine)
                            )
                    
                    elif annotation_type == "heatmap":
                        # Draw heatmap from stored data
                        heatmap_points = annotation_data.get("heatmap", [])
                        for point in heatmap_points:
                            try:
                                x = point.get("x")
                                y = point.get("y")
                                size = point.get("size", 20)
                                intensity = point.get("intensity", 0.7)
                                
                                gradient = QRadialGradient(QPointF(x, y), size)
                                gradient.setColorAt(0, QColor(255, 0, 0, int(255 * intensity)))
                                gradient.setColorAt(1, QColor(255, 0, 0, 0))
                                
                                brush = QBrush(gradient)
                                scene.addEllipse(
                                    x - size,
                                    y - size,
                                    size * 2,
                                    size * 2,
                                    QPen(Qt.PenStyle.NoPen),
                                    brush
                                )
                            except Exception as e:
                                logging.warning(f"Error displaying heatmap point: {e}")
                                continue
                
                except Exception as e:
                    logging.error(f"Error rendering annotations: {e}")
                    # Add error text to scene
                    error_text = scene.addText(f"Error rendering annotations: {str(e)}")
                    error_text.setDefaultTextColor(QColor(255, 0, 0))
                    error_text.setPos(10, 10)

                view.setSceneRect(QRectF(pixmap.rect()))
                view.fitInView(scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
            else:
                label = QLabel("Image not found")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.setStyleSheet("color: red;")
                image_layout.addWidget(label)

            image_layout.addWidget(view)

            # Add widgets to splitter
            splitter.addWidget(details_widget)
            splitter.addWidget(image_widget)

            # Set initial splitter sizes
            splitter.setSizes([300, 500])

            # Add splitter to main layout
            layout.addWidget(splitter)

            # Add close button
            close_btn = QPushButton("Close")
            close_btn.setStyleSheet(
                "background-color: #2196F3; color: white; font-weight: bold; padding: 8px;"
            )
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn)

            # Show dialog
            dialog.exec()

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to view training data: {str(e)}"
            )
            logging.error(f"Error viewing training data: {e}")

    def delete_training_data(self, data_id):
        """Delete a specific training data entry."""
        try:
            # Find the data
            data = next((d for d in self.training_data if d.get("id") == data_id), None)
            if not data:
                QMessageBox.warning(
                    self, "Not Found", f"Training data with ID {data_id} not found."
                )
                return

            # Confirm deletion
            reply = QMessageBox.question(
                self,
                "Confirm Deletion",
                f"Are you sure you want to delete this training data?\n\nBehavior Type: {data.get('behavior_type', '')}\nLabel: {data.get('label', '')}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

            # Delete from database
            cursor = self.db.connection.cursor()
            cursor.execute("DELETE FROM training_data WHERE id = ?", (data_id,))
            self.db.connection.commit()

            # Check if image should be deleted too
            image_path = data.get("image_path", "")
            if image_path and os.path.exists(image_path):
                reply = QMessageBox.question(
                    self,
                    "Delete Image",
                    "Do you want to delete the associated image file as well?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )

                if reply == QMessageBox.StandardButton.Yes:
                    try:
                        os.remove(image_path)
                        self.status_label.setText(f"Deleted training data and image.")
                    except BaseException:
                        self.status_label.setText(
                            f"Deleted training data but could not delete image."
                        )

            # Refresh the data
            self.load_training_data()

            QMessageBox.information(
                self, "Success", "Training data deleted successfully."
            )

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to delete training data: {str(e)}"
            )
            logging.error(f"Error deleting training data: {e}")

    def delete_all_training_data(self):
        """Delete all training data."""
        try:
            # Get count of training data
            cursor = self.db.connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM training_data")
            count = cursor.fetchone()[0]

            if count == 0:
                QMessageBox.information(self, "Info", "No training data to delete.")
                return

            # Confirm deletion
            reply = QMessageBox.question(
                self,
                "Confirm Deletion",
                f"Are you sure you want to delete ALL {count} training data entries?\n\nThis action cannot be undone!",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

            # Additional confirmation
            confirm_text = "DELETE ALL"
            text, ok = QInputDialog.getText(
                self,
                "Confirm Deletion",
                f"Type '{confirm_text}' to confirm deletion of all training data:",
                QLineEdit.EchoMode.Normal,
            )

            if not ok or text != confirm_text:
                return

            # Get image paths before deletion
            cursor.execute("SELECT image_path FROM training_data")
            image_paths = [row[0] for row in cursor.fetchall() if row[0]]

            # Delete from database
            cursor.execute("DELETE FROM training_data")
            self.db.connection.commit()

            # Ask about deleting images
            if image_paths:
                reply = QMessageBox.question(
                    self,
                    "Delete Images",
                    f"Do you want to delete all {len(image_paths)} associated image files as well?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )

                if reply == QMessageBox.StandardButton.Yes:
                    deleted_count = 0
                    for path in image_paths:
                        try:
                            if os.path.exists(path):
                                os.remove(path)
                                deleted_count += 1
                        except Exception as e:
                            logging.warning(f"Could not delete image {path}: {e}")
                            continue

                    self.status_label.setText(
                        f"Deleted all training data and {deleted_count} images."
                    )
                else:
                    self.status_label.setText(
                        f"Deleted all training data. Images were kept."
                    )
            else:
                self.status_label.setText(f"Deleted all training data.")

            # Refresh the data
            self.load_training_data()

            QMessageBox.information(
                self, "Success", "All training data deleted successfully."
            )

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to delete all training data: {str(e)}"
            )
            logging.error(f"Error deleting all training data: {e}")

    def export_training_data(self):
        """Export training data to JSON file."""
        try:
            # Check if we have any data
            if not self.training_data:
                QMessageBox.information(self, "Info", "No training data to export.")
                return

            # Ask for file location
            file_name, _ = QFileDialog.getSaveFileName(
                self, "Export Training Data", "", "JSON Files (*.json)"
            )

            if not file_name:
                return

            # Add .json extension if not already there
            if not file_name.lower().endswith(".json"):
                file_name += ".json"

            # Prepare data for export
            export_data = []
            for item in self.training_data:
                # Create a clean version of the data for export
                export_item = {
                    "id": item.get("id"),
                    "behavior_type": item.get("behavior_type"),
                    "label": item.get("label"),
                    "is_positive": item.get("is_positive"),
                    "points": json.loads(item.get("points", "[]")),
                    "notes": item.get("notes"),
                    "timestamp": item.get("timestamp"),
                    "image_path": item.get("image_path"),
                }
                export_data.append(export_item)

            # Write to file
            with open(file_name, "w") as f:
                json.dump(export_data, f, indent=4)

            QMessageBox.information(
                self,
                "Success",
                f"Successfully exported {len(export_data)} training data entries to {file_name}.",
            )

            self.status_label.setText(f"Exported training data to {file_name}")

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to export training data: {str(e)}"
            )
            logging.error(f"Error exporting training data: {e}")

    def test_with_image(self):
        """Test behavior detection on an image with enhanced results display."""
        try:
            # Check if we have training data
            if not self.training_data:
                QMessageBox.warning(
                    self,
                    "Warning",
                    "No training data available. Please add some training data first.",
                )
                return

            # Ask for image
            file_name, _ = QFileDialog.getOpenFileName(
                self, "Select Test Image", "", "Images (*.png *.jpg *.jpeg)"
            )

            if not file_name:
                return

            # Process image - in a real system this would run through the model
            self.status_label.setText("Processing image for behavior detection...")

            # Increment test counter
            self.test_counter += 1
            test_id = f"T{self.test_counter}"

            # Store the original image for display
            test_img = cv2.imread(file_name)
            test_img_rgb = cv2.cvtColor(test_img, cv2.COLOR_BGR2RGB)

            # Get image file name for display
            img_name = os.path.basename(file_name)

            # For demonstration, we'll just randomly match with existing behaviors
            behavior_types = set(d.get("behavior_type") for d in self.training_data)

            # Generate test results for this image
            image_results = []

            for behavior_type in behavior_types:
                # Get a random label for this type
                matching_data = [
                    d
                    for d in self.training_data
                    if d.get("behavior_type") == behavior_type
                ]
                if matching_data:
                    sample = matching_data[0]
                    label = sample.get("label", "")
                else:
                    label = "Unknown"

                # Random confidence score for demo
                confidence = np.random.uniform(0.5, 0.99)

                # Add to results
                if confidence > 0.6:  # Only add significant detections
                    image_results.append({
                        "test_id": test_id,
                        "image": img_name,
                        "image_path": file_name,
                        "behavior_type": behavior_type,
                        "label": label,
                        "confidence": confidence,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })

            # Add results to our storage
            self.test_results.extend(image_results)

            # Update results table - add rows instead of replacing
            current_row_count = self.results_table.rowCount()
            self.results_table.setRowCount(current_row_count + len(image_results))

            # Add new results
            for i, result in enumerate(image_results):
                row = current_row_count + i

                # Test ID
                self.results_table.setItem(row, 0, QTableWidgetItem(result["test_id"]))

                # Image name
                self.results_table.setItem(row, 1, QTableWidgetItem(result["image"]))

                # Behavior type
                self.results_table.setItem(row, 2, QTableWidgetItem(result["behavior_type"]))

                # Label
                self.results_table.setItem(row, 3, QTableWidgetItem(result["label"]))

                # Confidence with color coding
                confidence = result["confidence"]
                conf_item = QTableWidgetItem(f"{confidence:.2f}")

                if confidence > 0.8:
                    conf_item.setBackground(QColor("#E8F5E9"))  # Green
                elif confidence > 0.6:
                    conf_item.setBackground(QColor("#FFF9C4"))  # Yellow
                else:
                    conf_item.setBackground(QColor("#FFEBEE"))  # Red

                self.results_table.setItem(row, 4, conf_item)

            # Display the test image
            if test_img_rgb is not None:
                height, width, channel = test_img_rgb.shape
                bytes_per_line = 3 * width
                q_img = QImage(test_img_rgb.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
                pixmap = QPixmap.fromImage(q_img)

                # Resize for display
                scaled_pixmap = pixmap.scaled(
                    self.result_image_label.width(), 
                    self.result_image_label.height(),
                    Qt.AspectRatioMode.KeepAspectRatio
                )
                self.result_image_label.setPixmap(scaled_pixmap)

            # Update test count
            self.test_count_label.setText(f"Tests run: {len(self.test_results)}")

            # Update results label
            self.test_result_label.setText(
                f"Test {test_id} completed on {img_name} with {len(image_results)} detections"
            )
            self.status_label.setText("Behavior detection test completed.")

            # Switch to the testing tab if not already there
            self.tab_widget.setCurrentIndex(2)  # Testing tab

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Test failed: {str(e)}")
            self.status_label.setText("Test failed.")
            logging.error(f"Error in test_with_image: {e}")

    def test_with_camera(self):
        """Test behavior detection using camera."""
        try:
            # Check if we have training data
            if not self.training_data:
                QMessageBox.warning(
                    self,
                    "Warning",
                    "No training data available. Please add some training data first.",
                )
                return

            # Open camera dialog
            camera_dialog = QDialog(self)
            camera_dialog.setWindowTitle("Camera Test")
            camera_dialog.setMinimumSize(800, 600)

            # Layout
            layout = QVBoxLayout(camera_dialog)

            # Label for camera feed
            feed_label = QLabel("Starting camera...")
            feed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            feed_label.setMinimumSize(640, 480)
            layout.addWidget(feed_label)

            # Results label
            results_label = QLabel("Detecting behaviors...")
            results_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(results_label)

            # Button to close
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(camera_dialog.reject)
            layout.addWidget(close_btn)

            # Start camera in a separate thread
            self.camera_running = True

            def camera_thread():
                try:
                    cap = cv2.VideoCapture(0)
                    if not cap.isOpened():
                        raise ValueError("Could not open camera")

                    while self.camera_running:
                        ret, frame = cap.read()
                        if not ret:
                            logging.warning("Failed to capture frame")
                            time.sleep(0.1)
                            continue

                        # Convert to Qt image
                        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        h, w, ch = rgb_image.shape
                        bytes_per_line = ch * w
                        qt_image = QImage(
                            rgb_image.data,
                            w,
                            h,
                            bytes_per_line,
                            QImage.Format.Format_RGB888,
                        )
                        pixmap = QPixmap.fromImage(qt_image)

                        # Resize if needed
                        if (
                            pixmap.width() > feed_label.width()
                            or pixmap.height() > feed_label.height()
                        ):
                            pixmap = pixmap.scaled(
                                feed_label.size(),
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation,
                            )

                        # Update the label
                        feed_label.setPixmap(pixmap)

                        # Simulated behavior detection
                        behaviors = []
                        for btype in set(
                            d.get("behavior_type") for d in self.training_data
                        ):
                            # Random detection with 30% probability
                            if np.random.random() < 0.3:
                                confidence = np.random.uniform(0.6, 0.95)
                                behaviors.append((btype, confidence))

                        if behaviors:
                            results_text = "Detected: " + ", ".join(
                                [f"{b[0]} ({b[1]:.2f})" for b in behaviors]
                            )
                        else:
                            results_text = "No behaviors detected"

                        results_label.setText(results_text)

                        # Process events to keep UI responsive
                        QApplication.processEvents()
                        
                        # Add a small delay to reduce CPU usage
                        time.sleep(0.03)

                    # Release camera
                    cap.release()

                except Exception as e:
                    logging.error(f"Camera thread error: {e}")
                    results_label.setText(f"Error: {str(e)}")

            # Start thread
            camera_thread = threading.Thread(target=camera_thread)
            camera_thread.daemon = True
            camera_thread.start()

            # Connect dialog close to stopping camera
            def on_dialog_finished():
                self.camera_running = False

            camera_dialog.finished.connect(on_dialog_finished)

            # Show dialog
            camera_dialog.exec()

            # Update status
            self.status_label.setText("Camera test completed.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Camera test failed: {str(e)}")
            self.status_label.setText("Camera test failed.")
            logging.error(f"Error in test_with_camera: {e}")

    def test_with_video(self):
        """Test behavior detection on a video."""
        try:
            # Check if we have training data
            if not self.training_data:
                QMessageBox.warning(
                    self,
                    "Warning",
                    "No training data available. Please add some training data first.",
                )
                return

            # Ask for video file
            file_name, _ = QFileDialog.getOpenFileName(
                self, "Select Test Video", "", "Videos (*.mp4 *.avi *.mov *.wmv)"
            )

            if not file_name:
                return

            # Show progress dialog
            progress_dialog = QProgressDialog(
                "Processing video...", "Cancel", 0, 100, self
            )
            progress_dialog.setWindowTitle("Video Test")
            progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            progress_dialog.show()

            # Update status
            self.status_label.setText(
                f"Processing video: {os.path.basename(file_name)}"
            )

            # In a real implementation, this would process the video and detect behaviors
            # For this demo, we'll just simulate processing
            import time

            for i in range(101):
                if progress_dialog.wasCanceled():
                    break

                progress_dialog.setValue(i)
                time.sleep(0.05)  # Simulate processing time

                # Update every 10 frames with simulated results
                if i % 10 == 0:
                    self.results_table.setRowCount(0)

                    # Random number of behaviors detected
                    behavior_count = np.random.randint(1, 4)
                    behavior_types = list(
                        set(d.get("behavior_type") for d in self.training_data)
                    )

                    if behavior_types:
                        selected_types = np.random.choice(
                            behavior_types,
                            size=min(behavior_count, len(behavior_types)),
                            replace=False,
                        )

                        # Add results
                        self.results_table.setRowCount(len(selected_types))
                        for j, behavior_type in enumerate(selected_types):
                            # Get a random label
                            matching_data = [
                                d
                                for d in self.training_data
                                if d.get("behavior_type") == behavior_type
                            ]
                            if matching_data:
                                sample = matching_data[0]
                                label = sample.get("label", "")
                            else:
                                label = "Unknown"

                            # Random confidence
                            confidence = np.random.uniform(0.4, 0.99)

                            # Add to table
                            self.results_table.setItem(
                                j, 0, QTableWidgetItem(behavior_type)
                            )
                            self.results_table.setItem(j, 1, QTableWidgetItem(label))
                            self.results_table.setItem(
                                j, 2, QTableWidgetItem(f"{confidence:.2f}")
                            )

                            # Color based on confidence
                            if confidence > 0.8:
                                self.results_table.item(j, 2).setBackground(
                                    QColor("#E8F5E9")
                                )
                            elif confidence > 0.6:
                                self.results_table.item(j, 2).setBackground(
                                    QColor("#FFF9C4")
                                )
                            else:
                                self.results_table.item(j, 2).setBackground(
                                    QColor("#FFEBEE")
                                )

                    # Update test label
                    self.test_result_label.setText(
                        f"Processing frame {i} of video {os.path.basename(file_name)}"
                    )

                    # Process events to keep UI responsive
                    QApplication.processEvents()

            # Close progress dialog
            progress_dialog.close()

            # Final update
            if not progress_dialog.wasCanceled():
                self.test_result_label.setText(
                    f"Video analysis complete: {os.path.basename(file_name)}"
                )
                self.status_label.setText("Video behavior detection completed.")

                # Show a summary dialog
                QMessageBox.information(
                    self,
                    "Video Analysis Complete",
                    f"Analysis of {os.path.basename(file_name)} is complete.\n\n"
                    "In a real implementation, this would show detailed results and statistics.",
                )
            else:
                self.test_result_label.setText("Video analysis canceled")
                self.status_label.setText("Video behavior detection canceled.")

            # Switch to the testing tab if not already there
            self.tab_widget.setCurrentIndex(2)  # Testing tab

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Video test failed: {str(e)}")
            self.status_label.setText("Video test failed.")
            logging.error(f"Error in test_with_video: {e}")

    def test_batch(self):
        """Run batch testing on multiple samples."""
        try:
            # Check if we have training data
            if not self.training_data:
                QMessageBox.warning(
                    self,
                    "Warning",
                    "No training data available. Please add some training data first.",
                )
                return

            # Ask for directory containing test images
            dir_name = QFileDialog.getExistingDirectory(
                self, "Select Directory with Test Images", ""
            )

            if not dir_name:
                return

            # Find all images in the directory
            image_extensions = (".jpg", ".jpeg", ".png", ".bmp")
            image_files = [
                f
                for f in os.listdir(dir_name)
                if os.path.isfile(os.path.join(dir_name, f))
                and f.lower().endswith(image_extensions)
            ]

            if not image_files:
                QMessageBox.warning(
                    self, "Warning", "No image files found in the selected directory."
                )
                return

            # Ask for confirmation
            reply = QMessageBox.question(
                self,
                "Confirm Batch Test",
                f"Run batch test on {len(image_files)} images in the selected directory?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

            # Show progress dialog
            progress_dialog = QProgressDialog(
                "Processing batch...", "Cancel", 0, len(image_files), self
            )
            progress_dialog.setWindowTitle("Batch Test")
            progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            progress_dialog.show()

            # Prepare results
            batch_results = []
            behavior_types = list(
                set(d.get("behavior_type") for d in self.training_data)
            )

            # Process each image
            for i, image_file in enumerate(image_files):
                if progress_dialog.wasCanceled():
                    break

                # Update progress
                progress_dialog.setValue(i)
                progress_dialog.setLabelText(
                    f"Processing image {i+1} of {len(image_files)}: {image_file}"
                )

                # In a real implementation, this would process each image
                # For this demo, we'll just simulate results
                image_results = []
                for behavior_type in behavior_types:
                    # Only include some behaviors with random probability
                    if np.random.random() > 0.3:
                        confidence = np.random.uniform(0.5, 0.99)

                        # Get a random label for this type
                        matching_data = [
                            d
                            for d in self.training_data
                            if d.get("behavior_type") == behavior_type
                        ]
                        if matching_data:
                            sample = matching_data[0]
                            label = sample.get("label", "")
                        else:
                            label = "Unknown"

                        image_results.append(
                            {
                                "image": image_file,
                                "behavior_type": behavior_type,
                                "label": label,
                                "confidence": confidence,
                            }
                        )

                batch_results.extend(image_results)

                # Process events to keep UI responsive
                QApplication.processEvents()

            # Close progress dialog
            progress_dialog.close()

            if progress_dialog.wasCanceled():
                self.status_label.setText("Batch test canceled.")
                return

            # Show results in the results table
            self.results_table.setRowCount(0)

            # Calculate average confidence by behavior type
            avg_confidence = {}
            count = {}

            for result in batch_results:
                behavior_type = result["behavior_type"]
                confidence = result["confidence"]

                if behavior_type not in avg_confidence:
                    avg_confidence[behavior_type] = 0
                    count[behavior_type] = 0

                avg_confidence[behavior_type] += confidence
                count[behavior_type] += 1

            # Calculate averages
            for behavior_type in avg_confidence:
                if count[behavior_type] > 0:
                    avg_confidence[behavior_type] /= count[behavior_type]

            # Add results to table
            self.results_table.setRowCount(len(avg_confidence))
            row = 0
            for behavior_type, confidence in avg_confidence.items():
                # Get a common label for this type
                matching_data = [
                    d
                    for d in self.training_data
                    if d.get("behavior_type") == behavior_type
                ]
                label = (
                    matching_data[0].get("label", "") if matching_data else "Unknown"
                )

                # Add to table
                self.results_table.setItem(row, 0, QTableWidgetItem(behavior_type))
                self.results_table.setItem(row, 1, QTableWidgetItem(label))
                self.results_table.setItem(
                    row, 2, QTableWidgetItem(f"{confidence:.2f} (avg)")
                )

                # Color based on confidence
                if confidence > 0.8:
                    self.results_table.item(row, 2).setBackground(QColor("#E8F5E9"))
                elif confidence > 0.6:
                    self.results_table.item(row, 2).setBackground(QColor("#FFF9C4"))
                else:
                    self.results_table.item(row, 2).setBackground(QColor("#FFEBEE"))

                row += 1

            # Update UI
            self.test_result_label.setText(
                f"Batch test completed on {len(image_files)} images with {len(batch_results)} detections"
            )
            self.status_label.setText("Batch test completed.")

            # Switch to the testing tab if not already there
            self.tab_widget.setCurrentIndex(2)  # Testing tab

            # Ask if user wants to export results
            reply = QMessageBox.question(
                self,
                "Export Results",
                "Do you want to export the detailed batch test results to a CSV file?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.export_batch_results(batch_results)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Batch test failed: {str(e)}")
            self.status_label.setText("Batch test failed.")
            logging.error(f"Error in test_batch: {e}")

    def export_batch_results(self, results):
        """Export batch test results to CSV."""
        try:
            if not results:
                QMessageBox.warning(self, "Warning", "No results to export.")
                return

            # Ask for file location
            file_name, _ = QFileDialog.getSaveFileName(
                self, "Export Batch Results", "", "CSV Files (*.csv)"
            )

            if not file_name:
                return

            # Add .csv extension if not already there
            if not file_name.lower().endswith(".csv"):
                file_name += ".csv"

            # Write to CSV file
            import csv

            with open(file_name, "w", newline="") as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow(["Image", "Behavior Type", "Label", "Confidence"])

                # Write data rows
                for result in results:
                    writer.writerow(
                        [
                            result["image"],
                            result["behavior_type"],
                            result["label"],
                            f"{result['confidence']:.4f}",
                        ]
                    )

            QMessageBox.information(
                self, "Export Complete", f"Results successfully exported to {file_name}"
            )

            self.status_label.setText(f"Batch results exported to {file_name}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export results: {str(e)}")
            logging.error(f"Error exporting batch results: {e}")

    def resizeEvent(self, event):
        """Handle resize events to adjust the image view."""
        super().resizeEvent(event)
        # Resize the image to fit the view if there's an image loaded
        if (
            hasattr(self, "view")
            and hasattr(self.scene, "sceneRect")
            and not self.scene.sceneRect().isEmpty()
        ):
            self.view.fitInView(
                self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
            )

    def closeEvent(self, event):
        """Clean up resources when closing the window."""
        # Ensure camera is stopped if running
        if hasattr(self, "camera_running"):
            self.camera_running = False

        # Accept the close event
        event.accept()
    
    def clear_test_results(self):
        """Clear all test results and properly reset testing state."""
        try:
            self.test_results = []
            self.results_table.setRowCount(0)
            self.test_count_label.setText("No tests run")
            
            # Clear image display
            self.result_image_label.clear()
            self.result_image_label.setText("No test image")
            self.test_result_label.setText("Run a test to see results")
            
            # Reset test counter
            self.test_counter = 0
            
            # Update status
            self.status_label.setText("Test results cleared")
        except Exception as e:
            logging.error(f"Error clearing test results: {e}")
            QMessageBox.critical(self, "Error", f"Failed to clear test results: {str(e)}")
