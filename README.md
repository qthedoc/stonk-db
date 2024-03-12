# stonk-db
Live Database for any stonk or crypto data you may want! Designed to run on RaspberryPi

database is made with SQLAlchemy and runs on flask


# Setup Instructions
1. I recomend making a virtual env at stonk-db/p310

2. Required Packages
pip install <packages>:
os
json
datetime
flask
flask_apscheduler
sqlalchemy

3. review and then run stonk-db/setup.py to configure the app, which assets to log, and create instance files

4. Backfill data using the backfill_data.py script. DO NOT RUN THIS WHEN THE APP IS RUNNING

5. Run the app by running stonk-db/main.py (I recomend making this a system task so it autmatically runs even after system reboot)

# App Structure:
/stonk-db
│   main.py # main entry point for application
|   setup.py # script that should be run upon install, this creates neccesary instance files
|
├───/app
|   |   __init__.py
│   │   flask_app.py  # Flask application
│   │
│   ├───/database
│   │   │   __init__.py
│   │   │   engine.py  # SQLAlchemy engine setup
│   │   │   models.py  # SQLAlchemy ORM models
│
├───/db
|   |   asset.db # the actual database containing assets and asset_data
│
├───/config
|   |   config.json # instance specific settings like IP, port and file paths
|   |   assets.json # which assets will be tracked by the database
│
├───/env
│   │
│   ├───/<virtual env>
|   |   |   ... # I recomend putting virtualenv here to keep things together