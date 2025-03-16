import os
from pathlib import Path


def create_directories():
    """Create necessary directories for the application."""
    dirs = [
        "data",
        "data/models",
        "data/backups",
        "data/training_images",
    ]

    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)

    print("\nApplication directories created successfully!")


def main():
    """Main setup function."""
    print("=" * 50)
    print("Edison Class Vision Management System - Setup")
    print("=" * 50)

    try:
        # Create directories
        create_directories()
        print("\nSetup completed successfully!")
        print("\nYou can now run the application using: python main.py")

    except Exception as e:
        print(f"\nError during setup: {str(e)}")
        print("Setup failed. Please try again.")


if __name__ == "__main__":
    main()
