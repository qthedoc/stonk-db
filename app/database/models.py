# app/database/models.py
# defining assets.db models
# Quinn Marsh

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base() # The declarative base class contains a MetaData object where newly defined Table objects are collected. This allows SQLAlchemy to understand and map the database structure to your Python classes.

class Asset(Base):
    __tablename__ = 'assets'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    symbol = Column(String)
    base_symbol = Column(String)
    quote_symbol = Column(String)
    type = Column(String)  # e.g., 'stock', 'crypto'
    data = relationship("AssetData", back_populates="asset")

    def __init__(self, name, symbol, base_symbol, quote_symbol, type):
        self.name = name
        self.symbol = symbol
        self.base_symbol = base_symbol
        self.quote_symbol = quote_symbol
        self.type = type

class AssetData(Base):
    __tablename__ = 'asset_data'

    id = Column(Integer, primary_key=True)
    asset_id = Column(Integer, ForeignKey('assets.id'))
    date_time = Column(DateTime)
    source = Column(String)
    price = Column(Float)
    volume = Column(Float)  # Example additional parameter
    asset = relationship("Asset", back_populates="data")

    def __init__(self, asset_id, date_time, source, price, volume=None):
        self.asset_id = asset_id
        self.date_time = date_time
        self.source = source
        self.price = price
        self.volume = volume



