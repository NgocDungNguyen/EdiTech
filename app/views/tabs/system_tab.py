from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QFileDialog, QFrame, QMessageBox,
                               QProgressBar)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
import shutil
import os
from datetime import datetime
from pathlib import Path
import json

from app.models.database import Database
from app.utils.config import DATA_DIR, BACKUPS_DIR

class BackupWorker(QThread):
    """Worker thread for handling backup operations."""
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)

    def __init__(self, backup_path):
        super().__init__()
        self.backup_path = backup_path
        self.db = Database()

    def run(self):
        """Perform the backup operation."""
        try:
            # Create backup directory if it doesn't exist
            backup_dir = Path(self.backup_path)
            backup_dir.mkdir(parents=True, exist_ok=True)

            # 1. Export database data (20%)
            self.progress.emit(0)
            self.backup_database(backup_dir)
            self.progress.emit(20)

            # 2. Backup training images (40%)
            self.backup_training_data(backup_dir)
            self.progress.emit(60)

            # 3. Backup configuration (20%)
            self.backup_config(backup_dir)
            self.progress.emit(80)

            # 4. Create backup info file (20%)
            self.create_backup_info(backup_dir)
            self.progress.emit(100)

            self.finished.emit(True, "Backup completed successfully!")

        except Exception as e:
            self.finished.emit(False, f"Backup failed: {str(e)}")

    def backup_database(self, backup_dir):
        """Export database data to JSON files."""
        cursor = self.db.connection.cursor()
        
        # Get all tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
        """)
        tables = cursor.fetchall()

        # Export each table
        for table in tables:
            table_name = table['table_name']
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            
            with open(backup_dir / f"{table_name}.json", 'w') as f:
                json.dump(rows, f, default=str, indent=4)

    def backup_training_data(self, backup_dir):
        """Backup training images and data."""
        training_dir = DATA_DIR / "training_images"
        if training_dir.exists():
            shutil.copytree(
                training_dir,
                backup_dir / "training_images",
                dirs_exist_ok=True
            )

    def backup_config(self, backup_dir):
        """Backup configuration files."""
        config_file = Path("config.json")
        if config_file.exists():
            shutil.copy2(config_file, backup_dir / "config.json")

    def create_backup_info(self, backup_dir):
        """Create a backup information file."""
        info = {
            'timestamp': datetime.now().isoformat(),
            'version': '1.0',
            'contents': {
                'database': True,
                'training_data': True,
                'config': True
            }
        }
        
        with open(backup_dir / "backup_info.json", 'w') as f:
            json.dump(info, f, indent=4)

class SystemTab(QWidget):
    def __init__(self):
        super().__init__()
        self.backup_worker = None
        self.init_ui()

    def init_ui(self):
        """Initialize the system utilities UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # Backup Section
        backup_frame = QFrame()
        backup_frame.setObjectName("backupFrame")
        backup_layout = QVBoxLayout(backup_frame)

        # Title
        title = QLabel("System Utilities")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        backup_layout.addWidget(title)

        # Backup Controls
        backup_controls = QHBoxLayout()
        
        self.backup_btn = QPushButton("Create Backup")
        self.backup_btn.clicked.connect(self.create_backup)
        backup_controls.addWidget(self.backup_btn)
        
        self.restore_btn = QPushButton("Restore Backup")
        self.restore_btn.clicked.connect(self.restore_backup)
        backup_controls.addWidget(self.restore_btn)
        
        backup_layout.addLayout(backup_controls)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        backup_layout.addWidget(self.progress_bar)

        # Status Label
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        backup_layout.addWidget(self.status_label)

        layout.addWidget(backup_frame)

        # Exit Section
        exit_frame = QFrame()
        exit_frame.setObjectName("exitFrame")
        exit_layout = QVBoxLayout(exit_frame)

        exit_label = QLabel("Application Control")
        exit_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        exit_layout.addWidget(exit_label)

        exit_btn = QPushButton("Exit Application")
        exit_btn.setObjectName("exitButton")
        exit_btn.clicked.connect(self.exit_application)
        exit_layout.addWidget(exit_btn)

        layout.addWidget(exit_frame)

        # Add stretch to push frames to top
        layout.addStretch()

        # Styling
        self.setStyleSheet("""
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
                min-width: 150px;
            }
            QPushButton:hover {
                background-color: #1557b0;
            }
            #exitButton {
                background-color: #dc3545;
            }
            #exitButton:hover {
                background-color: #c82333;
            }
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 4px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #1a73e8;
            }
        """)

    def create_backup(self):
        """Create a backup of the system data."""
        try:
            # Create backup directory name with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = BACKUPS_DIR / f"backup_{timestamp}"

            # Initialize and start backup worker
            self.backup_worker = BackupWorker(str(backup_path))
            self.backup_worker.progress.connect(self.update_progress)
            self.backup_worker.finished.connect(self.backup_finished)

            # Update UI
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.backup_btn.setEnabled(False)
            self.restore_btn.setEnabled(False)
            self.status_label.setText("Creating backup...")

            # Start backup process
            self.backup_worker.start()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create backup: {str(e)}")

    def restore_backup(self):
        """Restore system data from a backup."""
        try:
            # Let user select backup directory
            backup_dir = QFileDialog.getExistingDirectory(
                self,
                "Select Backup Directory",
                str(BACKUPS_DIR)
            )

            if not backup_dir:
                return

            # Verify backup
            info_file = Path(backup_dir) / "backup_info.json"
            if not info_file.exists():
                raise Exception("Invalid backup directory: missing backup_info.json")

            # Confirm restoration
            reply = QMessageBox.warning(
                self,
                "Confirm Restore",
                "This will overwrite current data with backup data. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                # Perform restoration
                self.status_label.setText("Restoring backup...")
                
                # 1. Restore database
                self.restore_database(backup_dir)
                
                # 2. Restore training data
                self.restore_training_data(backup_dir)
                
                # 3. Restore configuration
                self.restore_config(backup_dir)

                QMessageBox.information(
                    self,
                    "Success",
                    "Backup restored successfully! Please restart the application."
                )

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to restore backup: {str(e)}")
        finally:
            self.status_label.clear()

    def restore_database(self, backup_dir):
        """Restore database from backup."""
        db = Database()
        cursor = db.connection.cursor()

        # Get all JSON files in backup directory
        for json_file in Path(backup_dir).glob("*.json"):
            if json_file.stem == "backup_info":
                continue

            # Load backup data
            with open(json_file) as f:
                records = json.load(f)

            if records:
                # Clear existing table
                cursor.execute(f"TRUNCATE TABLE {json_file.stem}")

                # Insert backup records
                for record in records:
                    placeholders = ", ".join(["%s"] * len(record))
                    columns = ", ".join(record.keys())
                    query = f"INSERT INTO {json_file.stem} ({columns}) VALUES ({placeholders})"
                    cursor.execute(query, list(record.values()))

        db.connection.commit()

    def restore_training_data(self, backup_dir):
        """Restore training data from backup."""
        backup_training = Path(backup_dir) / "training_images"
        if backup_training.exists():
            training_dir = DATA_DIR / "training_images"
            if training_dir.exists():
                shutil.rmtree(training_dir)
            shutil.copytree(backup_training, training_dir)

    def restore_config(self, backup_dir):
        """Restore configuration from backup."""
        backup_config = Path(backup_dir) / "config.json"
        if backup_config.exists():
            shutil.copy2(backup_config, "config.json")

    def update_progress(self, value):
        """Update the progress bar value."""
        self.progress_bar.setValue(value)

    def backup_finished(self, success, message):
        """Handle backup completion."""
        self.progress_bar.setVisible(False)
        self.backup_btn.setEnabled(True)
        self.restore_btn.setEnabled(True)
        self.status_label.setText(message)

        if success:
            QMessageBox.information(self, "Success", message)
        else:
            QMessageBox.critical(self, "Error", message)

    def exit_application(self):
        """Exit the application safely."""
        reply = QMessageBox.question(
            self,
            "Confirm Exit",
            "Are you sure you want to exit the application?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Close database connection
            db = Database()
            db.close()
            
            # Exit application
            import sys
            sys.exit(0)
