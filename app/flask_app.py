
import os
# import sys

from flask import Flask
from flask_apscheduler import APScheduler
# from apscheduler.triggers.cron import CronTrigger
# If you're using an application factory, enable CORS for your app instance
# from flask_cors import CORS


# SQLAlchemy database engine and models
from app.database.engine import init_db, init_engine, open_session
from app.database.models import Asset, AssetData

# import json
# from datetime import datetime, timedelta

def create_app(project_root):
    app = Flask(__name__)
    scheduler = APScheduler()
    
    # Use project_root as needed, e.g., for configuring database paths
    app.config['PROJECT_ROOT'] = project_root
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.config['PROJECT_ROOT'], 'db', 'assets.db')

    # Start engine to connect with database
    engine = init_engine(app.config['SQLALCHEMY_DATABASE_URI'])

    # Start Scheduler for Data Retreiver
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        scheduler.init_app(app)
        scheduler.start()


    # Maually push an application context to perform actions like creating database
    with app.app_context():
        print('Stonk DB Flask App Startup')
        init_db(engine)  # Initialize the database (create tables, etc.)

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        print('Stonk DB Flask App Shutdown')
    
    @app.route('/')
    def hello_world():
        return 'Hello, World!'
    
    # Example route that uses the database
    @app.route('/assets')
    def list_assets():
        session = open_session(engine)
        assets = session.query(Asset).all()  # Querying all assets
        return '\n'.join([asset.name for asset in assets])
    
    @scheduler.task(id='fetch_btc_data', trigger='cron', second=0)
    def fetch_btc():
        # task code
        print('fetch BTC data task executed')

        # trading info
        asset_info = {
            # these keys MUST match the database fields
            'name' : 'Bitcoin',
            'base_symbol' : 'BTC',
            'quote_symbol' : 'USD',
            'symbol' : 'BTCUSD', #['BTCUSD']
            'type' : 'crypto',
        }
        
        data_src = 'bitfinex'
        data = fetch_data(asset_info['symbol'], data_src)

        session = open_session(engine)

        try:
            # Check if the asset Asset already exists, if not, create it
            asset = session.query(Asset).filter_by(symbol=asset_info['symbol']).first()
            if not asset:
                asset = Asset(**asset_info)
                session.add(asset)
                session.commit()  # Commit to get an ID for the btc_asset

            # Create a new AssetData instance with the response data
            data['asset_id'] = asset.id
            asset_data = AssetData(**data)
            session.add(asset_data)
            session.commit()
            print('Data added succesfully to database!')

        except Exception as e:
            session.rollback()
            print(f'Error adding new data to database: {e}')

        finally:
            session.close()

        # cleaner way of doing it???
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

    return app


#%% Price Retriever Class

import requests
from datetime import datetime
# import ccxt

def fetch_data(symbol, data_src):
    """Get the stock price from an API"""
    
    try:

        if data_src == 'bitfinex':

            # Bitfinex API
            # docs (w key info): https://docs.bitfinex.com/reference/rest-public-ticker
            keys = ['BID', 'BID_SIZE', 'ASK', 'ASK_SIZE', 'DAILY_CHANGE', 'DAILY_CHANGE_RELATIVE', 'LAST_PRICE', 'VOLUME', 'HIGH', 'LOW']
            bitfinex_symbol = f"t{symbol}"
            url = f"https://api-pub.bitfinex.com/v2/ticker/{bitfinex_symbol}"
        
            headers = {"accept": "application/json"}

            response = requests.get(url, headers=headers)
            date_time = datetime.now().replace(microsecond=0)  # Round down to nearest second (This is moves as close to the API call as possible)

            data = response.json()

            price = data[keys.index('LAST_PRICE')]
            volume = data[keys.index('VOLUME')]

            formatted_data = {
                # these keys MUST match the database fields
                # 'symbol':symbol, 
                'source':data_src, 
                'date_time':date_time, 
                'price':price, 
                'volume':volume
            }
    
            return formatted_data
        
        else:
            print(f"Data source '{data_src}' not recognized")


    except Exception as e:
        print(f"Error fetching stock price for {symbol}: {str(e)}")

    return None


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





