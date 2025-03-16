from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QFrame,
    QDateEdit,
    QFileDialog,
    QMessageBox,
    QScrollArea,
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import pandas as pd
import seaborn as sns
from datetime import datetime, timedelta
import json

from app.models.database import Database


class AnalyticsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.init_ui()

    def init_ui(self):
        """Initialize the analytics UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # Data Selection Controls
        control_frame = QFrame()
        control_frame.setObjectName("controlFrame")
        control_layout = QVBoxLayout(control_frame)

        # Class Selection
        class_layout = QHBoxLayout()
        class_label = QLabel("Select Class:")
        class_label.setFont(QFont("Arial", 12))
        self.class_combo = QComboBox()
        self.load_classes()
        class_layout.addWidget(class_label)
        class_layout.addWidget(self.class_combo)
        control_layout.addLayout(class_layout)

        # Date Range Selection
        date_layout = QHBoxLayout()

        start_date_label = QLabel("Start Date:")
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate().addDays(-30))
        date_layout.addWidget(start_date_label)
        date_layout.addWidget(self.start_date)

        end_date_label = QLabel("End Date:")
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        date_layout.addWidget(end_date_label)
        date_layout.addWidget(self.end_date)

        control_layout.addLayout(date_layout)

        # Analysis Type Selection
        type_layout = QHBoxLayout()
        type_label = QLabel("Analysis Type:")
        self.analysis_combo = QComboBox()
        self.analysis_combo.addItems(
            [
                "Attendance Overview",
                "Behavior Trends",
                "Emotion Analysis",
                "Student Engagement",
            ]
        )
        type_layout.addWidget(type_label)
        type_layout.addWidget(self.analysis_combo)
        control_layout.addLayout(type_layout)

        # Control Buttons
        button_layout = QHBoxLayout()

        self.generate_btn = QPushButton("Generate Report")
        self.generate_btn.clicked.connect(self.generate_report)
        button_layout.addWidget(self.generate_btn)

        self.export_btn = QPushButton("Export Data")
        self.export_btn.clicked.connect(self.export_data)
        button_layout.addWidget(self.export_btn)

        control_layout.addLayout(button_layout)
        layout.addWidget(control_frame)

        # Visualization Area
        viz_frame = QFrame()
        viz_frame.setObjectName("vizFrame")
        viz_layout = QVBoxLayout(viz_frame)

        # Create matplotlib figure
        self.figure, self.ax = plt.subplots(figsize=(10, 6))
        self.canvas = FigureCanvas(self.figure)
        viz_layout.addWidget(self.canvas)

        layout.addWidget(viz_frame)

        # Styling
        self.setStyleSheet(
            """
            QFrame {
                background-color: white;
                border-radius: 10px;
                padding: 15px;
            }
            QComboBox, QDateEdit {
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
            QPushButton:hover {
                background-color: #1557b0;
            }
            #vizFrame {
                background-color: #f8f9fa;
                min-height: 400px;
            }
        """
        )

    def load_classes(self):
        """Load available classes into the combo box."""
        try:
            cursor = self.db.connection.cursor()
            cursor.execute(
                """
                SELECT class_id, name, subject
                FROM classes
                ORDER BY name
            """
            )
            classes = cursor.fetchall()

            self.class_combo.clear()
            for class_data in classes:
                self.class_combo.addItem(
                    f"{class_data['name']} - {class_data['subject']}",
                    class_data["class_id"],
                )

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load classes: {str(e)}")

    def generate_report(self):
        """Generate and display the selected analysis report."""
        class_id = self.class_combo.currentData()
        if class_id is None:
            QMessageBox.warning(self, "Warning", "Please select a class first!")
            return

        analysis_type = self.analysis_combo.currentText()
        start_date = self.start_date.date().toPyDate()
        end_date = self.end_date.date().toPyDate()

        try:
            # Clear previous plot
            self.ax.clear()

            if analysis_type == "Attendance Overview":
                self.generate_attendance_report(class_id, start_date, end_date)
            elif analysis_type == "Behavior Trends":
                self.generate_behavior_report(class_id, start_date, end_date)
            elif analysis_type == "Emotion Analysis":
                self.generate_emotion_report(class_id, start_date, end_date)
            else:  # Student Engagement
                self.generate_engagement_report(class_id, start_date, end_date)

            self.canvas.draw()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate report: {str(e)}")

    def generate_attendance_report(self, class_id, start_date, end_date):
        """Generate attendance overview visualization."""
        cursor = self.db.connection.cursor()

        # Get attendance data
        cursor.execute(
            """
            SELECT DATE(check_in_time) as date,
                   status,
                   COUNT(*) as count
            FROM attendance
            WHERE class_id = %s
            AND check_in_time BETWEEN %s AND %s
            GROUP BY DATE(check_in_time), status
            ORDER BY date
        """,
            (class_id, start_date, end_date),
        )

        data = cursor.fetchall()

        if not data:
            self.ax.text(
                0.5, 0.5, "No attendance data available", ha="center", va="center"
            )
            return

        # Process data for plotting
        df = pd.DataFrame(data)
        pivot_data = df.pivot(index="date", columns="status", values="count").fillna(0)

        # Create stacked bar chart
        pivot_data.plot(kind="bar", stacked=True, ax=self.ax)

        self.ax.set_title("Daily Attendance Overview")
        self.ax.set_xlabel("Date")
        self.ax.set_ylabel("Number of Students")
        self.ax.legend(title="Status")
        plt.xticks(rotation=45)
        plt.tight_layout()

    def generate_behavior_report(self, class_id, start_date, end_date):
        """Generate behavior trends visualization."""
        cursor = self.db.connection.cursor()

        # Get behavior data
        cursor.execute(
            """
            SELECT behavior_type,
                   behavior_value,
                   COUNT(*) as count
            FROM behavior_records
            WHERE class_id = %s
            AND timestamp BETWEEN %s AND %s
            GROUP BY behavior_type, behavior_value
            ORDER BY behavior_type, count DESC
        """,
            (class_id, start_date, end_date),
        )

        data = cursor.fetchall()

        if not data:
            self.ax.text(
                0.5, 0.5, "No behavior data available", ha="center", va="center"
            )
            return

        # Process data for plotting
        df = pd.DataFrame(data)

        # Create grouped bar chart
        sns.barplot(
            data=df, x="behavior_type", y="count", hue="behavior_value", ax=self.ax
        )

        self.ax.set_title("Behavior Distribution")
        self.ax.set_xlabel("Behavior Type")
        self.ax.set_ylabel("Frequency")
        plt.xticks(rotation=45)
        plt.tight_layout()

    def generate_emotion_report(self, class_id, start_date, end_date):
        """Generate emotion analysis visualization."""
        cursor = self.db.connection.cursor()

        # Get emotion data
        cursor.execute(
            """
            SELECT DATE(timestamp) as date,
                   behavior_value as emotion,
                   COUNT(*) as count
            FROM behavior_records
            WHERE class_id = %s
            AND behavior_type = 'emotion'
            AND timestamp BETWEEN %s AND %s
            GROUP BY DATE(timestamp), behavior_value
            ORDER BY date
        """,
            (class_id, start_date, end_date),
        )

        data = cursor.fetchall()

        if not data:
            self.ax.text(
                0.5, 0.5, "No emotion data available", ha="center", va="center"
            )
            return

        # Process data for plotting
        df = pd.DataFrame(data)
        pivot_data = df.pivot(index="date", columns="emotion", values="count").fillna(0)

        # Create line plot
        pivot_data.plot(kind="line", marker="o", ax=self.ax)

        self.ax.set_title("Emotion Trends Over Time")
        self.ax.set_xlabel("Date")
        self.ax.set_ylabel("Frequency")
        plt.xticks(rotation=45)
        plt.tight_layout()

    def generate_engagement_report(self, class_id, start_date, end_date):
        """Generate student engagement visualization."""
        cursor = self.db.connection.cursor()

        # Get engagement indicators (hand raising, focus)
        cursor.execute(
            """
            SELECT s.name,
                   COUNT(CASE WHEN b.behavior_value IN ('hand_raising', 'focus')
                             THEN 1 END) as engagement_count
            FROM students s
            JOIN class_enrollments e ON s.student_id = e.student_id
            LEFT JOIN behavior_records b ON s.student_id = b.student_id
            WHERE e.class_id = %s
            AND (b.timestamp IS NULL OR b.timestamp BETWEEN %s AND %s)
            GROUP BY s.name
            ORDER BY engagement_count DESC
        """,
            (class_id, start_date, end_date),
        )

        data = cursor.fetchall()

        if not data:
            self.ax.text(
                0.5, 0.5, "No engagement data available", ha="center", va="center"
            )
            return

        # Process data for plotting
        df = pd.DataFrame(data)

        # Create horizontal bar chart
        sns.barplot(data=df, y="name", x="engagement_count", orient="h", ax=self.ax)

        self.ax.set_title("Student Engagement Levels")
        self.ax.set_xlabel("Engagement Indicators Count")
        self.ax.set_ylabel("Student Name")
        plt.tight_layout()

    def export_data(self):
        """Export the analyzed data to a file."""
        class_id = self.class_combo.currentData()
        if class_id is None:
            QMessageBox.warning(self, "Warning", "Please select a class first!")
            return

        try:
            # Get export file path
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export Data", "", "CSV Files (*.csv);;Excel Files (*.xlsx)"
            )

            if not file_path:
                return

            # Get data based on current analysis type
            analysis_type = self.analysis_combo.currentText()
            start_date = self.start_date.date().toPyDate()
            end_date = self.end_date.date().toPyDate()

            cursor = self.db.connection.cursor()

            if analysis_type == "Attendance Overview":
                cursor.execute(
                    """
                    SELECT s.student_id, s.name,
                           a.status, a.check_in_time
                    FROM attendance a
                    JOIN students s ON a.student_id = s.student_id
                    WHERE a.class_id = %s
                    AND a.check_in_time BETWEEN %s AND %s
                    ORDER BY a.check_in_time
                """,
                    (class_id, start_date, end_date),
                )

            elif analysis_type in ["Behavior Trends", "Emotion Analysis"]:
                cursor.execute(
                    """
                    SELECT s.student_id, s.name,
                           b.behavior_type, b.behavior_value,
                           b.timestamp
                    FROM behavior_records b
                    JOIN students s ON b.student_id = s.student_id
                    WHERE b.class_id = %s
                    AND b.timestamp BETWEEN %s AND %s
                    ORDER BY b.timestamp
                """,
                    (class_id, start_date, end_date),
                )

            else:  # Student Engagement
                cursor.execute(
                    """
                    SELECT s.student_id, s.name,
                           b.behavior_type, b.behavior_value,
                           b.timestamp
                    FROM students s
                    JOIN class_enrollments e ON s.student_id = e.student_id
                    LEFT JOIN behavior_records b ON s.student_id = b.student_id
                    WHERE e.class_id = %s
                    AND (b.timestamp IS NULL OR b.timestamp BETWEEN %s AND %s)
                    ORDER BY s.name, b.timestamp
                """,
                    (class_id, start_date, end_date),
                )

            data = cursor.fetchall()
            df = pd.DataFrame(data)

            # Export based on file extension
            if file_path.endswith(".csv"):
                df.to_csv(file_path, index=False)
            else:
                df.to_excel(file_path, index=False)

            QMessageBox.information(
                self, "Success", f"Data exported successfully to {file_path}"
            )

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export data: {str(e)}")
