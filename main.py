import os
import sys
import traceback
import logging

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QVBoxLayout, QWidget, QMessageBox
)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt

# Import all tab views
from app.views.main_window import MainWindow
from app.views.tabs.dashboard_tab import DashboardTab
from app.views.tabs.registration_tab import RegistrationTab
from app.views.tabs.class_tab import ClassManagementTab
from app.views.tabs.attendance_tab import AttendanceTab
from app.views.tabs.behavior_tab import BehaviorTab
from app.views.tabs.training_tab import TrainingTab
from app.views.tabs.analytics_tab import AnalyticsTab
from app.views.tabs.system_tab import SystemTab

from app.models.database import Database
from app.utils.config import BASE_DIR, ICONS_DIR, load_config

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('application.log', mode='w'),
        logging.StreamHandler()
    ]
)

class MainApplication(MainWindow):
    def __init__(self):
        try:
            super().__init__()
            
            # Initialize database with detailed logging
            logging.info("Initializing database...")
            self.db = Database()
            logging.info("Creating database tables...")
            self.db.create_tables()
            
            # Debug and verify database
            self.db.debug_student_table()
            self.db.verify_database_schema()
            
            # Print detailed table schema for students and other key tables
            self.db.print_table_schema('students')
            self.db.print_table_schema('classes')
            
            logging.info("Database initialization complete")

            # Load configuration
            config = load_config()
            
            # Set application icon
            app_icon = QIcon(str(ICONS_DIR / "app_icon.png"))
            self.setWindowIcon(app_icon)

            # Remove existing tabs
            while self.tabs.count() > 0:
                self.tabs.removeTab(0)

            # Create tabs
            tabs = [
                ("Dashboard", DashboardTab()),
                ("Student Registration", RegistrationTab()),
                ("Class Management", ClassManagementTab()),
                ("Attendance", AttendanceTab()),
                ("Behavior Monitor", BehaviorTab()),
                ("Training", TrainingTab()),
                ("Analytics", AnalyticsTab()),
                ("System", SystemTab())
            ]
            
            # Add tabs to tab widget
            for title, tab in tabs:
                self.tabs.addTab(tab, title)
            
            # Set application-wide style
            app = QApplication.instance()
            app.setStyle('Fusion')
            
            # Set application-wide stylesheet
            app.setStyleSheet("""
                QWidget {
                    font-family: 'Arial', sans-serif;
                    font-size: 14px;
                }
                QLabel {
                    color: #202124;
                }
                QPushButton {
                    background-color: #1a73e8;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                }
                QPushButton:hover {
                    background-color: #185abc;
                }
                QTabWidget::pane {
                    border: 1px solid #ddd;
                    background: white;
                }
                QTabBar::tab {
                    background: #f1f3f4;
                    color: #5f6368;
                    padding: 10px 20px;
                    border: 1px solid #ddd;
                    border-bottom: none;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                }
                QTabBar::tab:selected {
                    background: #1a73e8;
                    color: white;
                }
            """)
            
            self.setWindowTitle("Edison Vision - Class Management System")
            self.resize(1200, 800)

        except Exception as e:
            # Comprehensive error handling
            logging.error(f"Initialization error: {e}")
            logging.error(traceback.format_exc())
            
            # Show detailed error dialog
            error_dialog = QMessageBox()
            error_dialog.setIcon(QMessageBox.Icon.Critical)
            error_dialog.setWindowTitle("Initialization Error")
            error_dialog.setText("Failed to start application")
            error_dialog.setDetailedText(str(traceback.format_exc()))
            error_dialog.exec()
            
            raise

def main():
    try:
        logging.info("Starting Edison Vision application...")
        app = QApplication(sys.argv)
        
        # Create and show main window
        window = MainApplication()
        window.show()
        
        # Start application event loop
        sys.exit(app.exec())
        
    except Exception as e:
        logging.error(f"Application Error: {str(e)}")
        logging.error(traceback.format_exc())
        QMessageBox.critical(None, "Critical Error", 
            f"Unhandled application error: {str(e)}\n\n"
            "Please check the log file for more details.")
        sys.exit(1)

if __name__ == "__main__":
    main()
