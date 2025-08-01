#!/usr/bin/env python3
"""
APK Editor - Main Application Entry Point
A web-based APK editor for modifying Android applications
"""

import os
import sys
from app import create_app, db

def main():
    """Main application entry point"""
    print("=" * 60)
    print("APK Editor - Web Application")
    print("=" * 60)
    print("Starting server...")
    print("Server will be available at: http://127.0.0.1:5001")
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    
    # Create the Flask app
    app = create_app()

    with app.app_context():
        db.create_all()

    # Run the application
    try:
        app.run(
            host='127.0.0.1',
            port=5001,
            debug=True,
            use_reloader=False  # Disable reloader to prevent double startup
        )
    except KeyboardInterrupt:
        print("\nShutting down server...")
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()