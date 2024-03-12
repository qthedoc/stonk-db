# stonk-db/setup.py
# ^^ensure file is located in this directory

# Author: Quinn Marsh
# Date Updated: 2024-03-09
# Description: app initialization script, run this before using the app

# Notes:
# Reruning this file to change configuraitons should be fine

import os
import json

# Determine the project root directory
# ensure this file is located in the project root under stonk-bd
PROJECT_ROOT = os.path.dirname( os.path.abspath(__file__) )
CONFIG_URI = os.path.join(PROJECT_ROOT, 'config', 'config.json')
ASSETS_URI = os.path.join(PROJECT_ROOT, 'config', 'assets.json')
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(PROJECT_ROOT, 'db', 'assets.db')

# Setup App Instance Settings
def create_config():

    config = {
        # These will all be added to Flasks app.config
        'IP': '0.0.0.0',
        'PORT': 5002,
        'PROJECT_ROOT': PROJECT_ROOT,
        'CONFIG_URI': CONFIG_URI,
        'ASSETS_URI': ASSETS_URI,
        'SQLALCHEMY_DATABASE_URI': SQLALCHEMY_DATABASE_URI
    }

    file_path = CONFIG_URI
    with open(file_path, 'w+') as file:
        json.dump(config, file, indent=2)

# Choose which assets to track
def set_assets():
    assets = [
        # 'symbol' field must match a pair on bitfinex.com
        # all fields are required for adding assets to the database
        {'name':'Bitcoin', 'symbol':'BTCUSD', 'base_symbol': 'BTC', 'quote_symbol': 'USD', 'type': 'crypto'},
        {'name':'Ethereum', 'symbol':'ETHUSD', 'base_symbol': 'ETH', 'quote_symbol': 'USD', 'type': 'crypto'},
        # {'name':'Bitcoin', 'symbol':'BTCUSD', 'base_symbol': 'BTC', 'quote_symbol': 'USD', 'type': 'crypto'},
        # {'name':'Bitcoin', 'symbol':'BTCUSD', 'base_symbol': 'BTC', 'quote_symbol': 'USD', 'type': 'crypto'},
        # {'name':'Bitcoin', 'symbol':'BTCUSD', 'base_symbol': 'BTC', 'quote_symbol': 'USD', 'type': 'crypto'},
        # {'name':'Bitcoin', 'symbol':'BTCUSD', 'base_symbol': 'BTC', 'quote_symbol': 'USD', 'type': 'crypto'},
        # {'name':'Bitcoin', 'symbol':'BTCUSD', 'base_symbol': 'BTC', 'quote_symbol': 'USD', 'type': 'crypto'},
    ]

    file_path = ASSETS_URI
    with open(file_path, 'w+') as file:
        json.dump(assets, file, indent=2)

    asset_symbols = [asset['symbol'] for asset in assets]

    print('The following assets will be tracked by the database:')
    print(asset_symbols)

# check that all file paths are as expected
def verify_installation():
    expected_paths = [
        'main.py',
        'setup.py',
        os.path.join('app', '__init__.py'),
        os.path.join('app', 'flask_app.py'),
        os.path.join('app', 'database', '__init__.py'),
        os.path.join('app', 'database', 'engine.py'),
        os.path.join('app', 'database', 'models.py'),
        os.path.join('db'),
        os.path.join('config'),
        os.path.join('env'),
    ]

    missing_paths = [path for path in expected_paths if not os.path.exists(path)]

    if missing_paths:
        print("The following expected files/directories are missing:")
        for path in missing_paths:
            print(f" - {path}")
        return False
    else:
        print("All necessary files and directories are in place!")
        return True

if __name__ == '__main__':
    verify_installation()
    create_config()
    set_assets()

