from PyQt6.QtWidgets import (QMainWindow, QTabWidget, QWidget, QVBoxLayout,
                               QLabel, QPushButton, QScrollArea)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from .tabs.dashboard_tab import DashboardTab
from .tabs.registration_tab import RegistrationTab
from .tabs.class_tab import ClassManagementTab
from .tabs.attendance_tab import AttendanceTab
from .tabs.behavior_tab import BehaviorTab
from .tabs.training_tab import TrainingTab
from .tabs.analytics_tab import AnalyticsTab
from .tabs.system_tab import SystemTab

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Edison Class Vision Management System")
        self.setMinimumSize(1200, 800)
        
        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # Create tab widget
        self.tabs = QTabWidget()
        self.tabs.setFont(QFont("Arial", 10))
        
        # Add tabs
        self.tabs.addTab(DashboardTab(), "Dashboard")
        self.tabs.addTab(RegistrationTab(), "Student Registration")
        self.tabs.addTab(ClassManagementTab(), "Class Management")
        self.tabs.addTab(AttendanceTab(), "Attendance")
        self.tabs.addTab(BehaviorTab(), "Behavior Monitor")
        self.tabs.addTab(TrainingTab(), "Training")
        self.tabs.addTab(AnalyticsTab(), "Analytics")
        self.tabs.addTab(SystemTab(), "System")
        
        layout.addWidget(self.tabs)
        
        # Set window style
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QTabWidget::pane {
                border: 1px solid #cccccc;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #e1e1e1;
                padding: 8px 20px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-top: 2px solid #0078d4;
            }
            QTabBar::tab:hover {
                background-color: #f5f5f5;
            }
        """)
