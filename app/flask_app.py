# stonk-db/app/flask_app.py
# ^^ensure file is located in this directory

# Author: Quinn Marsh
# Date Updated: 2024-03-09
# Description: flask app containg HTTP endpoitns and scheduled tasks

import os
# import sys

from flask import Flask, current_app, request, jsonify
from flask_apscheduler import APScheduler
# from apscheduler.triggers.cron import CronTrigger
# If you're using an application factory, enable CORS for your app instance
# from flask_cors import CORS


# SQLAlchemy database engine and models
from app.database.engine import init_db, init_engine, open_session
from app.database.models import Asset, AssetData

import json
import math
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from ratelimit import sleep_and_retry, limits

import traceback

import time


def create_app(config, init_scheduler=True):
    app = Flask(__name__)

    # Add configuration settings
    if config:
        app.config.update(config)

    # Start database engine
    # app.engine = init_engine(app.config['SQLALCHEMY_DATABASE_URI'])
    engine = init_engine(app.config['SQLALCHEMY_DATABASE_URI'])

    # Start Scheduler for automatic data fetching
    scheduler = APScheduler()
    scheduler.init_app(app)
    app.config['SCHEDULER_ENABLED'] = init_scheduler
    if (not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true"):
        scheduler.start()
  
    # Maually push an application context to perform actions like creating database
    with app.app_context():
        print('Stonk DB Flask App Startup')
        init_db(engine)  # Initialize the database (create tables, etc.)

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        print('App context closed')

    # Periodically fetch most recent data       
    # @scheduler.task(id='fetch_data', trigger='cron', second=0, minute='0,5,10,15,20,25,30,35,40,45,50,55')
    @scheduler.task(id='fetch_data', trigger='cron', second=0)
    def fetch_recent_data():
        # Skip if backfill is running
        if not app.config['SCHEDULER_ENABLED']:
            print("Fetch recent data skipped due to other operations.")
            return
        with app.app_context():
            print('\nFetching recent data.')
            fetch_and_log_assets()
    
    # Example route that uses the database
    @app.route('/list_assets')
    def list_assets():
        session = open_session(engine)
        assets = session.query(Asset).all()  # Querying all assets
        return '\n'.join([asset.name for asset in assets])

    
    @app.route('/backfill_data', methods=['POST'])
    def backfill_data():

        print('\nBackfill Initiated ---------------------------------------------')

        # Pause Scheduled Updates while backfill is running
        app.config['SCHEDULER_ENABLED'] = False
        print('Pausing Automatic Updates')

        # Assuming fetch_and_log_assets is accessible and properly defined
        data = request.json
        start_date_iso = data.get('start_date')
        end_date_iso = data.get('end_date')
        symbol = data.get('symbol')

        try:
            if start_date_iso:
                start_date = datetime.fromisoformat(start_date_iso)
            else:
                ValueError("Missing required parameter: start_date")
            
            if end_date_iso:
                end_date = datetime.fromisoformat(end_date_iso)
            else:
                end_date = None

        except Exception as e:
            return jsonify({"error": e}), 400

        try:
            status, mssg = fetch_and_log_assets(start_date_arg=start_date, end_date_arg=end_date, symbol=symbol)
            if status:
                return jsonify({"message": 'Data Backfilled Successfully'}), 200
            else:
                return jsonify({"message": 'Data Backfill Error'+mssg}), 500
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        finally:
            # Turn automatic updates back on
            app.config['SCHEDULER_ENABLED'] = True
            print('Resuming Automatic Updates')
    
    
    def fetch_and_log_assets(start_date_arg=None, end_date_arg=None, symbol=None):
        # with current_app.app_context():
        '''
        datetimes must be offset aware or they will be assumed to be in UTC
        start_date: None/default behavior to the last entry for each asset
        end_date: None/defaults to the present
        symbol: None/default behavior is 'ALL'

        candle_duration is assumed to be 1-minute '1m' for this data fetching
        '''
        # task code

        # Define database engine
        # engine = current_app.engine

        # hard coded params
        api_limit = 9000 # max number of entries requested per API call (10000 is Bitfinex's max allowed)
        # candle_duration = timedelta(minutes=1)

        error_mssg = ''

        # Load the assets we want to log into the database from assets.json
        file_path = app.config['ASSETS_URI']
        with open(file_path, 'r') as file:
            assets = json.load(file)
            if len(assets) < 1:
                print('Warning: No data fetched: Empty ''assets'' list loaded from assets.json')

        # Filter asset list based on args
        if symbol is not None:
            # filter assets list for the first asset that has 'symbol' as its symbol
            assets = [next((asset for asset in assets if asset.get('symbol') == symbol), None)]
            if len(assets) < 1:
                print('Warning: No data fetched: Invalid ''symbol'' argument')    
        

        for ass in assets:
            # open database session to query for asset.id and to check most recent entry for that asset
            session = open_session(engine)

            try:

                # Check if the Asset already exists, if not, create it
                asset = session.query(Asset).filter_by(symbol=ass['symbol']).first()
                if not asset:
                    asset = Asset(**ass)
                    session.add(asset)
                    session.commit()  # Commit to get an ID for the asset

                asset_id = asset.id # save asset_id for use after session closes

                # Fetch existing timestamps (used to filter out duplicate entries for asset)
                existing_timestamps = {dt[0] for dt in
                    session.query(AssetData.date_time)
                    .filter_by(asset_id=asset_id)
                    # .order_by(AssetData.date_time) # useful for debugging but slows down query
                    .all()
                }

                # Configure Start and End Times for Fetching Data ----------------------------------
                
                # Check if end date is provided
                if end_date_arg is None:
                    # Set end date to now if not provided
                    end_date = datetime.now(ZoneInfo('UTC'))
                else:
                    # If provided: If offset-aware, convert to UTC, if naive assume UTC
                    end_date = to_utc(end_date_arg)

                # Check if start date is provided
                if start_date_arg is None:
                    # If not provided, set equal to the most recent entry for the asset

                    # Query for the most recent entry in AssetData for current asset
                    most_recent_entry = session.query(AssetData).filter_by(asset_id=asset_id).order_by(AssetData.date_time.desc()).first()

                    # If there's no data, this is the first run or all data was deleted; handle accordingly
                    if most_recent_entry is None:
                        # fallback and request older data if no data exists
                        start_date = end_date - timedelta(days=1)
                    else:
                        # Time of the last entry
                        # datetime will be naive (SQLite does not suppert timezone info) and will be interpreted as utc (this assumes we saved them as UTC)
                        start_date = to_utc(most_recent_entry.date_time) # toUTC
                        
                else:
                    # If provided: If offset-aware, convert to UTC, if naive assume UTC
                    start_date = to_utc(start_date_arg)

                # Verify proper format of start and end times
                verify_start_end(start_date, end_date)

                # round down to nearest second
                # end_date = end_date.replace(microsecond=0)
                # start_date = start_date.replace(microsecond=0)
                        
                # ensure dates are formatted as UTC

            except Exception as e:
                session.rollback()
                print(f'Error querying database for asset info and/or most recent reading: {e}')
                error_mssg += e

            finally:
                session.close()


            # Call API several times if needed to get all data
            # open and close database session for each API call
            api_timedelta = timedelta(minutes=1)*api_limit
            api_num_calls = math.ceil((end_date - start_date).total_seconds() / api_timedelta.total_seconds())
            for i_api in range(api_num_calls):

                api_start_time = start_date + i_api * api_timedelta
                api_end_time = min(start_date + (1+i_api) * api_timedelta, datetime.now(ZoneInfo('UTC'))) # upper bracketed so that times cannot be in the future

                # round down to nearest second
                api_end_time = api_end_time.replace(microsecond=0)
                api_start_time = api_start_time.replace(microsecond=0)

                # open session to write data from the next api call
                session = open_session(engine)
                try:

                    # start_timer = time.time()

                    # Fetch data
                    data_src = 'bitfinex'
                    data = fetch_data(ass['symbol'], data_src, api_start_time, api_end_time, api_limit)

                    # print(f'fetching time [s]: {time.time() - start_timer}')

                    # Add data to database (only NEW entries)
                    # added = 0 
                    # for entry in data:
                    #     existing_entry = session.query(AssetData).filter_by(asset_id=asset_id, date_time=entry['date_time']).first()
                    #     if existing_entry:
                    #         # Update existing record logic if needed
                    #         # print(f"Passed: entry @ {entry['date_time']}")
                    #         pass
                    #     else:
                    #         # Insert new record
                    #         new_entry = AssetData(asset_id=asset.id, **entry)
                    #         session.add(new_entry)
                    #         added += 1
                    #         # print(f"Added: entry @ {entry['date_time']}")
                    

                    # start_timer = time.time()

                    # Filter out data entries that already exist
                    new_data = [
                        entry for entry in data
                        if entry['date_time'] not in existing_timestamps
                    ]

                    # add asset_id to new data
                    for entry in new_data:
                        entry['asset_id'] = asset_id

                    # Convert to AssetData objects or use bulk_insert_mappings for dictionaries
                    # new_entries = [AssetData(asset_id=asset_id, **entry) for entry in new_data]

                    # print(f'filtering time [s]: {time.time() - start_timer}')

                    # start_timer = time.time()

                    # Bulk insert new entries
                    # session.bulk_save_objects(new_entries)
                    session.bulk_insert_mappings(AssetData, new_data)

                    # print(f'saving time [s]: {time.time() - start_timer}')

                    session.commit()  # Commit once after all new entries are added

                    # info about run
                    print(f"\nDatabase Session for {ass['symbol']} --------------------------------")
                    print(f"API call: {i_api+1} / {api_num_calls}")
                    print(f'API Date Range: {api_start_time} - {api_end_time}')
                    print(f'API time range [min]: {(api_end_time.timestamp() - api_start_time.timestamp())/60}')

                    earliest = min([entry['date_time'] for entry in data])
                    latest = max([entry['date_time'] for entry in data])
                    print(f'Data Date range: {earliest} - {latest}')
                    print(f'Data time range [min]: {(latest.timestamp() - earliest.timestamp())/60}')
                    print(f'Entries [added / total fetched]: {len(new_data)} / {len(data)}')
                    # print(f'API UNIX range [s]: {api_start_time.timestamp()} - {api_end_time.timestamp()}')
                    # print(f'Data UNIX range [s]: {earliest.timestamp()} - {latest.timestamp()}')

                except Exception as e:
                    session.rollback()
                    print(f'Error adding new data to database: {e}')
                    print(traceback.print_exc())
                    error_mssg += e

                finally:
                    session.close()

        if error_mssg:
            mssg = 'Data fetching had errors:\n' + error_mssg
            return False, mssg
        else:
            mssg = '\nData fetched successfully'
            print(mssg)
            return True, mssg
    

    # def stop_scheduler(scheduler):
    #     for job in scheduler.get_jobs():
    #         scheduler.remove_job(job.id)
    #     print("Scheduler is dead.")
    #     return scheduler

    # def start_scheduler(scheduler):
    #     # Example of adding a job
    #     scheduler.add_job(id='fetch_recent_data', func=fetch_recent_data, trigger='cron', second='0')
    #     print("Scheduler is enabled and started.")
    #     return scheduler
    
    # # Start up schedduler
    # scheduler = APScheduler()
    # scheduler.init_app(app)
    # if init_scheduler:
    #     scheduler = start_scheduler(scheduler)  # Add your scheduled jobs here
    # scheduler.start()
               
    return app

#%% util functions

def to_utc(dt):
    # Check if datetime is offset-aware
    if dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None:
        # It's offset-aware, convert to UTC
        return dt.astimezone(ZoneInfo('UTC'))
    else:
        # It's naive, assume it's in UTC
        return dt.replace(tzinfo=ZoneInfo('UTC'))

def verify_start_end(start_date, end_date):
    # Verify dates are datetime objects
    if not (isinstance(start_date, datetime) and isinstance(end_date, datetime)):
        raise TypeError("Both 'start_date' and 'end_date' must be datetime objects.")

    # Verify they are timezone-aware and in UTC
    utc_zone = ZoneInfo("UTC")
    if start_date.tzinfo is None or start_date.tzinfo != utc_zone:
        raise ValueError("'start_date' is not set to UTC.")
    if end_date.tzinfo is None or end_date.tzinfo != utc_zone:
        raise ValueError("'end_date' is not set to UTC.")

    # Start date is before end date
    if (end_date - start_date).total_seconds() <= 0:
        raise ValueError("Invalid Datetimes: 'end_date' must come after 'start_date'.")



#%% Data Retriever Functions

# def fetch_and_log_assets(start_date_arg=None, end_date_arg=None, symbol=None):
#     # with current_app.app_context():
#     '''
#     datetimes must be offset aware or they will be assumed to be in UTC
#     start_date: None/default behavior to the last entry for each asset
#     end_date: None/defaults to the present
#     symbol: None/default behavior is 'ALL'

#     candle_duration is assumed to be 1-minute '1m' for this data fetching
#     '''
#     # task code
#     print('fetch ALL data task executed')

#     # Define database engine
#     engine = current_app.engine

#     # hard coded params
#     api_limit = 9000 # max number of entries requested per API call (10000 is Bitfinex's max allowed)
#     # candle_duration = timedelta(minutes=1)


#     # Load the assets we want to log into the database from assets.json
#     file_path = current_app.config['ASSETS_URI']
#     with open(file_path, 'r') as file:
#         assets = json.load(file)
#         if len(assets) < 1:
#             print('Warning: No data fetched: Empty ''assets'' list loaded from assets.json')

#     # Filter asset list based on args
#     if symbol is not None:
#         # filter assets list for the first asset that has 'symbol' as its symbol
#         assets = [next((asset for asset in assets if asset.get('symbol') == symbol), None)]
#         if len(assets) < 1:
#             print('Warning: No data fetched: Invalid ''symbol'' argument')    
    

#     for ass in assets:
#         # open database session to query for asset.id and to check most recent entry for that asset
#         session = open_session(engine)

#         try:

#             # Check if the Asset already exists, if not, create it
#             asset = session.query(Asset).filter_by(symbol=ass['symbol']).first()
#             if not asset:
#                 asset = Asset(**ass)
#                 session.add(asset)
#                 session.commit()  # Commit to get an ID for the asset

#             asset_id = asset.id # save asset_id for use after session closes

#             # Configure Start and End Times for Fetching Data ----------------------------------
            
#             # Check if end date is provided
#             if end_date_arg is None:
#                 # Set end date to now if not provided
#                 end_date = datetime.now(ZoneInfo('UTC'))
#             else:
#                 # If provided: If offset-aware, convert to UTC, if naive assume UTC
#                 end_date = to_utc(end_date_arg)

#             # Check if start date is provided
#             if start_date_arg is None:
#                 # If not provided, set equal to the most recent entry for the asset

#                 # Query for the most recent entry in AssetData for current asset
#                 most_recent_entry = session.query(AssetData).filter_by(asset_id=asset_id).order_by(AssetData.date_time.desc()).first()

#                 # If there's no data, this is the first run or all data was deleted; handle accordingly
#                 if most_recent_entry is None:
#                     # fallback and request older data if no data exists
#                     start_date = end_date - timedelta(days=1)
#                 else:
#                     # Time of the last entry
#                     # datetime will be naive (SQLite does not suppert timezone info) and will be interpreted as utc (this assumes we saved them as UTC)
#                     start_date = to_utc(most_recent_entry.date_time) # toUTC
                    
#             else:
#                 # If provided: If offset-aware, convert to UTC, if naive assume UTC
#                 start_date = to_utc(start_date_arg)

#             # Verify proper format of start and end times
#             verify_start_end(start_date, end_date)

#             # round down to nearest second
#             # end_date = end_date.replace(microsecond=0)
#             # start_date = start_date.replace(microsecond=0)
                    
#             # ensure dates are formatted as UTC

#         except Exception as e:
#             session.rollback()
#             print(f'Error querying database for asset info and/or most recent reading: {e}')

#         finally:
#             session.close()


#         # Call API several times if needed to get all data
#         # open and close database session for each API call
#         api_timedelta = timedelta(minutes=1)*api_limit
#         api_num_calls = math.ceil((end_date - start_date).total_seconds() / api_timedelta.total_seconds())
#         for i_api in range(api_num_calls):

#             api_start_time = start_date + i_api * api_timedelta
#             api_end_time = min(start_date + (1+i_api) * api_timedelta, datetime.now(ZoneInfo('UTC'))) # upper bracketed so that times cannot be in the future

#             # round down to nearest second
#             api_end_time = api_end_time.replace(microsecond=0)
#             api_start_time = api_start_time.replace(microsecond=0)

#             # open session to write data from the next api call
#             session = open_session(engine)
#             try:
#                 # Fetch data
#                 data_src = 'bitfinex'
#                 data = fetch_data(ass['symbol'], data_src, api_start_time, api_end_time, api_limit)
#                 print('data fetched! now saving to db')


#                 # Add data to database (only NEW entries)
#                 added = 0 
#                 for entry in data:
#                     existing_entry = session.query(AssetData).filter_by(asset_id=asset_id, date_time=entry['date_time']).first()
#                     if existing_entry:
#                         # Update existing record logic if needed
#                         # print(f"Passed: entry @ {entry['date_time']}")
#                         pass
#                     else:
#                         # Insert new record
#                         new_entry = AssetData(asset_id=asset.id, **entry)
#                         session.add(new_entry)
#                         added += 1
#                         # print(f"Added: entry @ {entry['date_time']}")

#                 # info about run
#                 print(f"Database Session for {ass['symbol']} --------------------------------")
#                 print(f"API call: {i_api+1} / {api_num_calls}")
#                 print(f'API Date Range: {api_start_time} - {api_end_time}')
#                 print(f'API time range [min]: {(api_end_time.timestamp() - api_start_time.timestamp())/60}')

#                 earliest = min([entry['date_time'] for entry in data])
#                 latest = max([entry['date_time'] for entry in data])
#                 print(f'Data Date range: {earliest} - {latest}')
#                 print(f'Data time range [min]: {(latest.timestamp() - earliest.timestamp())/60}')
#                 print(f'Entries [added / total fetched]: {added} / {len(data)}')
#                 # print(f'API UNIX range [s]: {api_start_time.timestamp()} - {api_end_time.timestamp()}')
#                 # print(f'Data UNIX range [s]: {earliest.timestamp()} - {latest.timestamp()}')
#                 print(' ')

                        
#                 session.commit()

#             except Exception as e:
#                 session.rollback()
#                 print(f'Error adding new data to database: {e}')
#                 print(traceback.print_exc())

#             finally:
#                 session.close()

#     return True



# import requests
# import ccxt

# throttle API rate to respect Bitfinex API limits
api_rate_limit = 60
ONE_MINUTE = 60

@sleep_and_retry
@limits(calls=api_rate_limit, period=ONE_MINUTE)
def fetch_data(symbol, data_src, api_start_time=None, api_end_time=None, api_limit=9000):
    """Get asset price from an API"""
    
    try:

        if data_src == 'bitfinex':

            # Bitfinex API
            # docs (w key info): https://docs.bitfinex.com/reference/rest-public-candles            
            keys = ['MTS', 'OPEN', 'CLOSE', 'HIGH', 'LOW', 'VOLUME']

            candle = f"trade:1m:t{symbol}"
            section = 'hist'
            api_start_epoch_ms = int(api_start_time.replace(microsecond=0).timestamp() * 1000) # Convert to millisecond UNIX epoch timestamp
            api_end_epoch_ms = int(api_end_time.replace(microsecond=0).timestamp() * 1000) # Convert to millisecond UNIX epoch timestamp
            api_url = f"https://api-pub.bitfinex.com/v2/candles/{candle}/{section}?start={api_start_epoch_ms}&end={api_end_epoch_ms}&limit={api_limit}&sort=1"

            headers = {"accept": "application/json"}
            response = requests.get(api_url, headers=headers)
            data = response.json()

            formatted_data = [
                {
                    # these keys must match the AssetData model
                    'date_time' : datetime.utcfromtimestamp(entry[keys.index('MTS')]/1000), # POSIX timestamp ms to datetime
                    # 'source'    : api_url, # this is very long anf roughly doubles the data size
                    'source'    : data_src,
                    'open'      : entry[keys.index('OPEN')],
                    'close'     : entry[keys.index('CLOSE')],
                    'high'      : entry[keys.index('HIGH')],
                    'low'       : entry[keys.index('LOW')],
                    'volume'    : entry[keys.index('VOLUME')]
                }
                for entry in data
            ]
            # formatted_data = None
    
            return formatted_data
        
        else:
            print(f"Data source '{data_src}' not recognized")


    except Exception as e:
        print(f"Error fetching stock price for {symbol}: {str(e)}")

    return None


#%% Old code

# def fetch_data_old(symbol, data_src):
#     """Get the stock price from an API"""
    
#     try:

#         if data_src == 'bitfinex':

#             # Bitfinex API
#             # docs (w key info): https://docs.bitfinex.com/reference/rest-public-ticker
#             keys = ['BID', 'BID_SIZE', 'ASK', 'ASK_SIZE', 'DAILY_CHANGE', 'DAILY_CHANGE_RELATIVE', 'LAST_PRICE', 'VOLUME', 'HIGH', 'LOW']
#             bitfinex_symbol = f"t{symbol}"
#             url = f"https://api-pub.bitfinex.com/v2/ticker/{bitfinex_symbol}"
        
#             headers = {"accept": "application/json"}

#             response = requests.get(url, headers=headers)
#             date_time = datetime.now().replace(microsecond=0)  # Round down to nearest second (This is moves as close to the API call as possible)

#             data = response.json()

#             price = data[keys.index('LAST_PRICE')]
#             volume = data[keys.index('VOLUME')]

#             formatted_data = {
#                 # these keys MUST match the database fields
#                 # 'symbol':symbol, 
#                 'source':data_src, 
#                 'date_time':date_time, 
#                 'price':price, 
#                 'volume':volume
#             }
    
#             return formatted_data
        
#         else:
#             print(f"Data source '{data_src}' not recognized")


#     except Exception as e:
#         print(f"Error fetching stock price for {symbol}: {str(e)}")

#     return None


        # below is old code for other API sources, would need some updating to get working

        # if price_src == 'yfinance':
        #     # Create a Ticker object for the specified symbol
        #     ticka = yf.Ticker(ticker)
        #     # ticka = {'info':{'previousClose': 69.420}}
            
        #     # Retrieve the current stock price (previousClose) from the Ticker info
        #     # current_price = ticka.info.get('previousClose')
        #     current_price = ticka.basic_info.last_price
            
        # elif price_src == 'ccxt':
        #     # Get crypocurrency price
        #     exchange = ccxt.binanceus()
        #     symbol = ticker+'/USDT'  # symbol
        #     ticka = exchange.fetch_ticker(symbol)
        #     current_price = ticka['last']  # Get the last traded price

        # # Return the current price
        # if current_price is not None:
        #     return current_price
        # # Handle the case where price_src is not recognized
        # else:
        #     print(f"Price source {price_src} not recognized")





    # old code for a single hard-coded asset
    # def fetch_and_log_btc():
    #     # task code
    #     print('fetch BTC data task executed')

    #     # trading info
    #     asset_info = {
    #         # these keys MUST match the database fields
    #         'name' : 'Bitcoin',
    #         'base_symbol' : 'BTC',
    #         'quote_symbol' : 'USD',
    #         'symbol' : 'BTCUSD', #['BTCUSD']
    #         'type' : 'crypto',
    #     }
        
    #     data_src = 'bitfinex'
    #     data = fetch_data(asset_info['symbol'], data_src)

    #     session = open_session(engine)

    #     try:
    #         # Check if the asset Asset already exists, if not, create it
    #         asset = session.query(Asset).filter_by(symbol=asset_info['symbol']).first()
    #         if not asset:
    #             asset = Asset(**asset_info)
    #             session.add(asset)
    #             session.commit()  # Commit to get an ID for the btc_asset

    #         # Create a new AssetData instance with the response data
    #         data['asset_id'] = asset.id
    #         asset_data = AssetData(**data)
    #         session.add(asset_data)
    #         session.commit()
    #         print('Data added succesfully to database!')

    #     except Exception as e:
    #         session.rollback()
    #         print(f'Error adding new data to database: {e}')

    #     finally:
    #         session.close()

        # cleaner way of handlling sessions???
        # from contextlib import contextmanager
        # @contextmanager
        # def session_scope():
        #     """Provide a transactional scope around a series of operations."""
        #     session = Session()  # Assuming Session is a sessionmaker instance
        #     try:
        #         yield session
        #         session.commit()
        #     except Exception as e:
        #         session.rollback()
        #         print(f'Error: {e}')
        #         raise
        #     finally:
        #         session.close()
        # with session_scope() as session:
        #     # Your database operations here
        #     asset = session.query(Asset).filter_by(symbol=asset_info.symbol).first()
        #     if not asset:
        #         asset = Asset(**asset_info.dict())  # Assuming asset_info is a Pydantic model or similar
        #         session.add(asset)
        #     # Create and add AssetData instance
        #     asset_data = AssetData(**data)
        #     session.add(asset_data)




                # [old method, could create duplicate entries] Bulk add all data to database
                # session.bulk_insert_mappings(AssetData, data)