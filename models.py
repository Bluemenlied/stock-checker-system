from database import db
from datetime import datetime
import hashlib
import secrets
import json  # Added missing import

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.UUID, primary_key=True, server_default=db.text('gen_random_uuid()'))
    username = db.Column(db.String, unique=True, nullable=False)
    password = db.Column(db.String, nullable=False)
    role = db.Column(db.String, nullable=False)
    email = db.Column(db.String)
    full_name = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    password_changed_at = db.Column(db.DateTime, default=datetime.utcnow)

    @staticmethod
    def hash_password(password):
        salt = secrets.token_hex(16)
        hash_obj = hashlib.sha256((password + salt).encode())
        return f"{salt}${hash_obj.hexdigest()}"

    @staticmethod
    def verify_password(password, hashed_password):
        salt, hash_value = hashed_password.split('$')
        hash_obj = hashlib.sha256((password + salt).encode())
        return hash_obj.hexdigest() == hash_value

class File(db.Model):
    __tablename__ = 'files'
    
    id = db.Column(db.UUID, primary_key=True, server_default=db.text('gen_random_uuid()'))
    filename = db.Column(db.String, nullable=False)
    file_date = db.Column(db.Date, nullable=False)
    record_count = db.Column(db.Integer, default=0)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_by = db.Column(db.String)
    file_size = db.Column(db.Integer)
    inventory = db.relationship('Inventory', backref='file', lazy=True, cascade='all, delete-orphan')

class Inventory(db.Model):
    __tablename__ = 'inventory'
    
    id = db.Column(db.UUID, primary_key=True, server_default=db.text('gen_random_uuid()'))
    file_id = db.Column(db.UUID, db.ForeignKey('files.id', ondelete='CASCADE'))
    sku = db.Column(db.String, nullable=False, index=True)
    description = db.Column(db.String)
    category = db.Column(db.String)
    last_count_date = db.Column(db.Date)
    last_count = db.Column(db.Integer, default=0)
    total_container_qty = db.Column(db.Integer, default=0)
    container_details = db.Column(db.Text)
    final_expected_count = db.Column(db.Integer, default=0)
    kenneth_inventory = db.Column(db.Integer, default=0)
    buffer_qty = db.Column(db.Integer, default=0)
    stock_status = db.Column(db.String)
    inventory_remark = db.Column(db.Text)
    file_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    @property
    def available_stock(self):
        return (self.kenneth_inventory or 0) + (self.total_container_qty or 0)
    
    @property
    def stock_level(self):
        avail = self.available_stock
        if avail <= 0:
            return 'out_of_stock'
        elif avail <= (self.buffer_qty or 0):
            return 'low_stock'
        return 'in_stock'
    
    @property
    def has_incoming(self):
        return (self.total_container_qty or 0) > 0

class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String)
    action = db.Column(db.String, nullable=False)
    details = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

# ============================================================================
# SETTINGS MODEL FOR PERSISTENT CONFIGURATION
# ============================================================================
class Settings(db.Model):
    __tablename__ = 'settings'
    
    id = db.Column(db.Integer, primary_key=True, default=1)  # Singleton row
    system_name = db.Column(db.String, default='Stock Checker System')
    logo_path = db.Column(db.String, default='/static/images/default-logo.png')
    primary_color = db.Column(db.String, default='#2563eb')
    success_color = db.Column(db.String, default='#059669')
    warning_color = db.Column(db.String, default='#d97706')
    danger_color = db.Column(db.String, default='#dc2626')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PrintRequest(db.Model):
    __tablename__ = 'print_requests'
    
    id = db.Column(db.UUID, primary_key=True, server_default=db.text('gen_random_uuid()'))
    request_id = db.Column(db.String, unique=True, nullable=False)
    requested_by = db.Column(db.String, nullable=False)
    requested_by_id = db.Column(db.String, nullable=False)
    requested_by_role = db.Column(db.String, nullable=False, default='viewer')
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String, default='pending')
    sku_list = db.Column(db.Text, nullable=False)  # JSON array of objects [{sku: "...", qty: n}]
    sku_count = db.Column(db.Integer, nullable=False)
    notes = db.Column(db.Text)
    approved_by = db.Column(db.String)
    approved_at = db.Column(db.DateTime)
    printed_at = db.Column(db.DateTime)
    printed_by = db.Column(db.String)
    download_count = db.Column(db.Integer, default=0)
    completed_at = db.Column(db.DateTime)
    completed_by = db.Column(db.String)
    source_type = db.Column(db.String)
    source_file_id = db.Column(db.UUID, db.ForeignKey('files.id'))
    source_file = db.relationship('File')
    
    @staticmethod
    def generate_request_id():
        from datetime import datetime
        today = datetime.utcnow().strftime('%Y%m%d')
        count = PrintRequest.query.filter(
            db.func.date(PrintRequest.requested_at) == datetime.utcnow().date()
        ).count() + 1
        return f"PR-{today}-{count:04d}"
    
    def get_sku_list(self):
        """Return the SKU list as a Python list of objects with sku and qty"""
        if self.sku_list:
            return json.loads(self.sku_list)
        return []
    
    def set_sku_list(self, skus):
        """Store SKU list as JSON array of objects with sku and qty"""
        self.sku_list = json.dumps(skus)
        self.sku_count = len(skus)