import os
import json
import re
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.utils import secure_filename
from functools import wraps
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import database modules
from database import db
from models import User, File, Inventory, ActivityLog, Settings, PrintRequest
from sqlalchemy import or_, desc

app = Flask(__name__)

# ============================================================================
# CONFIGURATION - LOADED FROM .ENV
# ============================================================================
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-this')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 10,
    'pool_recycle': 300,
    'pool_pre_ping': True,
}

# Upload configuration
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['ITEMS_PER_PAGE'] = 20
app.config['LOGS_PER_PAGE'] = 30

# Logo upload configuration
app.config['LOGO_UPLOAD_FOLDER'] = 'static/images'
app.config['ALLOWED_LOGO_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'svg'}

# Allowed file extensions
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================
db.init_app(app)

# Create tables if they don't exist
with app.app_context():
    db.create_all()
    
    # Initialize default settings if not exists
    if not Settings.query.get(1):
        default_settings = Settings(
            id=1,
            system_name=os.environ.get('SYSTEM_NAME', 'Stock Checker System'),
            logo_path=os.environ.get('SYSTEM_LOGO', '/static/images/default-logo.png'),
            primary_color=os.environ.get('PRIMARY_COLOR', '#2563eb'),
            success_color=os.environ.get('SUCCESS_COLOR', '#059669'),
            warning_color=os.environ.get('WARNING_COLOR', '#d97706'),
            danger_color=os.environ.get('DANGER_COLOR', '#dc2626')
        )
        db.session.add(default_settings)
        db.session.commit()
    
    print("✅ Database connected successfully!")
    print(f"📊 Database URL: {app.config['SQLALCHEMY_DATABASE_URI']}")

# ============================================================================
# AUTHENTICATION HELPERS
# ============================================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'role' not in session:
                flash('Access denied', 'error')
                return redirect(url_for('dashboard'))
            if session['role'] not in allowed_roles:
                flash('You do not have permission to access this page', 'error')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def prevent_back_after_logout(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        response = f(*args, **kwargs)
        if isinstance(response, str):
            return response
        try:
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        except AttributeError:
            pass
        return response
    return decorated_function

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_logo_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_LOGO_EXTENSIONS']

# ============================================================================
# CONTEXT PROCESSORS
# ============================================================================

@app.context_processor
def inject_system_settings():
    """Inject system settings from database into all templates"""
    try:
        settings = Settings.query.get(1)
        if settings:
            return {
                'system_name': settings.system_name,
                'logo_url': settings.logo_path,
                'primary_color': settings.primary_color,
                'secondary_color': os.environ.get('SECONDARY_COLOR', '#4b5563'),
                'success_color': settings.success_color,
                'warning_color': settings.warning_color,
                'danger_color': settings.danger_color
            }
    except Exception as e:
        print(f"Error loading settings: {e}")
    
    # Fallback to environment variables
    return {
        'system_name': os.environ.get('SYSTEM_NAME', 'Stock Checker System'),
        'logo_url': os.environ.get('SYSTEM_LOGO', '/static/images/default-logo.png'),
        'primary_color': os.environ.get('PRIMARY_COLOR', '#2563eb'),
        'secondary_color': os.environ.get('SECONDARY_COLOR', '#4b5563'),
        'success_color': os.environ.get('SUCCESS_COLOR', '#059669'),
        'warning_color': os.environ.get('WARNING_COLOR', '#d97706'),
        'danger_color': os.environ.get('DANGER_COLOR', '#dc2626')
    }

# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@app.route('/')
@prevent_back_after_logout
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
@prevent_back_after_logout
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember')
        
        user = User.query.filter_by(username=username, is_active=True).first()
        
        if user and User.verify_password(password, user.password):
            session.clear()
            session['user_id'] = str(user.id)
            session['username'] = user.username
            session['role'] = user.role
            session['full_name'] = user.full_name or user.username
            
            if remember:
                session.permanent = True
            
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            # Log activity
            log = ActivityLog(
                user_id=str(user.id),
                action='LOGIN',
                details=f'User {username} logged in'
            )
            db.session.add(log)
            db.session.commit()
            
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html', title='Login')

@app.route('/logout')
def logout():
    if 'user_id' in session:
        log = ActivityLog(
            user_id=session['user_id'],
            action='LOGOUT',
            details=f'User {session["username"]} logged out'
        )
        db.session.add(log)
        db.session.commit()
    
    session.clear()
    flash('You have been logged out', 'success')
    return redirect(url_for('login'))

@app.route('/check-session')
def check_session():
    return jsonify({'authenticated': 'user_id' in session})

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
@prevent_back_after_logout
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password != confirm_password:
            flash('New passwords do not match', 'danger')
            return redirect(url_for('change_password'))
        
        if len(new_password) < 8:
            flash('Password must be at least 8 characters long', 'danger')
            return redirect(url_for('change_password'))
        
        user = User.query.get(session['user_id'])
        
        if user and User.verify_password(current_password, user.password):
            user.password = User.hash_password(new_password)
            user.password_changed_at = datetime.utcnow()
            db.session.commit()
            
            log = ActivityLog(
                user_id=session['user_id'],
                action='CHANGE_PASSWORD',
                details='User changed password'
            )
            db.session.add(log)
            db.session.commit()
            
            flash('Password changed successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Current password is incorrect', 'danger')
    
    return render_template('change_password.html', title='Change Password')

# ============================================================================
# MAIN DASHBOARD ROUTES
# ============================================================================

@app.route('/dashboard')
@login_required
@prevent_back_after_logout
def dashboard():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('q', '')
    file_id = request.args.get('file_id')
    
    # Get available files
    files = File.query.order_by(File.file_date.desc()).all()
    available_files = []
    for f in files:
        available_files.append({
            'id': str(f.id),
            'filename': f.filename,
            'file_date': f.file_date.strftime('%Y-%m-%d'),
            'display_date': f.file_date.strftime('%b %d, %Y'),
            'record_count': f.record_count,
            'upload_date': f.uploaded_at.strftime('%Y-%m-%d %H:%M') if f.uploaded_at else None
        })
    
    # Get current file
    current_file = None
    if file_id:
        for f in available_files:
            if f['id'] == file_id:
                current_file = f
                break
    elif available_files:
        current_file = available_files[0]
        file_id = current_file['id']
    
    # Search inventory
    per_page = app.config.get('ITEMS_PER_PAGE', 20)
    result = search_sku(search_query, file_id, page, per_page)
    
    # Get statistics
    stats = None
    if current_file:
        stats = get_stats(current_file['id'])
    
    # Check if file needs update (older than 1 day)
    needs_update = False
    if current_file and 'file_date' in current_file:
        try:
            file_date = datetime.strptime(current_file['file_date'], '%Y-%m-%d')
            days_diff = (datetime.utcnow() - file_date).days
            needs_update = days_diff >= 1
        except:
            pass
    
    # Log activity
    log = ActivityLog(
        user_id=session['user_id'],
        action='VIEW_DASHBOARD',
        details=f'Viewed dashboard. File: {current_file["display_date"] if current_file else "None"}'
    )
    db.session.add(log)
    db.session.commit()
    
    return render_template(
        'dashboard.html',
        title='Dashboard',
        items=result['items'],
        pagination=result,
        search_query=search_query,
        available_files=available_files,
        current_file=current_file,
        stats=stats,
        needs_update=needs_update
    )

def search_sku(query, file_id=None, page=1, per_page=20):
    """Search SKU in PostgreSQL database"""
    try:
        query_obj = Inventory.query
        
        if file_id:
            query_obj = query_obj.filter(Inventory.file_id == file_id)
        else:
            # Get latest file
            latest_file = File.query.order_by(File.file_date.desc()).first()
            if latest_file:
                query_obj = query_obj.filter(Inventory.file_id == latest_file.id)
            else:
                return {'items': [], 'total': 0, 'page': page, 'per_page': per_page, 'total_pages': 0}
        
        if query:
            search_term = f"%{query}%"
            query_obj = query_obj.filter(
                or_(
                    Inventory.sku.ilike(search_term),
                    Inventory.description.ilike(search_term),
                    Inventory.category.ilike(search_term),
                    Inventory.inventory_remark.ilike(search_term)
                )
            )
        
        total = query_obj.count()
        items = query_obj.order_by(Inventory.sku).offset((page-1)*per_page).limit(per_page).all()
        
        items_list = []
        for item in items:
            items_list.append({
                'id': str(item.id),
                'sku': item.sku,
                'description': item.description,
                'category': item.category,
                'last_count_date': item.last_count_date.strftime('%Y-%m-%d') if item.last_count_date else None,
                'last_count': item.last_count,
                'total_container_qty': item.total_container_qty,
                'container_details': item.container_details,
                'kenneth_inventory': item.kenneth_inventory,
                'buffer_qty': item.buffer_qty,
                'stock_status': item.stock_status,
                'inventory_remark': item.inventory_remark,
                'available_stock': item.available_stock,
                'stock_level': item.stock_level,
                'has_incoming': item.has_incoming,
                'file_date': item.file_date.strftime('%Y-%m-%d') if item.file_date else None
            })
        
        return {
            'items': items_list,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page if total > 0 else 0
        }
    except Exception as e:
        print(f"Search error: {e}")
        return {'items': [], 'total': 0, 'page': page, 'per_page': per_page, 'total_pages': 0}

def get_stats(file_id):
    """Get inventory statistics"""
    try:
        items = Inventory.query.filter_by(file_id=file_id).all()
        
        total = len(items)
        in_stock = sum(1 for i in items if i.stock_level == 'in_stock')
        low_stock = sum(1 for i in items if i.stock_level == 'low_stock')
        out_of_stock = sum(1 for i in items if i.stock_level == 'out_of_stock')
        
        return {
            'total_skus': total,
            'in_stock': in_stock,
            'low_stock': low_stock,
            'out_of_stock': out_of_stock
        }
    except Exception as e:
        print(f"Error getting stats: {e}")
        return None

# ============================================================================
# BULK SEARCH ROUTE
# ============================================================================
@app.route('/bulk-search', methods=['GET', 'POST'])
@login_required
def bulk_search():
    if request.method == 'GET':
        # Get available files for the dropdown
        files = File.query.order_by(File.file_date.desc()).all()
        available_files = []
        for f in files:
            available_files.append({
                'id': str(f.id),
                'filename': f.filename,
                'file_date': f.file_date.strftime('%Y-%m-%d'),
                'display_date': f.file_date.strftime('%b %d, %Y'),
                'record_count': f.record_count
            })
        return render_template('bulk_search.html', title='Bulk Search', available_files=available_files)
    
    elif request.method == 'POST':
        try:
            import pandas as pd
            
            if 'file' not in request.files:
                return jsonify({'success': False, 'error': 'No file uploaded'}), 400
            
            file = request.files['file']
            file_id = request.form.get('file_id')
            
            if not file or not file_id:
                return jsonify({'success': False, 'error': 'Missing file or file selection'}), 400
            
            # Read the uploaded Excel file
            df = pd.read_excel(file)
            
            # Check if SKU column exists
            if 'SKU' not in df.columns:
                return jsonify({'success': False, 'error': 'Excel file must contain an "SKU" column'}), 400
            
            # Get all SKUs from the uploaded file
            search_skus = df['SKU'].dropna().astype(str).str.strip().unique().tolist()
            
            # Get inventory items from the selected file
            inventory_items = Inventory.query.filter_by(file_id=file_id).all()
            
            # Create a dictionary for quick lookup
            inventory_dict = {item.sku: item for item in inventory_items}
            
            # Separate found and not found SKUs
            found = []
            not_found = []
            
            for sku in search_skus:
                if sku in inventory_dict:
                    item = inventory_dict[sku]
                    found.append({
                        'id': str(item.id),
                        'sku': item.sku,
                        'description': item.description,
                        'category': item.category,
                        'stock_level': item.stock_level,
                        'available_stock': item.available_stock,
                        'total_container_qty': item.total_container_qty,
                        'container_details': item.container_details,
                        'last_count_date': item.last_count_date.strftime('%Y-%m-%d') if item.last_count_date else None,
                        'kenneth_inventory': item.kenneth_inventory,
                        'buffer_qty': item.buffer_qty
                    })
                else:
                    not_found.append(sku)
            
            # Log activity
            log = ActivityLog(
                user_id=session['user_id'],
                action='BULK_SEARCH',
                details=f'Bulk searched {len(search_skus)} SKUs. Found: {len(found)}, Not found: {len(not_found)}'
            )
            db.session.add(log)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'found': found,
                'not_found': not_found,
                'total': len(search_skus)
            })
            
        except Exception as e:
            print(f"Bulk search error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================================
# COMPARE ROUTE
# ============================================================================

@app.route('/compare')
@login_required
@role_required(['admin', 'staff'])
@prevent_back_after_logout
def compare():
    sku = request.args.get('sku', '')
    file_id1 = request.args.get('file_id1')
    file_id2 = request.args.get('file_id2')
    
    # Get available files
    files = File.query.order_by(File.file_date.desc()).all()
    available_files = []
    for f in files:
        available_files.append({
            'id': str(f.id),
            'filename': f.filename,
            'file_date': f.file_date.strftime('%Y-%m-%d'),
            'display_date': f.file_date.strftime('%b %d, %Y'),
            'record_count': f.record_count
        })
    
    comparison_result = None
    
    if sku and file_id1 and file_id2 and len(available_files) >= 2:
        try:
            # Get data for first date
            item1 = Inventory.query.filter_by(file_id=file_id1, sku=sku).first()
            # Get data for second date
            item2 = Inventory.query.filter_by(file_id=file_id2, sku=sku).first()
            
            comparison_result = {
                'sku': sku,
                'date1': None,
                'date2': None,
                'difference': None,
                'trend': 'no_change'
            }
            
            if item1:
                comparison_result['date1'] = {
                    'file_date': item1.file_date.strftime('%Y-%m-%d') if item1.file_date else None,
                    'available_stock': item1.available_stock,
                    'kenneth_inventory': item1.kenneth_inventory,
                    'total_container_qty': item1.total_container_qty,
                    'container_details': item1.container_details,
                    'buffer_qty': item1.buffer_qty,
                    'stock_status': item1.stock_status,
                    'stock_level': item1.stock_level
                }
            
            if item2:
                comparison_result['date2'] = {
                    'file_date': item2.file_date.strftime('%Y-%m-%d') if item2.file_date else None,
                    'available_stock': item2.available_stock,
                    'kenneth_inventory': item2.kenneth_inventory,
                    'total_container_qty': item2.total_container_qty,
                    'container_details': item2.container_details,
                    'buffer_qty': item2.buffer_qty,
                    'stock_status': item2.stock_status,
                    'stock_level': item2.stock_level
                }
            
            if comparison_result['date1'] and comparison_result['date2']:
                diff = comparison_result['date2']['available_stock'] - comparison_result['date1']['available_stock']
                comparison_result['difference'] = diff
                if diff > 0:
                    comparison_result['trend'] = 'increase'
                elif diff < 0:
                    comparison_result['trend'] = 'decrease'
            
            # Log activity
            log = ActivityLog(
                user_id=session['user_id'],
                action='COMPARE_SKU',
                details=f'Compared SKU: {sku}'
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            print(f"Compare error: {e}")
            flash('Error comparing SKUs', 'danger')
    
    return render_template(
        'compare.html',
        title='Compare SKU',
        sku=sku,
        file_id1=file_id1,
        file_id2=file_id2,
        available_files=available_files,
        comparison_result=comparison_result
    )

# ============================================================================
# UPLOAD ROUTE
# ============================================================================

@app.route('/upload', methods=['GET', 'POST'])
@login_required
@role_required(['admin', 'staff'])
@prevent_back_after_logout
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'danger')
            return redirect(request.url)
        
        file = request.files['file']
        
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file.save(filepath)
            
            success, result = parse_excel_file(filepath, filename)
            
            if success:
                log = ActivityLog(
                    user_id=session['user_id'],
                    action='UPLOAD_FILE',
                    details=f'Uploaded file: {filename}. Records: {result["record_count"]}'
                )
                db.session.add(log)
                db.session.commit()
                
                flash(f'File uploaded successfully! {result["record_count"]} records processed.', 'success')
                return redirect(url_for('dashboard', file_id=result['file_id']))
            else:
                flash(f'Error processing file: {result}', 'danger')
        else:
            flash('Invalid file type. Please upload .xlsx or .xls files.', 'danger')
        
        return redirect(request.url)
    
    # Get recent uploads
    recent_files = File.query.order_by(File.file_date.desc()).limit(5).all()
    recent_uploads = []
    for f in recent_files:
        recent_uploads.append({
            'id': str(f.id),
            'filename': f.filename,
            'display_date': f.file_date.strftime('%b %d, %Y'),
            'record_count': f.record_count,
            'upload_date': f.uploaded_at.strftime('%Y-%m-%d %H:%M') if f.uploaded_at else None
        })
    
    return render_template('upload.html', title='Upload Stock', recent_uploads=recent_uploads)

def parse_excel_file(file_path, filename):
    """Parse Excel file and save to PostgreSQL"""
    try:
        import pandas as pd
        import numpy as np
        import re
        
        print(f"📊 Processing file: {filename}")
        print(f"📦 NumPy version: {np.__version__}")
        print(f"🐼 Pandas version: {pd.__version__}")
        
        # Extract date from filename
        date_match = re.search(r'CheckStockTempFile_(\d{2}-\d{2}-\d{2})', filename)
        if not date_match:
            return False, "Invalid filename format. Expected: CheckStockTempFile_MM-DD-YY.xlsx"
        
        file_date_str = date_match.group(1)
        file_date = datetime.strptime(file_date_str, '%m-%d-%y')
        
        # Read Excel file with error handling
        try:
            # Try with different engines to avoid compatibility issues
            df = pd.read_excel(file_path, engine='openpyxl')
        except Exception as e:
            try:
                # Fallback to default engine
                df = pd.read_excel(file_path)
            except Exception as e2:
                return False, f"Could not read Excel file: {str(e2)}"
        
        print(f"✅ Excel loaded: {len(df)} rows, {len(df.columns)} columns")
        
        # Required columns
        required_columns = [
            'SKU', 'LastCountDate', 'LastCount', 'TotalContainerQty',
            'ContainerDetails', 'Final Expected Count', "Kenneth's Inventory",
            'StockStatus', 'InventoryRemark', 'Description', 'Category',
            'BufferQty'
        ]
        
        # Check which columns are actually present
        missing_columns = []
        for col in required_columns:
            if col not in df.columns:
                missing_columns.append(col)
        
        if missing_columns:
            return False, f"Missing columns: {missing_columns}"
        
        # Create file record
        new_file = File(
            filename=filename,
            file_date=file_date,
            record_count=len(df),
            uploaded_by=session.get('username', 'system'),
            file_size=os.path.getsize(file_path)
        )
        db.session.add(new_file)
        db.session.flush()
        
        # Process rows with batch insert for better performance
        batch_size = 500
        items_to_insert = []
        
        for idx, row in df.iterrows():
            if pd.isna(row['SKU']) or str(row['SKU']).strip() == '':
                continue
            
            # Parse date
            last_count_date = None
            if not pd.isna(row.get('LastCountDate')):
                try:
                    if isinstance(row['LastCountDate'], datetime):
                        last_count_date = row['LastCountDate']
                    elif isinstance(row['LastCountDate'], str):
                        for fmt in ['%m/%d/%y', '%m/%d/%Y', '%Y-%m-%d']:
                            try:
                                last_count_date = datetime.strptime(row['LastCountDate'], fmt)
                                break
                            except:
                                continue
                except:
                    pass
            
            # Safe integer conversion
            def safe_int(val):
                try:
                    if pd.isna(val):
                        return 0
                    if isinstance(val, str):
                        val = val.replace(',', '').strip()
                        if val == '':
                            return 0
                    return int(float(val))
                except:
                    return 0
            
            inventory_item = Inventory(
                file_id=new_file.id,
                sku=str(row['SKU']).strip(),
                description=str(row.get('Description', '')).strip(),
                category=str(row.get('Category', '')).strip(),
                last_count_date=last_count_date,
                last_count=safe_int(row.get('LastCount')),
                total_container_qty=safe_int(row.get('TotalContainerQty', 0)),
                container_details=str(row.get('ContainerDetails', '')).strip(),
                final_expected_count=safe_int(row.get('Final Expected Count', 0)),
                kenneth_inventory=safe_int(row.get("Kenneth's Inventory", 0)),
                buffer_qty=safe_int(row.get('BufferQty', 0)),
                stock_status=str(row.get('StockStatus', 'Unknown')).strip(),
                inventory_remark=str(row.get('InventoryRemark', '')).strip(),
                file_date=file_date
            )
            
            items_to_insert.append(inventory_item)
            
            # Batch insert to avoid memory issues
            if len(items_to_insert) >= batch_size:
                db.session.bulk_save_objects(items_to_insert)
                items_to_insert = []
        
        # Insert remaining items
        if items_to_insert:
            db.session.bulk_save_objects(items_to_insert)
        
        db.session.commit()
        
        # Clean up uploaded file
        try:
            os.remove(file_path)
            print(f"✅ Temporary file deleted: {file_path}")
        except Exception as e:
            print(f"⚠️ Could not delete temp file: {e}")
        
        return True, {
            'file_id': str(new_file.id),
            'record_count': len(df),
            'file_date': file_date.strftime('%Y-%m-%d')
        }
        
    except ImportError as e:
        db.session.rollback()
        print(f"❌ Import error: {e}")
        return False, f"Missing required library: {str(e)}. Run: pip install pandas openpyxl"
        
    except Exception as e:
        db.session.rollback()
        import traceback
        print("❌ ERROR DETAILS:")
        print(traceback.format_exc())
        return False, f"Error processing file: {str(e)}"

# ============================================================================
# DELETE FILE ROUTE - VERIFIED WORKING
# ============================================================================
@app.route('/delete-file/<file_id>', methods=['POST'])
@login_required
@role_required(['admin'])
def delete_file(file_id):
    """Delete a file and all its associated inventory records"""
    try:
        # Find the file
        file = File.query.get(file_id)
        if not file:
            return jsonify({'success': False, 'error': 'File not found'}), 404
        
        # Get count for logging
        record_count = Inventory.query.filter_by(file_id=file_id).count()
        filename = file.filename
        
        # Delete the file (cascade will delete all inventory records)
        db.session.delete(file)
        db.session.commit()
        
        # Log the activity
        log = ActivityLog(
            user_id=session['user_id'],
            action='DELETE_FILE',
            details=f'Deleted file: {filename} with {record_count} records'
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Deleted {filename} with {record_count} records'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting file: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================================
# PRINT REQUEST ROUTES
# ============================================================================
@app.route('/print-request', methods=['GET'])
@login_required
def print_request_page():
    # Get user's requests
    my_requests = PrintRequest.query.filter_by(
        requested_by_id=session['user_id']
    ).order_by(PrintRequest.requested_at.desc()).all()
    
    # Initialize empty lists for admin views
    pending_requests = []
    approved_requests = []
    printed_requests = []
    completed_requests = []
    
    # Statistics
    stats = {
        'pending': 0,
        'approved': 0,
        'printed': 0,
        'completed': 0
    }
    
    # Admin views
    if session['role'] == 'admin':
        # Get all requests with different statuses
        pending_requests = PrintRequest.query.filter_by(
            status='pending'
        ).order_by(PrintRequest.requested_at.asc()).all()
        
        approved_requests = PrintRequest.query.filter_by(
            status='approved'
        ).order_by(PrintRequest.requested_at.desc()).all()
        
        printed_requests = PrintRequest.query.filter_by(
            status='printed'
        ).order_by(PrintRequest.printed_at.desc()).all()
        
        completed_requests = PrintRequest.query.filter_by(
            status='completed'
        ).order_by(PrintRequest.completed_at.desc()).limit(50).all()
        
        # Calculate statistics for admin dashboard
        stats = {
            'pending': len(pending_requests),
            'approved': len(approved_requests),
            'printed': len(printed_requests),
            'completed': len(completed_requests)
        }
    
    # Get available files for dashboard source
    files = File.query.order_by(File.file_date.desc()).all()
    available_files = [{
        'id': str(f.id),
        'display_date': f.file_date.strftime('%b %d, %Y'),
        'record_count': f.record_count
    } for f in files]
    
    # Get recent bulk searches for this user
    bulk_searches = ActivityLog.query.filter_by(
        user_id=session['user_id'],
        action='BULK_SEARCH'
    ).order_by(ActivityLog.timestamp.desc()).limit(10).all()
    
    bulk_searches_data = []
    for log in bulk_searches:
        # Parse details to extract counts
        import re
        match = re.search(r'Found: (\d+), Not found: (\d+)', log.details)
        if match:
            bulk_searches_data.append({
                'id': log.id,
                'date': log.timestamp.strftime('%Y-%m-%d %H:%M'),
                'found': match.group(1),
                'not_found': match.group(2),
                'skus': []  # You'd need to store actual SKUs if you want this feature
            })
    
    return render_template(
        'print_request.html',
        title='Print Requests',
        my_requests=my_requests,
        pending_requests=pending_requests,
        approved_requests=approved_requests,
        printed_requests=printed_requests,
        completed_requests=completed_requests,
        stats=stats,  # Now stats is defined!
        available_files=available_files,
        bulk_searches=bulk_searches_data
    )

@app.route('/api/print-request', methods=['POST'])
@login_required
def create_print_request():
    try:
        data = request.json
        skus = data.get('skus', [])
        notes = data.get('notes', '')
        source = data.get('source', 'manual')
        
        if not skus:
            return jsonify({'success': False, 'error': 'No SKUs provided'}), 400
        
        if len(skus) > 500:
            return jsonify({'success': False, 'error': 'Maximum 500 SKUs allowed'}), 400
        
        # Generate unique request ID
        today = datetime.utcnow().strftime('%Y%m%d')
        count = PrintRequest.query.filter(
            db.func.date(PrintRequest.requested_at) == datetime.utcnow().date()
        ).count() + 1
        request_id = f"PR-{today}-{count:04d}"
        
        # Format SKUs to ensure they have quantity
        formatted_skus = []
        for sku in skus:
            if isinstance(sku, dict):
                # Already has sku and qty
                formatted_skus.append({
                    'sku': sku.get('sku'),
                    'qty': sku.get('qty', 1)
                })
            else:
                # Just a string, add default quantity 1
                formatted_skus.append({
                    'sku': sku,
                    'qty': 1
                })
        
        # Create print request
        print_request = PrintRequest(
            request_id=request_id,
            requested_by=session['username'],
            requested_by_id=session['user_id'],
            requested_by_role=session['role'],
            sku_list=json.dumps(formatted_skus),
            sku_count=len(formatted_skus),
            notes=notes,
            source_type=source,
            status='pending'
        )
        
        # Auto-approve if requested by admin
        if session['role'] == 'admin':
            print_request.status = 'approved'
            print_request.approved_by = session['username']
            print_request.approved_at = datetime.utcnow()
        
        db.session.add(print_request)
        db.session.commit()
        
        # Log activity
        total_qty = sum(item['qty'] for item in formatted_skus)
        log = ActivityLog(
            user_id=session['user_id'],
            action='CREATE_PRINT_REQUEST',
            details=f'Created print request {request_id} with {len(formatted_skus)} items, total quantity {total_qty}'
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'request_id': request_id,
            'status': print_request.status
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error creating print request: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/print-request/<request_id>/approve', methods=['POST'])
@login_required
@role_required(['admin'])
def approve_print_request(request_id):
    try:
        print_request = PrintRequest.query.get(request_id)
        if not print_request:
            return jsonify({'success': False, 'error': 'Request not found'}), 404
        
        print_request.status = 'approved'
        print_request.approved_by = session['username']
        print_request.approved_at = datetime.utcnow()
        db.session.commit()
        
        log = ActivityLog(
            user_id=session['user_id'],
            action='APPROVE_PRINT_REQUEST',
            details=f'Approved print request {print_request.request_id}'
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/print-request/<request_id>/reject', methods=['POST'])
@login_required
@role_required(['admin'])
def reject_print_request(request_id):
    try:
        data = request.json or {}
        reason = data.get('reason', '')
        
        print_request = PrintRequest.query.get(request_id)
        if not print_request:
            return jsonify({'success': False, 'error': 'Request not found'}), 404
        
        print_request.status = 'rejected'
        print_request.notes = (print_request.notes or '') + f"\nRejected: {reason}".strip()
        db.session.commit()
        
        log = ActivityLog(
            user_id=session['user_id'],
            action='REJECT_PRINT_REQUEST',
            details=f'Rejected print request {print_request.request_id}'
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/print-request/<request_id>/complete', methods=['POST'])
@login_required
def complete_print_request(request_id):
    try:
        print_request = PrintRequest.query.get(request_id)
        if not print_request:
            return jsonify({'success': False, 'error': 'Request not found'}), 404
        
        # Only the requester or admin can mark as complete
        if print_request.requested_by_id != session['user_id'] and session['role'] != 'admin':
            return jsonify({'success': False, 'error': 'Permission denied'}), 403
        
        print_request.status = 'completed'
        print_request.completed_at = datetime.utcnow()
        db.session.commit()
        
        log = ActivityLog(
            user_id=session['user_id'],
            action='COMPLETE_PRINT_REQUEST',
            details=f'Completed print request {print_request.request_id}'
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/print-request/<request_id>/skus', methods=['GET'])
@login_required
def get_print_request_skus(request_id):
    """Get SKUs for a request with quantities"""
    try:
        print_request = PrintRequest.query.get(request_id)
        if not print_request:
            return jsonify({'success': False, 'error': 'Request not found'}), 404
        
        # Check permission
        if print_request.requested_by_id != session['user_id'] and session['role'] != 'admin':
            return jsonify({'success': False, 'error': 'Permission denied'}), 403
        
        skus = print_request.get_sku_list()
        
        return jsonify({'success': True, 'skus': skus, 'count': len(skus)})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/print-request/<request_id>/print', methods=['GET'])
@login_required
def print_request_view(request_id):
    try:
        print_request = PrintRequest.query.get(request_id)
        if not print_request:
            flash('Print request not found', 'danger')
            return redirect(url_for('print_request_page'))
        
        # Check permission
        if print_request.requested_by_id != session['user_id'] and session['role'] != 'admin':
            flash('Permission denied', 'danger')
            return redirect(url_for('print_request_page'))
        
        skus = json.loads(print_request.sku_list)
        
        return render_template(
            'print_view.html',
            title=f'Print Request {print_request.request_id}',
            request=print_request,
            skus=skus
        )
        
    except Exception as e:
        print(f"Print view error: {e}")
        flash('Error loading print request', 'danger')
        return redirect(url_for('print_request_page'))

# ============================================================================
# LOGS ROUTE
# ============================================================================

@app.route('/logs')
@login_required
@role_required(['admin'])
@prevent_back_after_logout
def view_logs():
    page = request.args.get('page', 1, type=int)
    per_page = app.config.get('LOGS_PER_PAGE', 30)
    
    try:
        total = ActivityLog.query.count()
        logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).offset((page-1)*per_page).limit(per_page).all()
        
        log_list = []
        for log in logs:
            log_list.append({
                'id': log.id,
                'user_id': log.user_id,
                'action': log.action,
                'details': log.details,
                'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S') if log.timestamp else None
            })
        
        pagination = {
            'logs': log_list,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page if total > 0 else 0
        }
    except Exception as e:
        print(f"Logs error: {e}")
        pagination = {'logs': [], 'total': 0, 'page': page, 'per_page': per_page, 'total_pages': 0}
    
    return render_template('logs.html', title='Activity Logs', logs=pagination['logs'], pagination=pagination)

# ============================================================================
# SETTINGS ROUTES - UPDATED WITH LOGO UPLOAD
# ============================================================================

@app.route('/settings', methods=['GET'])
@login_required
@role_required(['admin'])
@prevent_back_after_logout
def settings():
    # Get all users
    try:
        users_list = User.query.order_by(User.created_at.desc()).all()
        users = []
        for user in users_list:
            users.append({
                'id': str(user.id),
                'username': user.username,
                'role': user.role,
                'full_name': user.full_name or '',
                'created_at': user.created_at.strftime('%Y-%m-%d') if user.created_at else '',
                'last_login': user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else 'Never'
            })
    except Exception as e:
        print(f"Error loading users: {e}")
        users = []
    
    # Get current settings
    settings_obj = Settings.query.get(1) or Settings(id=1)
    
    settings_dict = {
        'system_name': settings_obj.system_name,
        'logo': settings_obj.logo_path,
        'primary_color': settings_obj.primary_color,
        'success_color': settings_obj.success_color,
        'warning_color': settings_obj.warning_color,
        'danger_color': settings_obj.danger_color
    }
    
    return render_template('settings.html', title='Settings', settings=settings_dict, users=users)

@app.route('/update-settings', methods=['POST'])
@login_required
@role_required(['admin'])
def update_settings():
    system_name = request.form.get('system_name')
    primary_color = request.form.get('primary_color')
    success_color = request.form.get('success_color')
    warning_color = request.form.get('warning_color')
    danger_color = request.form.get('danger_color')
    
    # Get or create settings
    settings = Settings.query.get(1)
    if not settings:
        settings = Settings(id=1)
        db.session.add(settings)
    
    # Update settings
    if system_name:
        settings.system_name = system_name
    if primary_color:
        settings.primary_color = primary_color
    if success_color:
        settings.success_color = success_color
    if warning_color:
        settings.warning_color = warning_color
    if danger_color:
        settings.danger_color = danger_color
    
    settings.updated_at = datetime.utcnow()
    
    # ✅ HANDLE LOGO UPLOAD
    if 'logo' in request.files:
        logo = request.files['logo']
        if logo and logo.filename:
            # Validate file type
            if allowed_logo_file(logo.filename):
                # Create filename with timestamp to avoid caching
                timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
                file_ext = logo.filename.rsplit('.', 1)[1].lower()
                filename = f'custom_logo_{timestamp}.{file_ext}'
                
                # Save the file
                logo_path = os.path.join(app.config['LOGO_UPLOAD_FOLDER'], filename)
                os.makedirs(app.config['LOGO_UPLOAD_FOLDER'], exist_ok=True)
                logo.save(logo_path)
                
                # Update settings with new logo path
                settings.logo_path = f'/static/images/{filename}'
                
                flash('Logo uploaded successfully!', 'success')
            else:
                flash('Invalid logo format. Use PNG, JPG, JPEG, GIF, or SVG.', 'warning')
    
    # Commit changes
    try:
        db.session.commit()
        
        # Log activity
        log = ActivityLog(
            user_id=session['user_id'],
            action='UPDATE_SETTINGS',
            details='Updated system settings'
        )
        db.session.add(log)
        db.session.commit()
        
        flash('Settings updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error saving settings: {str(e)}', 'danger')
        print(f"Settings error: {e}")
    
    return redirect(url_for('settings'))

@app.route('/create-user', methods=['POST'])
@login_required
@role_required(['admin'])
def create_user():
    username = request.form.get('username')
    password = request.form.get('password')
    role = request.form.get('role')
    email = request.form.get('email')
    full_name = request.form.get('full_name', username)
    
    if not username or not password or not role:
        flash('Username, password, and role are required', 'danger')
        return redirect(url_for('settings'))
    
    try:
        existing = User.query.filter_by(username=username).first()
        if existing:
            flash('Username already exists', 'danger')
            return redirect(url_for('settings'))
        
        new_user = User(
            username=username,
            password=User.hash_password(password),
            role=role,
            email=email,
            full_name=full_name
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        log = ActivityLog(
            user_id=session['user_id'],
            action='CREATE_USER',
            details=f'Created user: {username}'
        )
        db.session.add(log)
        db.session.commit()
        
        flash(f'User {username} created successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating user: {str(e)}', 'danger')
        print(f"Create user error: {e}")
    
    return redirect(url_for('settings'))

@app.route('/get-file-skus/<file_id>', methods=['GET'])
@login_required
def get_file_skus(file_id):
    """Get all SKUs from a specific file (for bulk search preview)"""
    try:
        skus = [item.sku for item in Inventory.query.filter_by(file_id=file_id).all()]
        return jsonify({'success': True, 'skus': skus})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    
# ============================================================================
# EXPORT API ROUTES - WITH SKU LISTS
# ============================================================================
@app.route('/api/export-requests/<status>', methods=['GET'])
@login_required
@role_required(['admin'])
def export_requests(status):
    """Export requests data for CSV download with quantities"""
    try:
        if status == 'pending':
            requests = PrintRequest.query.filter_by(status='pending').order_by(PrintRequest.requested_at.asc()).all()
        elif status == 'approved':
            requests = PrintRequest.query.filter_by(status='approved').order_by(PrintRequest.requested_at.desc()).all()
        elif status == 'printed':
            requests = PrintRequest.query.filter_by(status='printed').order_by(PrintRequest.printed_at.desc()).all()
        else:
            return jsonify({'success': False, 'error': 'Invalid status'}), 400
        
        request_list = []
        for req in requests:
            sku_list = req.get_sku_list()
            data = {
                'request_id': req.request_id,
                'requested_by': req.requested_by,
                'role': req.requested_by_role.upper(),
                'sku_count': req.sku_count,
                'sku_list': sku_list,
                'notes': req.notes or ''
            }
            
            if status == 'pending':
                data['date'] = req.requested_at.strftime('%Y-%m-%d %H:%M')
            elif status == 'approved':
                data['approved_by'] = req.approved_by or ''
                data['approved_date'] = req.approved_at.strftime('%Y-%m-%d %H:%M') if req.approved_at else ''
            elif status == 'printed':
                data['printed_by'] = req.printed_by or ''
                data['printed_at'] = req.printed_at.strftime('%Y-%m-%d %H:%M') if req.printed_at else ''
                data['download_count'] = req.download_count
            
            request_list.append(data)
        
        return jsonify({'success': True, 'requests': request_list})
        
    except Exception as e:
        print(f"Export error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    
@app.route('/api/print-request/<request_id>/details', methods=['GET'])
@login_required
def get_print_request_details(request_id):
    """Get details for a print request"""
    try:
        print_request = PrintRequest.query.get(request_id)
        if not print_request:
            return jsonify({'success': False, 'error': 'Request not found'}), 404
        
        # Check permission
        if print_request.requested_by_id != session['user_id'] and session['role'] != 'admin':
            return jsonify({'success': False, 'error': 'Permission denied'}), 403
        
        return jsonify({
            'success': True,
            'request_id': print_request.request_id,
            'requested_by': print_request.requested_by,
            'requested_by_role': print_request.requested_by_role,
            'requested_at': print_request.requested_at.strftime('%Y-%m-%d %H:%M'),
            'sku_count': print_request.sku_count,
            'notes': print_request.notes,
            'status': print_request.status
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found_error(error):
    flash('Page not found', 'warning')
    return redirect(url_for('dashboard'))

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    flash('An internal error occurred', 'danger')
    return redirect(url_for('dashboard'))

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    # For development only - use gunicorn in production
    app.run(debug=True, host='0.0.0.0', port=5000)