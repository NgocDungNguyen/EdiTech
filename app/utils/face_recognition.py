import os
import numpy as np
import face_recognition
import cv2
import logging
import sqlite3
import base64

class FaceRecognitionManager:
    def __init__(self, db_path):
        """
        Initialize Face Recognition Manager
        
        :param db_path: Path to SQLite database
        """
        self.db_path = db_path
        self.known_face_encodings = []
        self.known_student_ids = []
        self.load_known_faces()

    def load_known_faces(self):
        """
        Load known face encodings from the database
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Fetch students with face encodings
            cursor.execute("""
                SELECT student_id, face_encoding 
                FROM students 
                WHERE face_encoding IS NOT NULL AND length(face_encoding) > 0
            """
            )

            for student_id, encoded_face in cursor.fetchall():
                try:
                    # Check if the encoding is non-empty
                    if not encoded_face:
                        continue
                
                    # Try to decode as a base64 string first
                    try:
                        face_encoding = np.frombuffer(
                            base64.b64decode(encoded_face), 
                            dtype=np.float64
                        )
                    except:
                        # If base64 decoding fails, try direct binary
                        face_encoding = np.frombuffer(encoded_face, dtype=np.float64)
                
                    if len(face_encoding) > 0:
                        self.known_face_encodings.append(face_encoding)
                        self.known_student_ids.append(student_id)
                except Exception as decode_error:
                    logging.error(f"Error decoding face encoding for student {student_id}: {decode_error}")
        
            conn.close()
            logging.info(f"Loaded {len(self.known_student_ids)} known faces")
    
        except sqlite3.Error as e:
            logging.error(f"Database error loading faces: {e}")
        except Exception as e:
            logging.error(f"Unexpected error loading faces: {e}")

    def capture_and_recognize_face(self, class_id=None):
        """
        Capture a face and recognize the student
        
        :param class_id: Optional class ID for attendance tracking
        :return: Dictionary with recognition results
        """
        try:
            # Initialize webcam
            video_capture = cv2.VideoCapture(0)

            # Check if webcam is opened successfully
            if not video_capture.isOpened():
                logging.error("Could not open webcam")
                return {"success": False, "error": "Webcam not available"}

            # Capture frame
            ret, frame = video_capture.read()
            video_capture.release()

            if not ret:
                logging.error("Failed to capture frame")
                return {"success": False, "error": "Frame capture failed"}

            # Find face locations and encodings
            face_locations = face_recognition.face_locations(frame)
            face_encodings = face_recognition.face_encodings(frame, face_locations)

            # No faces detected
            if not face_encodings:
                return {"success": False, "error": "No face detected"}

            # Compare with known faces
            results = []
            for face_encoding in face_encodings:
                # Compare with known face encodings
                matches = face_recognition.compare_faces(
                    self.known_face_encodings, 
                    face_encoding, 
                    tolerance=0.6  # Adjust tolerance as needed
                )

                # Find best match
                face_distances = face_recognition.face_distance(
                    self.known_face_encodings, 
                    face_encoding
                )
                best_match_index = np.argmin(face_distances)

                if matches[best_match_index]:
                    student_id = self.known_student_ids[best_match_index]
                    confidence = 1 - face_distances[best_match_index]

                    # Record attendance
                    self.record_attendance(
                        student_id, 
                        class_id, 
                        confidence
                    )

                    results.append({
                        "student_id": student_id,
                        "confidence": float(confidence)
                    })

            return {
                "success": True, 
                "matches": results
            }

        except Exception as e:
            logging.error(f"Face recognition error: {e}")
            return {"success": False, "error": str(e)}

    def record_attendance(self, student_id, class_id=None, confidence=None):
        """
        Record student attendance in the database
    
        :param student_id: ID of the recognized student
        :param class_id: Optional class ID
        :param confidence: Face match confidence
        """
        try:
            # Use direct connection to database to ensure compatibility
            from datetime import datetime
            check_in_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO attendance 
                (student_id, class_id, status, check_in_time, notes) 
                VALUES (?, ?, ?, ?, ?)
            """, (
                student_id, 
                class_id or 'Unknown', 
                'Present', 
                check_in_time,
                f"Face recognition confidence: {confidence:.2%}" if confidence else None
            ))

            conn.commit()
            conn.close()

            logging.info(f"Attendance recorded for student {student_id}")
            return True

        except sqlite3.Error as e:
            logging.error(f"Error recording attendance: {e}")
            return False

    def add_student_face(self, student_id, face_image_path):
        """
        Add a student's face encoding to the database
        
        :param student_id: ID of the student
        :param face_image_path: Path to the student's face image
        :return: Whether face was successfully added
        """
        try:
            # Load the image
            image = face_recognition.load_image_file(face_image_path)

            # Find face encodings
            face_encodings = face_recognition.face_encodings(image)

            if not face_encodings:
                logging.error(f"No face found in image for student {student_id}")
                return False

            # Take the first face encoding
            face_encoding = face_encodings[0]

            # Convert to base64 for storage
            encoded_face = base64.b64encode(face_encoding.tobytes()).decode('utf-8')

            # Update database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE students 
                SET face_encoding = ?, face_image_path = ? 
                WHERE student_id = ?
            """, (encoded_face, face_image_path, student_id))

            conn.commit()
            conn.close()

            # Reload known faces
            self.load_known_faces()

            logging.info(f"Face added for student {student_id}")
            return True

        except Exception as e:
            logging.error(f"Error adding student face: {e}")
            return False
