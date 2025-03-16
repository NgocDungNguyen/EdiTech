# Edison Class Vision Management System

A comprehensive classroom management system with facial recognition, behavior monitoring, and attendance tracking capabilities.

## Features
- Student Registration with Multi-Stage Facial Capture
- Class Management and Student Assignment
- Automated Attendance Tracking
- Real-time Behavior and Emotion Monitoring
- Custom Behavior Model Training Interface
- Analytics Dashboard
- Data Backup and System Utilities

## Setup Instructions
1. Install Python 3.8 or higher
2. Install required dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Set up MySQL database using the provided schema
4. Configure database credentials in config.py
5. Run the application:
   ```
   python main.py
   ```

## Project Structure
```
edison_vision/
├── app/
│   ├── controllers/      # Business logic
│   ├── models/          # Database models
│   ├── views/           # UI files
│   └── utils/           # Helper functions
├── data/
│   ├── models/          # Trained models
│   └── backups/         # System backups
├── docs/               # Documentation
├── resources/
│   ├── icons/          # UI icons
│   └── styles/         # CSS/QSS styles
└── tests/             # Unit tests
```
