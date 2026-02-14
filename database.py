from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
import os

db = SQLAlchemy()

def init_db(app):
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 10,
        'pool_recycle': 300,
        'pool_pre_ping': True,
    }
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
        print("✅ Database connected successfully!")