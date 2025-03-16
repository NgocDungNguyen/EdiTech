import sqlite3
import os
import sys
import traceback
import logging
import json
from pathlib import Path
from app.utils.config import DATABASE_PATH, DATA_DIR  # Add DATA_DIR import
import uuid


class Database:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance.connection = None
        return cls._instance

    def __init__(self, db_path=None):
        """
        Initialize database connection with enhanced logging.
    
        :param db_path: Optional custom path to SQLite database
        """
        # Prevent re-initialization if already connected
        if self.connection is not None:
            return

        # Set default database path if not provided
        if db_path is None:
            # Ensure data directory exists
            data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, 'edison_vision.db')

        # Log database path for debugging
        logging.info(f"Initializing database at path: {db_path}")

        try:
            # Establish connection with additional error handling
            self.connection = sqlite3.connect(db_path)
            self.connection.row_factory = sqlite3.Row  # Use Row factory for more flexible access

            # Log successful connection
            logging.info("Database connection established successfully")

            # Create cursor for initial operations
            cursor = self.connection.cursor()

            # Verify database integrity
            cursor.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()
            logging.info(f"Database integrity check result: {integrity_result}")

            # Create tables if not exists
            self.create_tables()

            # Run database migrations to add missing columns
            self.migrate_schema()

        except sqlite3.Error as e:
            # Comprehensive error logging
            logging.error(f"Database connection error: {e}")

    def create_tables(self):
        """
        Create necessary tables for the application with comprehensive logging.
        """
        try:
            cursor = self.connection.cursor()

            # Students table
            cursor.execute(
                """
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                email TEXT NOT NULL,
                phone TEXT NOT NULL,
                date_of_birth DATE NOT NULL,
                gender TEXT NOT NULL,
                face_encoding BLOB,
                face_image_path TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
            )

            # Classes table
            cursor.execute(
                """
            CREATE TABLE IF NOT EXISTS classes (
                class_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                subject TEXT NOT NULL,
                teacher TEXT NOT NULL,
                room TEXT,
                class_type TEXT,
                description TEXT,
                max_capacity INTEGER DEFAULT 30,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
            )

            # Class Enrollments table
            cursor.execute(
                """
            CREATE TABLE IF NOT EXISTS class_enrollments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id TEXT NOT NULL,
                student_id TEXT NOT NULL,
                status TEXT DEFAULT 'Active',
                enroll_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (class_id) REFERENCES classes (class_id),
                FOREIGN KEY (student_id) REFERENCES students (student_id),
                UNIQUE(class_id, student_id)
            )
            """
            )

            # class_schedules table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS class_schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id TEXT NOT NULL,
                days TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (class_id) REFERENCES classes (class_id)
            )
            """)

            # Attendance table
            cursor.execute(
                """
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                class_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Present',
                check_in_time DATETIME NOT NULL,
                check_out_time DATETIME,
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                FOREIGN KEY (class_id) REFERENCES classes(class_id)
            )
            """
            )

            # Behavior Records table
            cursor.execute(
                """
            CREATE TABLE IF NOT EXISTS behavior_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id TEXT NOT NULL,
                student_id TEXT NOT NULL,
                behavior_type TEXT NOT NULL,
                behavior_value REAL NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                FOREIGN KEY (class_id) REFERENCES classes (class_id),
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
            """
            )

            # Training Data table
            cursor.execute(
                """
            CREATE TABLE IF NOT EXISTS training_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                behavior_type TEXT NOT NULL,
                label TEXT NOT NULL,
                image_path TEXT NOT NULL,
                points TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
            )

            # Commit transaction
            self.connection.commit()

            # Log success
            logging.info("Tables created/updated successfully")

            # Log existing tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [table[0] for table in cursor.fetchall()]
            logging.info(f"Existing tables: {tables}")

        except sqlite3.Error as e:
            logging.error(f"Error creating tables: {e}")
            self.connection.rollback()

        finally:
            if cursor:
                cursor.close()

    def close(self):
        """Close the database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None

    def execute(self, query, params=None):
        """Execute a query and return the cursor."""
        try:
            cursor = self.connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor
        except sqlite3.Error as e:
            logging.error(f"Database execution error: {e}")
            logging.error(f"Query: {query}")
            logging.error(f"Params: {params}")
            logging.error(traceback.format_exc())
            raise

    def commit(self):
        """Commit the current transaction."""
        self.connection.commit()

    def rollback(self):
        """Rollback the current transaction."""
        self.connection.rollback()

    # Student operations
    def add_student(self, student_data):
        """
        Add a new student to the database with comprehensive validation.

        :param student_data: Dictionary containing student information
        :return: Student ID of the newly added student
        """
        try:
            # Validate required fields
            student_id = student_data.get("student_id", "").strip()
            first_name = student_data.get("first_name", "").strip()
            last_name = student_data.get("last_name", "").strip()
            email = student_data.get("email", "").strip()
            phone = student_data.get("phone", "").strip()
            date_of_birth = student_data.get("date_of_birth", "").strip()
            gender = student_data.get("gender", "").strip()

            # Log all the fields for debugging
            logging.info(f"Adding student: {first_name} {last_name}")
            logging.info(f"Student data: {student_data}")

            # Check for required fields
            missing_fields = []
            if not first_name: missing_fields.append("first_name")
            if not last_name: missing_fields.append("last_name")
            if not email: missing_fields.append("email")
            if not phone: missing_fields.append("phone")
            if not date_of_birth: missing_fields.append("date_of_birth")
            if not gender: missing_fields.append("gender")

            if missing_fields:
                missing_str = ", ".join(missing_fields)
                logging.error(f"Missing required fields: {missing_str}")
                raise ValueError(f"Missing required fields: {missing_str}")

            # Generate unique student ID if not provided
            if not student_id:
                student_id = f"STU-{str(uuid.uuid4())[:8].upper()}"

            # Get face image path or set to empty
            face_image_path = student_data.get("face_image_path", "")

            # Get face encoding or set to empty bytes
            face_encoding = student_data.get("face_encoding", b'')

            # Insert into database
            cursor = self.connection.cursor()
            cursor.execute(
                """
                INSERT INTO students (
                    student_id, first_name, last_name, email, phone, 
                    date_of_birth, gender, face_encoding, face_image_path,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (
                    student_id, first_name, last_name, email, phone,
                    date_of_birth, gender, face_encoding, face_image_path
                )
            )

            # Commit transaction
            self.connection.commit()

            logging.info(f"Successfully added student {student_id}: {first_name} {last_name}")
            return student_id

        except sqlite3.Error as e:
            # Rollback and log error
            self.connection.rollback()
            logging.error(f"Database error adding student: {e}")
            raise ValueError(f"Database error: {e}")
        except Exception as e:
            logging.error(f"Error adding student: {e}")
            raise

    def get_students(self, query=None, filters=None):
        """
        Retrieve students from the database with optional filtering.

        :param query: Optional search query string
        :param filters: Optional dictionary of filter conditions
        :return: List of student dictionaries
        """
        try:
            # Validate connection
            if not self.connection:
                raise ValueError("Database connection is not established")

            # Base query with explicit column selection
            base_query = """
                SELECT 
                    student_id, 
                    first_name, 
                    last_name, 
                    email, 
                    phone,
                    date_of_birth,
                    gender,
                    face_encoding,
                    face_image_path,
                    created_at, 
                    updated_at 
                FROM students
            """

            # Add a simple WHERE clause if provided
            where_conditions = []
            params = []

            if query and isinstance(query, str):
                where_conditions.append("(student_id LIKE ? OR first_name LIKE ? OR last_name LIKE ?)")
                search_param = f"%{query}%"
                params.extend([search_param, search_param, search_param])

            # Add filtering logic
            if where_conditions:
                base_query += " WHERE " + " AND ".join(where_conditions)

            # Add ordering
            base_query += " ORDER BY created_at DESC"

            # Execute query
            cursor = self.connection.cursor()
            cursor.execute(base_query, params)

            # Fetch results and convert to dictionaries
            students = []
            for row in cursor.fetchall():
                try:
                    # Always convert to dictionary regardless of row type
                    student = {}

                    if isinstance(row, sqlite3.Row):
                        # Get column names from sqlite3.Row
                        for key in row.keys():
                            student[key] = row[key]
                    else:
                        # For tuple results, map by position
                        student = {
                            'student_id': row[0],
                            'first_name': row[1],
                            'last_name': row[2],
                            'email': row[3],
                            'phone': row[4],
                            'date_of_birth': row[5] if len(row) > 5 else '',
                            'gender': row[6] if len(row) > 6 else '',
                            'face_image_path': row[8] if len(row) > 8 else ''
                        }

                    students.append(student)
                except Exception as row_error:
                    logging.error(f"Error processing student row: {row_error}")
                    logging.error(f"Row data: {row}")
                    continue

            logging.info(f"Found {len(students)} students")
            return students

        except sqlite3.Error as e:
            logging.error(f"Database error in get_students: {e}")
            return []
        except Exception as e:
            logging.error(f"Unexpected error in get_students: {e}")
            return []

    def get_student(self, student_id):
        """Get student details by ID with expanded fields."""
        cursor = self.execute(
            """
            SELECT * FROM students WHERE student_id = ?
        """,
            (student_id,),
        )
        return cursor.fetchone()

    def update_student(self, student_id, **kwargs):
        """
        Update student information.

        :param student_id: Unique identifier of the student
        :param kwargs: Keyword arguments for fields to update
        """
        try:
            cursor = self.connection.cursor()

            # Prepare update query
            updates = []
            params = []

            # Map input keys to database column names
            column_map = {
                "first_name": "first_name",
                "last_name": "last_name",
                "email": "email",
                "phone": "phone",
            }

            # Build update query dynamically
            for key, value in kwargs.items():
                if key in column_map and value is not None:
                    updates.append(f"{column_map[key]} = ?")
                    params.append(value)

            # Add student_id to params
            params.append(student_id)

            # Construct full query
            if updates:
                query = f"""
                    UPDATE students 
                    SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP
                    WHERE student_id = ?
                """

                # Execute update
                cursor.execute(query, params)
                self.connection.commit()

                return cursor.rowcount > 0

            return False

        except sqlite3.Error as e:
            self.connection.rollback()
            logging.error(f"Error updating student {student_id}: {e}")
            raise ValueError(f"Could not update student: {e}")

    def delete_student(self, student_id):
        """Delete a student from the database."""
        try:
            cursor = self.connection.cursor()
            cursor.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
            self.connection.commit()
            return cursor.rowcount > 0
        except Exception as e:
            self.connection.rollback()
            logging.error(f"Error deleting student: {e}")
            logging.error(traceback.format_exc())
            return False

    def search_students(self, query=None, filters=None):
        """
        Search and filter students with flexible and safe search options.

        :param query: Optional search query string
        :param filters: Optional dictionary of filter conditions
        :return: List of matching students
        """
        try:
            # Base query with safe default
            base_query = "SELECT * FROM students WHERE 1=1"
            params = []

            # Safely handle query parameter
            if query and isinstance(query, str):
                # Use parameterized query to prevent SQL injection
                base_query += (
                    " AND (student_id LIKE ? OR first_name LIKE ? OR last_name LIKE ?)"
                )
                search_param = f"%{query}%"
                params.extend([search_param, search_param, search_param])

            # Safely handle filters
            if filters and isinstance(filters, dict):
                # Email filter
                if "email" in filters and isinstance(filters["email"], str):
                    base_query += " AND email LIKE ?"
                    params.append(f"%{filters['email']}%")

                # Phone filter
                if "phone" in filters and isinstance(filters["phone"], str):
                    base_query += " AND phone LIKE ?"
                    params.append(f"%{filters['phone']}%")

                # First name filter
                if "first_name" in filters and isinstance(filters["first_name"], str):
                    base_query += " AND first_name LIKE ?"
                    params.append(f"%{filters['first_name']}%")

                # Last name filter
                if "last_name" in filters and isinstance(filters["last_name"], str):
                    base_query += " AND last_name LIKE ?"
                    params.append(f"%{filters['last_name']}%")

            # Add ordering
            base_query += " ORDER BY created_at DESC"

            # Log the final query for debugging
            logging.info(f"Executing student search query: {base_query}")
            logging.info(f"Query parameters: {params}")

            # Execute query safely
            cursor = self.connection.cursor()
            if params:
                cursor.execute(base_query, params)
            else:
                cursor.execute(base_query)

            # Fetch and process results
            students = []
            for row in cursor.fetchall():
                # Safely convert row to dictionary
                try:
                    student = {
                        "student_id": str(row[0]) if row[0] is not None else "",
                        "first_name": str(row[1]) if row[1] is not None else "",
                        "last_name": str(row[2]) if row[2] is not None else "",
                        "email": str(row[3]) if row[3] is not None else "",
                        "phone": str(row[4]) if row[4] is not None else "",
                        "created_at": str(row[5]) if row[5] is not None else "",
                        "updated_at": str(row[6]) if row[6] is not None else "",
                    }
                    students.append(student)
                except Exception as conversion_error:
                    logging.error(f"Error converting student row: {conversion_error}")
                    logging.error(f"Problematic row: {row}")

            # Log results
            logging.info(f"Found {len(students)} students")

            return students

        except sqlite3.Error as e:
            # Comprehensive error logging
            logging.error(f"Database search error: {e}")
            logging.error(f"Query: {base_query}")
            logging.error(f"Params: {params}")
            logging.error(traceback.format_exc())
            raise ValueError(f"Could not search students: {e}")
        except Exception as e:
            # Catch-all for any other unexpected errors
            logging.error(f"Unexpected error in student search: {e}")
            logging.error(traceback.format_exc())
            raise

    # Class operations
    def add_class(
        self,
        name,
        subject,
        teacher,
        room=None,
        max_capacity=30,
        class_type=None,
        description=None,
        schedules=None,
    ):
        """
        Add a new class to the database.

        :param name: Name of the class
        :param subject: Subject of the class
        :param teacher: Teacher's name
        :param room: Room number (optional)
        :param max_capacity: Maximum number of students (default 30)
        :param class_type: Type of class (optional)
        :param description: Class description (optional)
        :param schedules: List of schedules (optional)
        :return: Class ID of the newly created class
        """
        try:
            # Start a transaction
            self.connection.execute("BEGIN TRANSACTION")
            cursor = self.connection.cursor()

            # Generate unique class ID
            class_id = f"CLASS-{str(uuid.uuid4())[:8].upper()}"

            # Insert class information
            cursor.execute(
                """
                INSERT INTO classes (
                    class_id, name, subject, teacher, 
                    room, max_capacity, class_type, description,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
                (
                    class_id,
                    name,
                    subject,
                    teacher,
                    room,
                    max_capacity,
                    class_type,
                    description,
                ),
            )

            # Insert schedules if provided
            if schedules:
                for schedule in schedules:
                    cursor.execute(
                        """
                        INSERT INTO class_schedules (
                            class_id, days, start_time, end_time
                        ) VALUES (?, ?, ?, ?)
                    """,
                        (
                            class_id,
                            schedule.get("days", ""),
                            schedule.get("start_time", ""),
                            schedule.get("end_time", ""),
                        ),
                    )

            # Commit the transaction
            self.connection.commit()

            return class_id

        except sqlite3.Error as e:
            # Rollback the transaction in case of error
            self.connection.rollback()
            logging.error(f"Database error adding class: {e}")
            raise

    def enroll_student(self, class_id, student_id, status="Active"):
        """Enroll a student in a class."""
        try:
            # Check class capacity
            cursor = self.connection.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) as current_enrollment, max_capacity 
                FROM class_enrollments 
                JOIN classes ON class_enrollments.class_id = classes.class_id 
                WHERE classes.class_id = ?
            """,
                (class_id,),
            )
            enrollment_info = cursor.fetchone()

            if enrollment_info[0] >= enrollment_info[1]:
                raise ValueError("Class is already at maximum capacity")

            cursor.execute(
                """
                INSERT INTO class_enrollments (class_id, student_id, status) 
                VALUES (?, ?, ?)
            """,
                (class_id, student_id, status),
            )
            self.connection.commit()
            return True
        except sqlite3.IntegrityError:
            logging.error(f"Student {student_id} already enrolled in class {class_id}")
            return False
        except Exception as e:
            logging.error(f"Enrollment error: {e}")
            logging.error(traceback.format_exc())
            self.connection.rollback()
            return False

    def get_class_details(self, class_id):
        """
        Retrieve detailed information about a specific class.

        :param class_id: Unique identifier for the class
        :return: Dictionary containing class details
        """
        try:
            cursor = self.connection.cursor()

            # Fetch class details
            cursor.execute(
                """
                SELECT 
                    class_id, 
                    name, 
                    subject, 
                    teacher, 
                    room, 
                    max_capacity,
                    class_type,
                    description
                FROM 
                    classes 
                WHERE 
                    class_id = ?
            """,
                (class_id,),
            )

            # Fetch the class result
            class_result = cursor.fetchone()

            if not class_result:
                logging.warning(f"No class found with ID: {class_id}")
                return None

            # Fetch schedules for this class
            cursor.execute(
                """
                SELECT 
                    days, 
                    start_time, 
                    end_time 
                FROM 
                    class_schedules 
                WHERE 
                    class_id = ?
            """,
                (class_id,),
            )

            # Fetch schedules
            schedule_results = cursor.fetchall()

            # Prepare schedules list
            schedules = [
                {
                    "days": schedule[0],
                    "start_time": schedule[1],
                    "end_time": schedule[2],
                }
                for schedule in schedule_results
            ]

            # Convert result to dictionary
            class_details = {
                "class_id": class_result[0],
                "name": class_result[1],
                "subject": class_result[2],
                "teacher": class_result[3],
                "room": class_result[4],
                "max_capacity": class_result[5],
                "class_type": class_result[6],
                "description": class_result[7],
                "schedules": schedules,
            }

            return class_details

        except sqlite3.Error as e:
            logging.error(f"Database error in get_class_details: {e}")
            raise

    def update_class(self, class_data):
        """
        Update an existing class in the database.

        :param class_data: Dictionary containing class information
        :return: Boolean indicating success of the operation
        """
        try:
            # Start a transaction
            self.connection.execute("BEGIN TRANSACTION")
            cursor = self.connection.cursor()

            # Update class information
            cursor.execute(
                """
                UPDATE classes 
                SET 
                    name = ?, 
                    subject = ?, 
                    teacher = ?, 
                    room = ?, 
                    max_capacity = ?, 
                    class_type = ?, 
                    description = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE class_id = ?
            """,
                (
                    class_data["name"],
                    class_data["subject"],
                    class_data["teacher"],
                    class_data["room"],
                    class_data["max_capacity"],
                    class_data["class_type"],
                    class_data["description"],
                    class_data["class_id"],
                ),
            )

            # Remove existing schedules for this class
            cursor.execute(
                "DELETE FROM class_schedules WHERE class_id = ?",
                (class_data["class_id"],),
            )

            # Insert new schedules
            for schedule in class_data.get("schedules", []):
                cursor.execute(
                    """
                    INSERT INTO class_schedules (
                        class_id, days, start_time, end_time
                    ) VALUES (?, ?, ?, ?)
                """,
                    (
                        class_data["class_id"],
                        schedule.get("days", ""),
                        schedule.get("start_time", ""),
                        schedule.get("end_time", ""),
                    ),
                )

            # Commit the transaction
            self.connection.commit()

            return True

        except sqlite3.Error as e:
            # Rollback the transaction in case of error
            self.connection.rollback()
            logging.error(f"Database error updating class: {e}")
            return False

    def search_classes(self, query=None, filters=None):
        """
        Enhanced search_classes method with comprehensive logging.

        :param query: Search query string
        :param filters: Dictionary of filter conditions
        :return: List of classes matching search criteria
        """
        try:
            base_query = """
                SELECT 
                    c.class_id, 
                    c.name, 
                    c.subject, 
                    c.teacher, 
                    COUNT(ce.student_id) as current_enrollment 
                FROM classes c
                LEFT JOIN class_enrollments ce ON c.class_id = ce.class_id
                WHERE 1=1
            """
            params = []

            # Log search parameters
            logging.info(f"Searching classes - Query: {query}, Filters: {filters}")

            if query:
                base_query += (
                    " AND (c.name LIKE ? OR c.subject LIKE ? OR c.teacher LIKE ?)"
                )
                search_param = f"%{query}%"
                params.extend([search_param, search_param, search_param])

            if filters:
                if "subject" in filters:
                    base_query += " AND c.subject = ?"
                    params.append(filters["subject"])

                if "teacher" in filters:
                    base_query += " AND c.teacher = ?"
                    params.append(filters["teacher"])

                if "semester" in filters:
                    base_query += " AND c.semester = ?"
                    params.append(filters["semester"])

                if "min_enrollment" in filters:
                    base_query += " GROUP BY c.class_id HAVING current_enrollment >= ?"
                    params.append(filters["min_enrollment"])

            base_query += " GROUP BY c.class_id ORDER BY c.created_at DESC"

            # Log final query and parameters
            logging.info(f"Executing query: {base_query}")
            logging.info(f"Query parameters: {params}")

            cursor = self.connection.cursor()
            cursor.execute(base_query, params)
            results = cursor.fetchall()

            # Log search results
            logging.info(f"Found {len(results)} classes")

            return results

        except sqlite3.Error as e:
            # Comprehensive error logging
            logging.error(f"Error searching classes: {e}")
            logging.error(traceback.format_exc())
            raise

    def add_class_schedule(self, class_id, days, start_time, end_time):
        """
        Add a schedule to a specific class.

        :param class_id: Unique identifier of the class
        :param days: Days of the week for the schedule
        :param start_time: Start time of the class
        :param end_time: End time of the class
        :return: ID of the inserted schedule
        :raises ValueError: If class_id is invalid or does not exist
        """
        try:
            cursor = self.connection.cursor()

            # Validate inputs
            if not class_id or not days or not start_time or not end_time:
                raise ValueError("All parameters are required")

            # Check if class exists
            cursor.execute("SELECT 1 FROM classes WHERE class_id = ?", (class_id,))
            if not cursor.fetchone():
                raise ValueError(f"Class with ID {class_id} does not exist")

            # Insert schedule
            cursor.execute(
                """
                INSERT INTO class_schedules (
                    class_id, days, start_time, end_time
                ) VALUES (?, ?, ?, ?)
            """,
                (class_id, days, start_time, end_time),
            )

            # Commit transaction
            self.connection.commit()

            return cursor.lastrowid

        except sqlite3.Error as e:
            # Rollback transaction
            self.connection.rollback()

            # Log detailed error
            logging.error(f"Error adding class schedule: {e}")
            raise ValueError(f"Could not add class schedule: {e}")

    def get_classes(self):
        """Retrieve all classes from the database"""
        try:
            cursor = self.connection.cursor()

            # Log the start of the query
            logging.info("Retrieving classes from database...")

            cursor.execute(
                """
                SELECT 
                    class_id, 
                    name, 
                    subject, 
                    teacher,
                    room,
                    class_type,
                    description,
                    max_capacity
                FROM classes
                ORDER BY name
                """
            )

            # Fetch and log the results
            classes = cursor.fetchall()

            # Debug logging
            logging.info(f"Raw classes data: {classes}")
            logging.info(f"Number of classes retrieved: {len(classes)}")

            if len(classes) > 0:
                # Log sample class data
                logging.info(f"Sample class ID: {classes[0]['class_id']}, Name: {classes[0]['name']}")

            return classes
        except sqlite3.Error as e:
            logging.error(f"Error getting classes: {e}")
            # Return empty list instead of raising error
            return []

    def get_attendance_records(self, class_id, date=None):
        """
        Get attendance records for a specific class and date.
    
        :param class_id: ID of the class
        :param date: Date string in format 'YYYY-MM-DD'
        :return: List of attendance records
        """
        try:
            cursor = self.connection.cursor()

            query = """
                SELECT 
                    a.id, 
                    a.student_id, 
                    s.first_name || ' ' || s.last_name as name,
                    a.check_in_time, 
                    a.status, 
                    a.notes
                FROM attendance a
                JOIN students s ON a.student_id = s.student_id
                WHERE a.class_id = ?
            """
            params = [class_id]

            if date:
                query += " AND date(a.check_in_time) = ?"
                params.append(date)

            query += " ORDER BY a.check_in_time DESC"

            cursor.execute(query, params)

            # Convert rows to dictionaries
            records = []
            for row in cursor.fetchall():
                record = {
                    'id': row[0],
                    'student_id': row[1], 
                    'name': row[2],
                    'check_in_time': row[3],
                    'status': row[4],
                    'notes': row[5],
                    'location': ''  # Added for compatibility with UI
                }
                records.append(record)

            return records

        except sqlite3.Error as e:
            logging.error(f"Error getting attendance records: {e}")
            return []

    # Attendance operations
    def mark_attendance(self, student_id, class_id, status="Present", check_in_time=None, notes=None):
        """
        Mark student attendance
    
        :param student_id: Student ID
        :param class_id: Class ID
        :param status: Attendance status (Present, Absent, Late, etc.)
        :param check_in_time: Check-in time (defaults to current time)
        :param notes: Additional notes
        :return: ID of the attendance record
        """
        try:
            cursor = self.connection.cursor()

            # Set default check-in time to now if not provided
            if not check_in_time:
                from datetime import datetime
                check_in_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Insert attendance record
            cursor.execute(
                """
                INSERT INTO attendance
                (student_id, class_id, status, check_in_time, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (student_id, class_id, status, check_in_time, notes)
            ) 

            # Get the ID of the inserted record
            cursor.execute("SELECT last_insert_rowid()")
            attendance_id = cursor.fetchone()[0]

            self.connection.commit()
            logging.info(f"Marked attendance for student {student_id} in class {class_id}")

            return attendance_id

        except sqlite3.Error as e:
            self.connection.rollback()
            logging.error(f"Error marking attendance: {e}")
            raise ValueError(f"Could not mark attendance: {e}")

    def get_student_attendance(self, student_id, class_id=None):
        """Get attendance records for a student."""
        if class_id:
            cursor = self.execute(
                """
                SELECT * FROM attendance 
                WHERE student_id = ? AND class_id = ?
                ORDER BY check_in_time DESC
            """,
                (student_id, class_id),
            )
        else:
            cursor = self.execute(
                """
                SELECT * FROM attendance 
                WHERE student_id = ?
                ORDER BY check_in_time DESC
            """,
                (student_id,),
            )
        return cursor.fetchall()
    
    
    def get_class_schedules(self, class_id):
        """
        Get schedules for a specific class
    
        :param class_id: ID of the class
        :return: List of schedule dictionaries
        """
        try:
            cursor = self.connection.cursor()
        
            cursor.execute(
                """
                SELECT 
                    id,
                    class_id,
                    day_of_week,
                    start_time,
                    end_time,
                    room,
                    created_at,
                    updated_at
                FROM class_schedules
                WHERE class_id = ?
                ORDER BY 
                    CASE 
                        WHEN day_of_week = 'Monday' THEN 1
                        WHEN day_of_week = 'Tuesday' THEN 2
                        WHEN day_of_week = 'Wednesday' THEN 3
                        WHEN day_of_week = 'Thursday' THEN 4
                        WHEN day_of_week = 'Friday' THEN 5
                        WHEN day_of_week = 'Saturday' THEN 6
                        WHEN day_of_week = 'Sunday' THEN 7
                    END,
                    start_time
                """,
                (class_id,)
            )
        
            schedules = []
            for row in cursor.fetchall():
                if isinstance(row, sqlite3.Row):
                    schedule = {}
                    for key in row.keys():
                        schedule[key] = row[key]
                else:
                    schedule = {
                        'id': row[0],
                        'class_id': row[1],
                        'day_of_week': row[2],
                        'start_time': row[3],
                        'end_time': row[4],
                        'room': row[5]
                    }
                schedules.append(schedule)
            
            return schedules
        
        except sqlite3.Error as e:
            logging.error(f"Error getting class schedules: {e}")
            return []

    # Behavior operations
    def record_behavior(self, class_id, student_id, behavior_type, behavior_value):
        """Record student behavior."""
        self.execute(
            """
            INSERT INTO behavior_records (class_id, student_id, behavior_type, behavior_value)
            VALUES (?, ?, ?, ?)
        """,
            (class_id, student_id, behavior_type, behavior_value),
        )
        self.commit()

    def get_student_behaviors(self, student_id, class_id=None, behavior_type=None):
        """Get behavior records for a student."""
        query = "SELECT * FROM behavior_records WHERE student_id = ?"
        params = [student_id]

        if class_id:
            query += " AND class_id = ?"
            params.append(class_id)
        if behavior_type:
            query += " AND behavior_type = ?"
            params.append(behavior_type)

        query += " ORDER BY timestamp DESC"
        cursor = self.execute(query, params)
        return cursor.fetchall()

    # Training data operations
    def add_training_data(self, behavior_type, label, image_path, points=None):
        """Add new training data."""
        self.execute(
            """
            INSERT INTO training_data (behavior_type, label, image_path, points)
            VALUES (?, ?, ?, ?)
        """,
            (behavior_type, label, image_path, json.dumps(points) if points else None),
        )
        self.commit()

    def get_training_data(self, behavior_type=None, label=None):
        """Get training data records."""
        query = "SELECT * FROM training_data"
        params = []

        if behavior_type or label:
            query += " WHERE"
            conditions = []
            if behavior_type:
                conditions.append("behavior_type = ?")
                params.append(behavior_type)
            if label:
                conditions.append("label = ?")
                params.append(label)
            query += " " + " AND ".join(conditions)

        cursor = self.execute(query, params)
        return cursor.fetchall()

    def debug_student_table(self):
        """
        Debug method to check the structure and content of the students table.
        """
        try:
            cursor = self.connection.cursor()

            # Check table info
            cursor.execute("PRAGMA table_info(students)")
            columns = cursor.fetchall()
            logging.info("Students Table Columns:")
            for col in columns:
                logging.info(f"Column {col[0]}: Name={col[1]}, Type={col[2]}")

            # Check row count
            cursor.execute("SELECT COUNT(*) FROM students")
            count = cursor.fetchone()[0]
            logging.info(f"Total number of students: {count}")

            # Fetch a few rows for inspection
            cursor.execute("SELECT * FROM students LIMIT 5")
            rows = cursor.fetchall()
            logging.info("Sample Student Rows:")
            for row in rows:
                logging.info(f"Row: {list(row)}")

        except sqlite3.Error as e:
            logging.error(f"Error debugging student table: {e}")
            logging.error(traceback.format_exc())

        except Exception as e:
            logging.error(f"Unexpected error in debug_student_table: {e}")
            logging.error(traceback.format_exc())

    def verify_database_schema(self):
        """
        Comprehensive method to verify database schema and report any inconsistencies.
        """
        try:
            cursor = self.connection.cursor()

            # Check table existence
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            logging.info("Existing tables:")
            for table in tables:
                logging.info(f"- {table[0]}")

            # Verify students table schema
            cursor.execute("PRAGMA table_info(students)")
            columns = cursor.fetchall()
            logging.info("\nStudents Table Schema:")
            for col in columns:
                logging.info(
                    f"Column {col[0]}: Name={col[1]}, Type={col[2]}, Nullable={col[3]}, Default={col[4]}, Primary Key={col[5]}"
                )

            # Check for any schema anomalies
            cursor.execute("PRAGMA foreign_key_list(students)")
            foreign_keys = cursor.fetchall()
            if foreign_keys:
                logging.info("\nForeign Keys in Students Table:")
                for fk in foreign_keys:
                    logging.info(f"- {fk}")
            else:
                logging.info("\nNo foreign keys found in Students Table")

            # Sample data check
            cursor.execute("SELECT COUNT(*) FROM students")
            count = cursor.fetchone()[0]
            logging.info(f"\nTotal number of students: {count}")

            if count > 0:
                cursor.execute("SELECT * FROM students LIMIT 5")
                sample_rows = cursor.fetchall()
                logging.info("\nSample Student Rows:")
                for row in sample_rows:
                    logging.info(f"Row: {list(row)}")

        except sqlite3.Error as e:
            logging.error(f"Error verifying database schema: {e}")
            logging.error(traceback.format_exc())

        except Exception as e:
            logging.error(f"Unexpected error in verify_database_schema: {e}")
            logging.error(traceback.format_exc())

    def print_table_schema(self, table_name="students"):
        """
        Print detailed schema information for a given table.

        :param table_name: Name of the table to inspect, defaults to 'students'
        """
        try:
            cursor = self.connection.cursor()

            # Get table info
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()

            logging.info(f"\n{'='*20} Table Schema for {table_name} {'='*20}")
            for col in columns:
                logging.info(f"Column {col[0]}: ")
                logging.info(f"  - Name: {col[1]}")
                logging.info(f"  - Type: {col[2]}")
                logging.info(f"  - Nullable: {col[3]}")
                logging.info(f"  - Default Value: {col[4]}")
                logging.info(f"  - Primary Key: {col[5]}")

            # Check for any foreign keys
            cursor.execute(f"PRAGMA foreign_key_list({table_name})")
            foreign_keys = cursor.fetchall()

            if foreign_keys:
                logging.info("\nForeign Keys:")
                for fk in foreign_keys:
                    logging.info(f"  - {fk}")
            else:
                logging.info("\nNo foreign keys found")

            # Sample data
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
            rows = cursor.fetchall()

            logging.info("\nSample Data:")
            for row in rows:
                logging.info(f"  - {list(row)}")

        except sqlite3.Error as e:
            logging.error(f"Error inspecting table schema: {e}")
            logging.error(traceback.format_exc())

    def check_database_connection(self):
        """Check database connection and report issues silently to log rather than showing message boxes"""
        try:
            # Just check connection by running a simple query
            cursor = self.connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM sqlite_master")
            cursor.fetchone()

            # Log success
            logging.info("Database connection test successful")

            # Try getting classes, but don't let errors propagate to UI
            try:
                classes = self.get_classes()
                if classes:
                    logging.info(f"Found {len(classes)} classes in database")
                else:
                    logging.info("No classes found in database (this is not an error)")
            except Exception as class_error:
                logging.error(f"Error getting classes: {class_error}")
                # Don't propagate this error

            return True

        except Exception as e:
            logging.error(f"Database connection error: {e}")
            return False

    def migrate_schema(self):
        """Migrate database schema to latest version"""
        try:
            cursor = self.connection.cursor()

            # Check if students table has NOT NULL constraints on face fields
            cursor.execute("PRAGMA table_info(students)")
            columns = {column[1]: column for column in cursor.fetchall()}

            # If face_encoding or face_image_path have NOT NULL constraint
            needs_relaxed_constraints = False
            face_fields_missing = False

            if 'face_encoding' not in columns:
                face_fields_missing = True
            elif columns['face_encoding'][3] == 1:  # 1 means NOT NULL
                needs_relaxed_constraints = True

            if 'face_image_path' not in columns:
                face_fields_missing = True
            elif columns['face_image_path'][3] == 1:
                needs_relaxed_constraints = True

            # If we need to relax constraints, we need to recreate the table
            if needs_relaxed_constraints:
                logging.info("Relaxing NOT NULL constraints on face fields in students table")

                # Create a new table without the constraints
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS students_new (
                    student_id TEXT PRIMARY KEY,
                    first_name TEXT,
                    last_name TEXT,
                    email TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    date_of_birth DATE NOT NULL,
                    gender TEXT NOT NULL,
                    face_encoding BLOB,
                    face_image_path TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """)

                # Copy data from old to new table
                cursor.execute("""
                INSERT INTO students_new 
                SELECT student_id, first_name, last_name, email, phone, date_of_birth, gender, 
                       IFNULL(face_encoding, ''), IFNULL(face_image_path, ''), created_at, updated_at 
                FROM students
                """)

                # Drop old table and rename new one
                cursor.execute("DROP TABLE students")
                cursor.execute("ALTER TABLE students_new RENAME TO students")

                logging.info("Successfully migrated students table to remove NOT NULL constraints")
            elif face_fields_missing:
                # Add missing columns to students table if needed
                if 'face_encoding' not in columns:
                    try:
                        cursor.execute("ALTER TABLE students ADD COLUMN face_encoding BLOB")
                        logging.info("Added missing column 'face_encoding' to students table")
                    except sqlite3.Error as column_error:
                        logging.warning(f"Could not add column 'face_encoding': {column_error}")

                if 'face_image_path' not in columns:
                    try:
                        cursor.execute("ALTER TABLE students ADD COLUMN face_image_path TEXT")
                        logging.info("Added missing column 'face_image_path' to students table")
                    except sqlite3.Error as column_error:
                        logging.warning(f"Could not add column 'face_image_path': {column_error}")

            # Check table structure for classes table
            cursor.execute("PRAGMA table_info(classes)")
            columns = {column[1]: column for column in cursor.fetchall()}

            # Add missing columns to classes table if needed
            missing_columns = []
            if 'subject' not in columns:
                missing_columns.append(("subject", "TEXT NOT NULL DEFAULT ''"))
            if 'teacher' not in columns:
                missing_columns.append(("teacher", "TEXT NOT NULL DEFAULT ''"))
            if 'class_type' not in columns:
                missing_columns.append(("class_type", "TEXT"))
            if 'max_capacity' not in columns:
                missing_columns.append(("max_capacity", "INTEGER DEFAULT 30"))

            # Apply class table migrations if needed
            for column_name, column_type in missing_columns:
                try:
                    cursor.execute(f"ALTER TABLE classes ADD COLUMN {column_name} {column_type}")
                    logging.info(f"Added missing column '{column_name}' to classes table")
                except sqlite3.Error as column_error:
                    logging.warning(f"Could not add column '{column_name}': {column_error}")

            # Make sure class_schedules table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='class_schedules'")
            if not cursor.fetchone():
                cursor.execute("""
                CREATE TABLE class_schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    class_id TEXT NOT NULL,
                    days TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (class_id) REFERENCES classes (class_id)
                )
                """)
                logging.info("Created missing class_schedules table")

            # Ensure default profile image exists
            default_profile_path = os.path.join(DATA_DIR, 'default_profile.png')
            if not os.path.exists(default_profile_path):
                try:
                    # Create student_captures directory
                    student_captures_dir = os.path.join(DATA_DIR, 'student_captures')
                    os.makedirs(student_captures_dir, exist_ok=True)

                    # Generate a simple default profile image if PIL is available
                    try:
                        from PIL import Image, ImageDraw

                        # Create a 100x100 white image with a gray silhouette
                        img = Image.new('RGB', (100, 100), color=(240, 240, 240))
                        d = ImageDraw.Draw(img)

                        # Draw a simple silhouette
                        d.ellipse((25, 10, 75, 60), fill=(200, 200, 200))  # Head
                        d.rectangle((35, 60, 65, 90), fill=(200, 200, 200))  # Body

                        # Save the image
                        img.save(default_profile_path)
                        logging.info(f"Created default profile image at {default_profile_path}")
                    except ImportError:
                        logging.warning("PIL not available, can't create default profile image")
                        # Create an empty file as fallback
                        with open(default_profile_path, 'wb') as f:
                            f.write(b'')
                except Exception as e:
                    logging.warning(f"Could not create default profile image: {e}")

            # Commit changes
            self.connection.commit()

            logging.info("Database schema migration completed successfully")

        except sqlite3.Error as e:
            logging.error(f"Database migration error: {e}")
            self.connection.rollback()
            raise
