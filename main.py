# stonk-db/main.py
# ^^ensure file is located in this directory

# Author: Quinn Marsh
# Date Updated: 2024-03-09
# Description: entry point for the stonk-db app

import os
import json
from app.flask_app import create_app

def main():
    # Determine the project root directory
    PROJECT_ROOT = os.path.dirname( os.path.abspath(__file__) )
    
    # load config file with keys paths and app configuration info
    config = load_config(PROJECT_ROOT)

    # Pass config settings to the Flask app creation function
    app = create_app(config)

    # Run the Flask app
    app.run(host=config['IP'], port=config['PORT']) #  debug=True, 


def load_config(PROJECT_ROOT):
    # load config file with keys paths and app configuration info
    file_path = os.path.join(PROJECT_ROOT, 'config', 'config.json')
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            config = json.load(file)
    else:
        FileNotFoundError('App could not be started: Could not locate ''config.json'' file. Try initialing app with ''setup.py'' and run again.')

    return config


if __name__ == '__main__':
    main()