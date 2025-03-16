from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon


class DashboardTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        """Initialize the dashboard UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # Welcome section
        welcome_frame = QFrame()
        welcome_frame.setObjectName("welcomeFrame")
        welcome_layout = QVBoxLayout(welcome_frame)

        title = QLabel("Welcome to Edison Class Vision")
        title.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        welcome_layout.addWidget(title)

        subtitle = QLabel("Intelligent Classroom Management System")
        subtitle.setFont(QFont("Arial", 14))
        welcome_layout.addWidget(subtitle)

        layout.addWidget(welcome_frame)

        # Quick Actions section
        actions_frame = QFrame()
        actions_frame.setObjectName("actionsFrame")
        actions_layout = QHBoxLayout(actions_frame)

        # Create quick action buttons
        quick_actions = [
            ("Register Student", "Add new students to the system"),
            ("Manage Classes", "Create and modify class schedules"),
            ("Take Attendance", "Start attendance tracking"),
            ("Monitor Behavior", "Begin classroom monitoring"),
        ]

        for title, description in quick_actions:
            action_widget = self.create_action_button(title, description)
            actions_layout.addWidget(action_widget)

        layout.addWidget(actions_frame)

        # System Status section
        status_frame = QFrame()
        status_frame.setObjectName("statusFrame")
        status_layout = QVBoxLayout(status_frame)

        status_title = QLabel("System Status")
        status_title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        status_layout.addWidget(status_title)

        # Add status indicators
        status_grid = QHBoxLayout()
        status_items = [
            ("Database", "Connected"),
            ("Camera", "Ready"),
            ("AI Models", "Loaded"),
            ("Storage", "Available"),
        ]

        for title, status in status_items:
            status_widget = self.create_status_indicator(title, status)
            status_grid.addWidget(status_widget)

        status_layout.addLayout(status_grid)
        layout.addWidget(status_frame)

        # Instructions section
        instructions_frame = QFrame()
        instructions_frame.setObjectName("instructionsFrame")
        instructions_layout = QVBoxLayout(instructions_frame)

        instructions_title = QLabel("Quick Start Guide")
        instructions_title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        instructions_layout.addWidget(instructions_title)

        instructions_text = """
        1. Register Students: Add new students with facial recognition
        2. Create Classes: Set up class schedules and assign students
        3. Take Attendance: Use facial recognition for automatic check-in
        4. Monitor Behavior: Track student engagement and activities
        5. View Analytics: Generate reports and analyze classroom data
        """

        instructions = QLabel(instructions_text)
        instructions.setFont(QFont("Arial", 12))
        instructions_layout.addWidget(instructions)

        layout.addWidget(instructions_frame)

        # Set styles
        self.setStyleSheet(
            """
            QFrame {
                background-color: white;
                border-radius: 10px;
                padding: 15px;
            }
            #welcomeFrame {
                background-color: #1a73e8;
                color: white;
            }
            #actionsFrame {
                background-color: #f8f9fa;
            }
            QPushButton {
                background-color: #fff;
                border: 2px solid #1a73e8;
                border-radius: 5px;
                padding: 10px;
                color: #1a73e8;
            }
            QPushButton:hover {
                background-color: #1a73e8;
                color: white;
            }
            .status-indicator {
                padding: 10px;
                border-radius: 5px;
                background-color: #e8f0fe;
            }
        """
        )

    def create_action_button(self, title, description):
        """Create a quick action button widget."""
        widget = QFrame()
        layout = QVBoxLayout(widget)

        button = QPushButton(title)
        button.setFont(QFont("Arial", 12))
        button.setMinimumSize(150, 40)

        desc = QLabel(description)
        desc.setFont(QFont("Arial", 10))
        desc.setWordWrap(True)

        layout.addWidget(button)
        layout.addWidget(desc)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        return widget

    def create_status_indicator(self, title, status):
        """Create a status indicator widget."""
        widget = QFrame()
        widget.setProperty("class", "status-indicator")
        layout = QVBoxLayout(widget)

        title_label = QLabel(title)
        title_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))

        status_label = QLabel(status)
        status_label.setFont(QFont("Arial", 10))

        layout.addWidget(title_label)
        layout.addWidget(status_label)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        return widget
