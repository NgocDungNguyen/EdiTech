import sqlite3
import os
import sys
import traceback
import logging
import json
from pathlib import Path
from app.utils.config import DATABASE_PATH
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
        
        except sqlite3.Error as e:
            # Comprehensive error logging
            logging.error(f"Database connection error: {e}")
            logging.error(traceback.format_exc())
            raise

    def create_tables(self):
        """
        Create necessary tables for the application with comprehensive logging.
        """
        try:
            cursor = self.connection.cursor()
            
            # Students table with enhanced details
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT UNIQUE,
                phone TEXT,
                date_of_birth DATE,
                gender TEXT,
                face_encoding BLOB,
                face_image_path TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # Classes table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS classes (
                class_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                instructor TEXT NOT NULL,
                class_type TEXT NOT NULL,
                description TEXT,
                semester TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # Class Enrollments
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS class_enrollments (
                enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id TEXT,
                student_id TEXT,
                status TEXT DEFAULT 'Active',
                enrolled_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(class_id) REFERENCES classes(class_id),
                FOREIGN KEY(student_id) REFERENCES students(student_id),
                UNIQUE(class_id, student_id)
            )
            """)
            
            # Attendance table with detailed tracking
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                class_id TEXT NOT NULL,
                check_in_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                check_out_time DATETIME,
                status TEXT CHECK(status IN ('Present', 'Absent', 'Late', 'Excused')),
                face_match_confidence REAL,
                location TEXT,
                notes TEXT,
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                FOREIGN KEY (class_id) REFERENCES classes(class_id)
            )
            """)
            
            # Behavior records table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS behavior_records (
                record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id TEXT,
                student_id TEXT,
                behavior_type TEXT,
                behavior_value TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(class_id) REFERENCES classes(class_id),
                FOREIGN KEY(student_id) REFERENCES students(student_id)
            )
            """)
            
            # Training data table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS training_data (
                data_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                label TEXT,
                image_path TEXT,
                points TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            self.connection.commit()
            logging.info("Tables created/updated successfully")
        
        except sqlite3.Error as e:
            logging.error(f"Error creating tables: {e}")
            logging.error(traceback.format_exc())
            self.connection.rollback()
            raise
        
        finally:
            # Verify table existence
            try:
                cursor = self.connection.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()
                logging.info(f"Existing tables: {[table[0] for table in tables]}")
            except Exception as log_error:
                logging.error(f"Error logging tables: {log_error}")

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
            # Validate required fields with more flexible handling
            first_name = student_data.get('first_name', '').strip()
            last_name = student_data.get('last_name', '').strip()
            name = student_data.get('name', '').strip()
            
            # If first_name and last_name are empty, try to split the name
            if not first_name and not last_name and name:
                name_parts = name.split(' ', 1)
                first_name = name_parts[0]
                last_name = name_parts[1] if len(name_parts) > 1 else first_name
            
            # Validate first name
            if not first_name:
                raise ValueError("First name is required")
            
            # If last name is still empty, use first name as both first and last name
            if not last_name:
                last_name = first_name
            
            # Update student data with processed names
            student_data['first_name'] = first_name
            student_data['last_name'] = last_name
            
            # Generate unique student ID if not provided
            student_id = student_data.get('student_id')
            if not student_id:
                student_id = f"STU-{str(uuid.uuid4())[:8].upper()}"
            
            # Prepare student data
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT INTO students (
                    student_id, 
                    first_name, 
                    last_name, 
                    email, 
                    phone, 
                    created_at, 
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (
                student_id,
                first_name,
                last_name,
                student_data.get('email'),
                student_data.get('phone')
            ))
            
            # Commit transaction
            self.connection.commit()
            
            return student_id
        
        except sqlite3.Error as e:
            # Rollback transaction
            self.connection.rollback()
            
            # Log detailed error
            logging.error(f"Error adding student: {e}")
            raise ValueError(f"Could not add student: {e}")
        except Exception as e:
            # Rollback transaction
            self.connection.rollback()
            
            # Log detailed error
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

            # Detailed logging of input parameters
            logging.info("=" * 50)
            logging.info("GET STUDENTS METHOD DIAGNOSTIC")
            logging.info(f"Query parameter type: {type(query)}")
            logging.info(f"Query parameter value: {repr(query)}")
            logging.info(f"Filters parameter type: {type(filters)}")
            logging.info(f"Filters parameter value: {repr(filters)}")

            # Validate input types
            if query is not None and not isinstance(query, str):
                raise TypeError(f"Query must be a string, got {type(query)}")
            
            if filters is not None and not isinstance(filters, dict):
                raise TypeError(f"Filters must be a dictionary, got {type(filters)}")

            # Base query with explicit column selection
            base_query = """
                SELECT 
                    student_id, 
                    first_name, 
                    last_name, 
                    email, 
                    phone, 
                    created_at, 
                    updated_at 
                FROM students
            """
            
            # Conditions and params for dynamic filtering
            conditions = []
            params = []

            # Handle query parameter
            if query:
                # Use exact match on multiple fields
                conditions.append("""
                    (student_id = ? OR 
                     first_name = ? OR 
                     last_name = ? OR 
                     email = ? OR 
                     phone = ?)
                """)
                search_param = f"%{query}%"
                params.extend([search_param, search_param, search_param, search_param, search_param])

            # Handle filters
            if filters:
                # Email filter
                if 'email' in filters and isinstance(filters['email'], str):
                    conditions.append("email = ?")
                    params.append(filters['email'])
                
                # Phone filter
                if 'phone' in filters and isinstance(filters['phone'], str):
                    conditions.append("phone = ?")
                    params.append(filters['phone'])
                
                # First name filter
                if 'first_name' in filters and isinstance(filters['first_name'], str):
                    conditions.append("first_name = ?")
                    params.append(filters['first_name'])
                
                # Last name filter
                if 'last_name' in filters and isinstance(filters['last_name'], str):
                    conditions.append("last_name = ?")
                    params.append(filters['last_name'])

            # Construct final query
            if conditions:
                base_query += " WHERE " + " AND ".join(conditions)
            
            # Add ordering
            base_query += " ORDER BY created_at DESC"

            # Log the final constructed query
            logging.info("FINAL QUERY:")
            logging.info(base_query)
            logging.info("QUERY PARAMETERS:")
            logging.info(repr(params))

            # Execute query
            cursor = self.connection.cursor()
            if params:
                cursor.execute(base_query, params)
            else:
                cursor.execute(base_query)

            # Fetch results
            students = []
            for row in cursor.fetchall():
                # Detailed row logging
                logging.info(f"RAW ROW DATA: {list(row)}")
                
                try:
                    student = {
                        'student_id': str(row[0]) if row[0] is not None else '',
                        'first_name': str(row[1]) if row[1] is not None else '',
                        'last_name': str(row[2]) if row[2] is not None else '',
                        'email': str(row[3]) if row[3] is not None else '',
                        'phone': str(row[4]) if row[4] is not None else '',
                        'created_at': str(row[5]) if row[5] is not None else '',
                        'updated_at': str(row[6]) if row[6] is not None else '',
                        'name': f"{row[1]} {row[2]}".strip()
                    }
                    students.append(student)
                except Exception as conversion_error:
                    logging.error(f"Error converting student row: {conversion_error}")
                    logging.error(f"Problematic row: {list(row)}")

            # Log final results
            logging.info("=" * 50)
            logging.info(f"Found {len(students)} students")
            
            return students

        except sqlite3.Error as e:
            # Comprehensive SQLite error logging
            logging.error("=" * 50)
            logging.error("SQLITE ERROR IN GET_STUDENTS")
            logging.error(f"Error: {e}")
            logging.error(f"Error type: {type(e)}")
            logging.error(f"Query: {base_query}")
            logging.error(f"Parameters: {params}")
            logging.error(traceback.format_exc())
            
            # Additional diagnostic information
            try:
                # Check table structure
                cursor = self.connection.cursor()
                cursor.execute("PRAGMA table_info(students)")
                table_info = cursor.fetchall()
                logging.error(f"Students table structure: {table_info}")
            except Exception as diag_error:
                logging.error(f"Error getting table info: {diag_error}")
            
            raise ValueError(f"Could not retrieve students: {e}")
        
        except Exception as e:
            # Catch-all for any other unexpected errors
            logging.error("=" * 50)
            logging.error("UNEXPECTED ERROR IN GET_STUDENTS")
            logging.error(f"Error: {e}")
            logging.error(f"Error type: {type(e)}")
            logging.error(traceback.format_exc())
            raise

    def get_student(self, student_id):
        """Get student details by ID with expanded fields."""
        cursor = self.execute("""
            SELECT * FROM students WHERE student_id = ?
        """, (student_id,))
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
                'first_name': 'first_name',
                'last_name': 'last_name',
                'email': 'email',
                'phone': 'phone'
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
                base_query += " AND (student_id LIKE ? OR first_name LIKE ? OR last_name LIKE ?)"
                search_param = f"%{query}%"
                params.extend([search_param, search_param, search_param])

            # Safely handle filters
            if filters and isinstance(filters, dict):
                # Email filter
                if 'email' in filters and isinstance(filters['email'], str):
                    base_query += " AND email LIKE ?"
                    params.append(f"%{filters['email']}%")
                
                # Phone filter
                if 'phone' in filters and isinstance(filters['phone'], str):
                    base_query += " AND phone LIKE ?"
                    params.append(f"%{filters['phone']}%")
                
                # First name filter
                if 'first_name' in filters and isinstance(filters['first_name'], str):
                    base_query += " AND first_name LIKE ?"
                    params.append(f"%{filters['first_name']}%")
                
                # Last name filter
                if 'last_name' in filters and isinstance(filters['last_name'], str):
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
                        'student_id': str(row[0]) if row[0] is not None else '',
                        'first_name': str(row[1]) if row[1] is not None else '',
                        'last_name': str(row[2]) if row[2] is not None else '',
                        'email': str(row[3]) if row[3] is not None else '',
                        'phone': str(row[4]) if row[4] is not None else '',
                        'created_at': str(row[5]) if row[5] is not None else '',
                        'updated_at': str(row[6]) if row[6] is not None else ''
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
    def add_class(self, name, subject, teacher, room=None, max_capacity=30, class_type=None, description=None, schedules=None):
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
            cursor.execute("""
                INSERT INTO classes (
                    class_id, name, subject, teacher, 
                    room, max_capacity, class_type, description,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (
                class_id, name, subject, teacher, 
                room, max_capacity, class_type, description
            ))
            
            # Insert schedules if provided
            if schedules:
                for schedule in schedules:
                    cursor.execute("""
                        INSERT INTO class_schedules (
                            class_id, days, start_time, end_time
                        ) VALUES (?, ?, ?, ?)
                    """, (
                        class_id, 
                        schedule.get('days', ''), 
                        schedule.get('start_time', ''), 
                        schedule.get('end_time', '')
                    ))
            
            # Commit the transaction
            self.connection.commit()
            
            return class_id
        
        except sqlite3.Error as e:
            # Rollback the transaction in case of error
            self.connection.rollback()
            logging.error(f"Database error adding class: {e}")
            raise

    def enroll_student(self, class_id, student_id, status='Active'):
        """Enroll a student in a class."""
        try:
            # Check class capacity
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT COUNT(*) as current_enrollment, max_capacity 
                FROM class_enrollments 
                JOIN classes ON class_enrollments.class_id = classes.class_id 
                WHERE classes.class_id = ?
            """, (class_id,))
            enrollment_info = cursor.fetchone()
            
            if enrollment_info[0] >= enrollment_info[1]:
                raise ValueError("Class is already at maximum capacity")

            cursor.execute("""
                INSERT INTO class_enrollments (class_id, student_id, status) 
                VALUES (?, ?, ?)
            """, (class_id, student_id, status))
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
            cursor.execute("""
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
            """, (class_id,))
            
            # Fetch the class result
            class_result = cursor.fetchone()
            
            if not class_result:
                logging.warning(f"No class found with ID: {class_id}")
                return None
            
            # Fetch schedules for this class
            cursor.execute("""
                SELECT 
                    days, 
                    start_time, 
                    end_time 
                FROM 
                    class_schedules 
                WHERE 
                    class_id = ?
            """, (class_id,))
            
            # Fetch schedules
            schedule_results = cursor.fetchall()
            
            # Prepare schedules list
            schedules = [
                {
                    'days': schedule[0],
                    'start_time': schedule[1],
                    'end_time': schedule[2]
                } for schedule in schedule_results
            ]
            
            # Convert result to dictionary
            class_details = {
                'class_id': class_result[0],
                'name': class_result[1],
                'subject': class_result[2],
                'teacher': class_result[3],
                'room': class_result[4],
                'max_capacity': class_result[5],
                'class_type': class_result[6],
                'description': class_result[7],
                'schedules': schedules
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
            cursor.execute("""
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
            """, (
                class_data['name'], 
                class_data['subject'], 
                class_data['teacher'], 
                class_data['room'], 
                class_data['max_capacity'], 
                class_data['class_type'], 
                class_data['description'],
                class_data['class_id']
            ))
            
            # Remove existing schedules for this class
            cursor.execute("DELETE FROM class_schedules WHERE class_id = ?", (class_data['class_id'],))
            
            # Insert new schedules
            for schedule in class_data.get('schedules', []):
                cursor.execute("""
                    INSERT INTO class_schedules (
                        class_id, days, start_time, end_time
                    ) VALUES (?, ?, ?, ?)
                """, (
                    class_data['class_id'], 
                    schedule.get('days', ''), 
                    schedule.get('start_time', ''), 
                    schedule.get('end_time', '')
                ))
            
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
                base_query += " AND (c.name LIKE ? OR c.subject LIKE ? OR c.teacher LIKE ?)"
                search_param = f"%{query}%"
                params.extend([search_param, search_param, search_param])
            
            if filters:
                if 'subject' in filters:
                    base_query += " AND c.subject = ?"
                    params.append(filters['subject'])
                
                if 'teacher' in filters:
                    base_query += " AND c.teacher = ?"
                    params.append(filters['teacher'])
                
                if 'semester' in filters:
                    base_query += " AND c.semester = ?"
                    params.append(filters['semester'])
                
                if 'min_enrollment' in filters:
                    base_query += " GROUP BY c.class_id HAVING current_enrollment >= ?"
                    params.append(filters['min_enrollment'])
            
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
            cursor.execute("""
                INSERT INTO class_schedules (
                    class_id, days, start_time, end_time
                ) VALUES (?, ?, ?, ?)
            """, (class_id, days, start_time, end_time))
            
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
            cursor.execute("""
                SELECT class_id, name, teacher, class_type, description, semester
                FROM classes
                ORDER BY name
            """)
            return cursor.fetchall()
        except sqlite3.Error as e:
            logging.error(f"Error getting classes: {e}")
            return []

    # Attendance operations
    def mark_attendance(self, class_id, student_id, status, check_in_time):
        """Mark student attendance."""
        self.execute("""
            INSERT INTO attendance (class_id, student_id, status, check_in_time)
            VALUES (?, ?, ?, ?)
        """, (class_id, student_id, status, check_in_time))
        self.commit()

    def get_student_attendance(self, student_id, class_id=None):
        """Get attendance records for a student."""
        if class_id:
            cursor = self.execute("""
                SELECT * FROM attendance 
                WHERE student_id = ? AND class_id = ?
                ORDER BY check_in_time DESC
            """, (student_id, class_id))
        else:
            cursor = self.execute("""
                SELECT * FROM attendance 
                WHERE student_id = ?
                ORDER BY check_in_time DESC
            """, (student_id,))
        return cursor.fetchall()

    # Behavior operations
    def record_behavior(self, class_id, student_id, behavior_type, behavior_value):
        """Record student behavior."""
        self.execute("""
            INSERT INTO behavior_records (class_id, student_id, behavior_type, behavior_value)
            VALUES (?, ?, ?, ?)
        """, (class_id, student_id, behavior_type, behavior_value))
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
        self.execute("""
            INSERT INTO training_data (behavior_type, label, image_path, points)
            VALUES (?, ?, ?, ?)
        """, (behavior_type, label, image_path, json.dumps(points) if points else None))
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
                logging.info(f"Column {col[0]}: Name={col[1]}, Type={col[2]}, Nullable={col[3]}, Default={col[4]}, Primary Key={col[5]}")
            
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

    def print_table_schema(self, table_name='students'):
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
        try:
            db = Database()
            classes = db.get_classes()
            if not classes:
                print("No classes found in database")
            else:
                print(f"Found {len(classes)} classes")
        except Exception as e:
            print(f"Database connection error: {e}")

    def migrate_schema(self):
        """Migrate database schema to latest version"""
        try:
            cursor = self.connection.cursor()
            
            # Check if subject column exists
            cursor.execute("PRAGMA table_info(classes)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'subject' in columns:
                # Migrate from old schema
                cursor.execute("""
                    ALTER TABLE classes RENAME COLUMN subject TO class_type
                """)
                
            # Ensure all required columns exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS classes (
                    class_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    instructor TEXT NOT NULL,
                    class_type TEXT NOT NULL,
                    description TEXT,
                    semester TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            self.connection.commit()
        except sqlite3.Error as e:
            logging.error(f"Schema migration failed: {e}")
            raise
