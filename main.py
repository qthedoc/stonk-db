# stonk-db/main.py
# entry point for our app
import os
from app.flask_app import create_app

def main():
    # Determine the project root directory
    PROJECT_ROOT = os.path.dirname( os.path.abspath(__file__) )
    
    # Pass the project root to the Flask app creation function
    app = create_app(PROJECT_ROOT)
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5002) # debug=True, 

if __name__ == '__main__':
    main()