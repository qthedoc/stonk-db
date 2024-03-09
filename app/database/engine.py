# engine.py
# defining assets.db engine
# Quinn Marsh

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
# Import Base from models.py to ensure model tables are recognized
from .models import Base  # Adjust the import path as necessary


def init_engine(db_uri):
    # Connect to the database
    engine = create_engine(db_uri, echo=True)
    return engine

def open_session(engine):
    # Create a configured "Session" class     
    Session = sessionmaker(bind=engine)

    # Create a session
    session = Session()

    return session

def init_db(engine):
    # Create all tables by using Base.metadata.create_all
    Base.metadata.create_all(engine)

if __name__ == "__main__":
    # Initialize the database (create tables) if running this script directly
    init_db()

# Create a session to interact with the database
# Session = sessionmaker(bind=engine)
# session = Session()