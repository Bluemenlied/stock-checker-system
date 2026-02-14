import os
from flask import Flask
from dotenv import load_dotenv
from database import init_db, db
from models import User

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def create_admin():
    with app.app_context():
        # Check if admin exists
        admin = User.query.filter_by(username='admin').first()
        
        if admin:
            print("⚠️ Admin user already exists!")
            overwrite = input("Overwrite? (yes/no): ").strip().lower()
            if overwrite == 'yes':
                db.session.delete(admin)
                db.session.commit()
                print("✅ Existing admin removed")
            else:
                print("❌ Cancelled")
                return
        
        # Create new admin
        new_admin = User(
            username='admin',
            password=User.hash_password('admin123'),
            role='admin',
            email='admin@stockchecker.com',
            full_name='System Administrator',
            is_active=True
        )
        
        db.session.add(new_admin)
        db.session.commit()
        print("\n" + "="*50)
        print("✅ ADMIN USER CREATED SUCCESSFULLY!")
        print("="*50)
        print("   Username: admin")
        print("   Password: admin123")
        print("="*50)

if __name__ == '__main__':
    create_admin()