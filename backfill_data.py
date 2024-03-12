# stonk-db/backfill_data.py
# ^^ensure file is located in this directory

# Author: Quinn Marsh
# Date Updated: 2024-03-09
# Description: Manually add data to database

# APP MUST BE ALREADY RUNNING

import requests
import json
from datetime import datetime

# Start date is the only required parameter here all other can be commented out
# End date will default to the present
# Symbol will default to fetching all database assets defined in assets.json

data = {
    'start_date': datetime(2023,9,1).isoformat(),
    "end_date": datetime(2023,10,2).isoformat(),
    # "symbol": 'BTCUSD'
}

url = 'http://localhost:5002/backfill_data'
headers = {'Content-Type': 'application/json'}
response = requests.post(url, headers=headers, data=json.dumps(data))

if response.status_code == 200:
    print("Backfill initiated successfully", response.json())
else:
    print("Error initiating backfill:", response.json())






# DO NOT RUN THIS SCRIPT WHILE APP IS RUNNING
# this could result database conflicts and exceeding API limits
# import os
# import json
# from datetime import datetime

# from main import main, load_config
# from app.flask_app import create_app

# def backfill_data():
#     # app = main(init_scheduler=False)

#     # Determine the project root directory
#     PROJECT_ROOT = os.path.dirname( os.path.abspath(__file__) )
    
#     # load config file with keys paths and app configuration info
#     config = load_config(PROJECT_ROOT)

#     # Pass config settings to the Flask app creation function
#     app = create_app(config, init_scheduler=False)

#     with app.app_context():
#         print('starting app context')
#         start_date = datetime(2023, 1, 1)
#         symbol='BTCUSD'
#         fetch_and_log_assets(start_date=start_date, symbol=symbol)
#         print('closing app context')


# if __name__ == '__main__':
#     backfill_data()
