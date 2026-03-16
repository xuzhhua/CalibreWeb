"""
Calibre Web 管理系统 - 主应用
提供书籍管理、用户认证等功能
"""
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
import os
from datetime import datetime, timedelta
import json
import threading
import time
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler

# 加载环境变量
load_dotenv()

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI', 'sqlite:///calibre_web.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Calibre书库配置
app.config['CALIBRE_LIBRARY_PATH'] = os.environ.get('CALIBRE_LIBRARY_PATH', '')
app.config['USE_CALIBRE_DB'] = os.environ.get('USE_CALIBRE_DB', 'False').lower() == 'true'

# AI辅助功能配置
app.config['OLLAMA_BASE_URL'] = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
app.config['OLLAMA_MODEL'] = os.environ.get('OLLAMA_MODEL', 'qwen2.5:latest')
app.config['OLLAMA_TIMEOUT'] = int(os.environ.get('OLLAMA_TIMEOUT', '60'))
app.config['SEARXNG_BASE_URL'] = os.environ.get('SEARXNG_BASE_URL', 'http://localhost:8080')
app.config['SEARXNG_ENABLED'] = os.environ.get('SEARXNG_ENABLED', 'True').lower() == 'true'

db = SQLAlchemy(app)

# 确保上传文件夹存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 配置日志
logs_dir = 'logs'
os.makedirs(logs_dir, exist_ok=True)

# 创建导入失败日志记录器
import_logger = logging.getLogger('import_failures')
import_logger.setLevel(logging.INFO)

# 创建文件处理器（最大10MB，保留5个备份）
log_file = os.path.join(logs_dir, 'import_failures.log')
file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
file_handler.setLevel(logging.INFO)

# 设置日志格式
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
file_handler.setFormatter(log_formatter)

import_logger.addHandler(file_handler)

# 导入状态跟踪
import_status = {
    'running': False,
    'progress': 0,
    'total': 0,
    'imported': 0,
    'updated': 0,
    'skipped': 0,
    'failed': 0,
    'current_book': '',
    'start_time': None,
    'completed': False,
    'error': None,
    'acknowledged': False
}

# ==================== 数据库模型 ====================

class User(db.Model):
    """用户模型"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_approved = db.Column(db.Boolean, default=False)  # 是否通过审核
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'is_admin': self.is_admin,
            'is_approved': self.is_approved,
            'created_at': self.created_at.isoformat()
        }


class Book(db.Model):
    """书籍模型"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(200))
    publisher = db.Column(db.String(200))
    isbn = db.Column(db.String(20))
    publication_date = db.Column(db.Date)
    description = db.Column(db.Text)
    cover_image = db.Column(db.String(300))
    file_path = db.Column(db.String(500))
    file_format = db.Column(db.String(10))
    file_size = db.Column(db.Integer)
    language = db.Column(db.String(50))
    tags = db.Column(db.String(500))
    rating = db.Column(db.Float, default=0.0)
    calibre_id = db.Column(db.Integer, nullable=True, index=True)  # Calibre数据库中的书籍ID
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self, user_id=None):
        # 处理tags：确保空字符串或None返回空数组
        tags_list = []
        if self.tags and self.tags.strip():
            tags_list = [tag.strip() for tag in self.tags.split(',') if tag.strip()]
        
        result = {
            'id': self.id,
            'title': self.title,
            'author': self.author,
            'publisher': self.publisher,
            'isbn': self.isbn,
            'publication_date': self.publication_date.isoformat() if self.publication_date else None,
            'description': self.description,
            'cover_image': self.cover_image,
            'file_path': self.file_path,
            'file_format': self.file_format,
            'file_size': self.file_size,
            'language': self.language,
            'tags': tags_list,
            'rating': self.rating,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'is_favorite': False,  # 默认值
            'is_read': False  # 默认值
        }
        
        # 如果提供了user_id，查询用户相关状态
        if user_id:
            status = UserBookStatus.query.filter_by(user_id=user_id, book_id=self.id).first()
            if status:
                result['is_favorite'] = status.is_favorite
                result['is_read'] = status.is_read
        
        return result


class UserBookStatus(db.Model):
    """用户书籍状态表（收藏、已读等）"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    is_favorite = db.Column(db.Boolean, default=False)
    is_read = db.Column(db.Boolean, default=False)
    reading_progress = db.Column(db.Integer, default=0)  # 阅读进度百分比
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 唯一约束：一个用户对一本书只能有一条状态记录
    __table_args__ = (db.UniqueConstraint('user_id', 'book_id', name='unique_user_book'),)


# ==================== 装饰器 ====================

@app.before_request
def track_user_activity():
    """跟踪用户活动，用于自动补充任务的空闲检测"""
    # 排除静态文件和健康检查请求
    if request.path.startswith('/static/') or request.path == '/health':
        return
    
    # 排除自动补充相关的API（避免自动任务触发活动检测）
    if '/api/ai/auto-fill/' in request.path or '/api/ai/batch-progress/' in request.path:
        return
    
    # 更新最后活动时间
    update_last_activity()

def login_required(f):
    """需要登录的装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': '请先登录'}), 401
        user = db.session.get(User, session['user_id'])
        if not user:
            return jsonify({'error': '用户不存在'}), 401
        if not user.is_approved and not user.is_admin:
            return jsonify({'error': '账号待审核，请联系管理员'}), 403
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """需要管理员权限的装饰器（用于API）"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': '请先登录'}), 401
        user = db.session.get(User, session['user_id'])
        if not user or not user.is_admin:
            return jsonify({'error': '需要管理员权限'}), 403
        return f(*args, **kwargs)
    return decorated_function


def admin_page_required(f):
    """需要管理员权限的装饰器（用于HTML页面）"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        user = db.session.get(User, session['user_id'])
        if not user or not user.is_admin:
            flash('需要管理员权限才能访问此页面')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function


# ==================== 路由 ====================

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/login')
def login_page():
    """登录页面"""
    return render_template('login.html')


@app.route('/register')
def register_page():
    """注册页面"""
    return render_template('register.html')


@app.route('/dashboard')
@login_required
def dashboard():
    """仪表板"""
    return render_template('dashboard.html')


@app.route('/test')
@login_required
def test_dashboard():
    """测试页面"""
    return render_template('test_dashboard.html')


@app.route('/reader')
@login_required
def reader():
    """在线阅读器"""
    return render_template('reader.html')


@app.route('/calibre-diff')
@admin_page_required
def calibre_diff_page():
    """Calibre差异分析页面（仅管理员）"""
    return render_template('calibre_diff.html')


# ==================== API - 用户认证 ====================

@app.route('/api/register', methods=['POST'])
def api_register():
    """用户注册"""
    data = request.get_json()
    
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    
    if not all([username, email, password]):
        return jsonify({'error': '请提供完整信息'}), 400
    
    if User.query.filter_by(username=username).first():
        return jsonify({'error': '用户名已存在'}), 400
    
    if User.query.filter_by(email=email).first():
        return jsonify({'error': '邮箱已被注册'}), 400
    
    user = User(username=username, email=email)
    user.set_password(password)
    
    # 第一个用户自动成为管理员并通过审核
    if User.query.count() == 0:
        user.is_admin = True
        user.is_approved = True
    else:
        # 其他用户需要等待管理员审核
        user.is_admin = False
        user.is_approved = False
    
    db.session.add(user)
    db.session.commit()
    
    message = '注册成功！请等待管理员审核' if not user.is_approved else '注册成功'
    return jsonify({'message': message, 'user': user.to_dict(), 'needs_approval': not user.is_approved}), 201


@app.route('/api/login', methods=['POST'])
def api_login():
    """用户登录"""
    data = request.get_json()
    
    username = data.get('username')
    password = data.get('password')
    
    if not all([username, password]):
        return jsonify({'error': '请提供用户名和密码'}), 400
    
    user = User.query.filter_by(username=username).first()
    
    if not user or not user.check_password(password):
        return jsonify({'error': '用户名或密码错误'}), 401
    
    # 检查账号是否通过审核（管理员除外）
    if not user.is_approved and not user.is_admin:
        return jsonify({'error': '账号待审核，请联系管理员'}), 403
    
    session['user_id'] = user.id
    session['username'] = user.username
    session['is_admin'] = user.is_admin
    session.permanent = True
    
    return jsonify({'message': '登录成功', 'user': user.to_dict()}), 200


@app.route('/api/logout', methods=['POST'])
def api_logout():
    """用户登出"""
    session.clear()
    return jsonify({'message': '已退出登录'}), 200


@app.route('/api/current-user', methods=['GET'])
@login_required
def api_current_user():
    """获取当前用户信息"""
    user = db.session.get(User, session['user_id'])
    return jsonify(user.to_dict()), 200


# ==================== API - 用户管理（管理员） ====================

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def api_get_users():
    """获取所有用户列表（管理员）"""
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify({
        'users': [user.to_dict() for user in users],
        'total': len(users)
    }), 200


@app.route('/api/admin/users/<int:user_id>/approve', methods=['POST'])
@admin_required
def api_approve_user(user_id):
    """审核通过用户（管理员）"""
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    if user.is_admin:
        return jsonify({'error': '管理员无需审核'}), 400
    
    user.is_approved = True
    db.session.commit()
    
    return jsonify({'message': '用户已通过审核', 'user': user.to_dict()}), 200


@app.route('/api/admin/users/<int:user_id>/reject', methods=['POST'])
@admin_required
def api_reject_user(user_id):
    """拒绝用户（管理员）"""
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    if user.is_admin:
        return jsonify({'error': '不能拒绝管理员'}), 400
    
    user.is_approved = False
    db.session.commit()
    
    return jsonify({'message': '已取消用户审核', 'user': user.to_dict()}), 200


@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@admin_required
def api_delete_user(user_id):
    """删除用户（管理员）"""
    current_user = db.session.get(User, session['user_id'])
    user = db.session.get(User, user_id)
    
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    if user.id == current_user.id:
        return jsonify({'error': '不能删除自己'}), 400
    
    if user.is_admin:
        return jsonify({'error': '不能删除管理员'}), 400
    
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({'message': '用户已删除'}), 200


@app.route('/api/admin/users/<int:user_id>/set-admin', methods=['POST'])
@admin_required
def api_set_admin(user_id):
    """设置/取消管理员（管理员）"""
    current_user = db.session.get(User, session['user_id'])
    user = db.session.get(User, user_id)
    
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    if user.id == current_user.id:
        return jsonify({'error': '不能修改自己的管理员权限'}), 400
    
    data = request.get_json()
    is_admin = data.get('is_admin', False)
    
    user.is_admin = is_admin
    if is_admin:
        user.is_approved = True  # 管理员自动通过审核
    db.session.commit()
    
    return jsonify({'message': f'已{"设置为" if is_admin else "取消"}管理员', 'user': user.to_dict()}), 200


# ==================== API - 书籍管理 ====================

@app.route('/api/books', methods=['GET'])
@login_required
def api_get_books():
    """获取书籍列表（支持搜索、分页和过滤）"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '')
        filter_type = request.args.get('filter', '')  # all, favorites, read
        
        if app.debug:
            print(f"[DEBUG] API调用 - page:{page}, per_page:{per_page}, search:{search}, filter:{filter_type}")
        
        query = Book.query
        
        # 根据过滤类型进行筛选
        if filter_type == 'favorites':
            # 获取当前用户收藏的书籍
            query = query.join(UserBookStatus, (UserBookStatus.book_id == Book.id) & 
                              (UserBookStatus.user_id == session.get('user_id')) & 
                              (UserBookStatus.is_favorite == True))
        elif filter_type == 'read':
            # 获取当前用户已读的书籍
            query = query.join(UserBookStatus, (UserBookStatus.book_id == Book.id) & 
                              (UserBookStatus.user_id == session.get('user_id')) & 
                              (UserBookStatus.is_read == True))
        
        if search:
            search_filter = f'%{search}%'
            query = query.filter(
                db.or_(
                    Book.title.like(search_filter),
                    Book.author.like(search_filter),
                    Book.publisher.like(search_filter),
                    Book.isbn.like(search_filter),
                    Book.tags.like(search_filter)
                )
            )
        
        query = query.order_by(Book.created_at.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        user_id = session.get('user_id')
        if app.debug:
            print(f"[DEBUG] 查询结果 - total:{pagination.total}, items:{len(pagination.items)}, user_id:{user_id}")
        
        return jsonify({
            'books': [book.to_dict(user_id) for book in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page,
            'per_page': per_page
        }), 200
    except Exception as e:
        print(f"[ERROR] API错误: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/books/<int:book_id>', methods=['GET'])
@login_required
def api_get_book(book_id):
    """获取单本书籍详情"""
    book = db.session.get(Book, book_id)
    if not book:
        return jsonify({'error': '书籍不存在'}), 404
    user_id = session.get('user_id')
    return jsonify(book.to_dict(user_id)), 200


@app.route('/api/books', methods=['POST'])
@admin_required
def api_create_book():
    """创建新书籍（仅管理员）"""
    data = request.get_json()
    
    title = data.get('title')
    if not title:
        return jsonify({'error': '书名不能为空'}), 400
    
    book = Book(
        title=title,
        author=data.get('author'),
        publisher=data.get('publisher'),
        isbn=data.get('isbn'),
        description=data.get('description'),
        language=data.get('language', '中文'),
        tags=','.join(data.get('tags', [])) if isinstance(data.get('tags'), list) else data.get('tags', ''),
        rating=data.get('rating', 0.0)
    )
    
    # 处理出版日期
    if data.get('publication_date'):
        try:
            book.publication_date = datetime.strptime(data['publication_date'], '%Y-%m-%d').date()
        except ValueError:
            pass
    
    db.session.add(book)
    db.session.commit()
    
    return jsonify({'message': '书籍创建成功', 'book': book.to_dict()}), 201


@app.route('/api/books/<int:book_id>', methods=['PUT'])
@admin_required
def api_update_book(book_id):
    """更新书籍信息（仅管理员）"""
    book = db.session.get(Book, book_id)
    if not book:
        return jsonify({'error': '书籍不存在'}), 404
    data = request.get_json()
    
    if 'title' in data:
        book.title = data['title']
    if 'author' in data:
        book.author = data['author']
    if 'publisher' in data:
        book.publisher = data['publisher']
    if 'isbn' in data:
        book.isbn = data['isbn']
    if 'description' in data:
        book.description = data['description']
    if 'language' in data:
        book.language = data['language']
    if 'rating' in data:
        book.rating = data['rating']
    if 'tags' in data:
        book.tags = ','.join(data['tags']) if isinstance(data['tags'], list) else data['tags']
    
    if 'publication_date' in data:
        try:
            book.publication_date = datetime.strptime(data['publication_date'], '%Y-%m-%d').date()
        except (ValueError, TypeError):
            pass
    
    book.updated_at = datetime.utcnow()
    db.session.commit()
    
    # 同步更新到Calibre数据库
    calibre_updated = update_calibre_metadata(book)
    
    # 根据Calibre同步结果构造提示消息
    if calibre_updated:
        message = '书籍更新成功，已同步到Calibre数据库'
    else:
        message = '书籍更新成功，但未能同步到Calibre数据库（可能该书籍不存在于Calibre中）'
        app.logger.warning(f"书籍 {book.title} (ID: {book_id}) 更新成功，但Calibre同步失败")
    
    response_data = {
        'message': message,
        'book': book.to_dict(),
        'calibre_synced': calibre_updated
    }
    
    return jsonify(response_data), 200


@app.route('/api/books/<int:book_id>', methods=['DELETE'])
@admin_required
def api_delete_book(book_id):
    """删除书籍（仅管理员）"""
    book = db.session.get(Book, book_id)
    if not book:
        return jsonify({'error': '书籍不存在'}), 404
    
    # 删除关联文件
    if book.file_path and os.path.exists(book.file_path):
        try:
            os.remove(book.file_path)
        except Exception as e:
            print(f"删除文件失败: {e}")
    
    if book.cover_image and os.path.exists(book.cover_image):
        try:
            os.remove(book.cover_image)
        except Exception as e:
            print(f"删除封面失败: {e}")
    
    db.session.delete(book)
    db.session.commit()
    
    return jsonify({'message': '书籍删除成功'}), 200


@app.route('/api/upload-book-file/<int:book_id>', methods=['POST'])
@login_required
def api_upload_book_file(book_id):
    """上传书籍文件"""
    book = db.session.get(Book, book_id)
    if not book:
        return jsonify({'error': '书籍不存在'}), 404
    
    if 'file' not in request.files:
        return jsonify({'error': '没有文件上传'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400
    
    # 保存文件
    filename = secure_filename(f"{book.id}_{file.filename}")
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)
    
    # 更新书籍信息
    book.file_path = file_path
    book.file_format = os.path.splitext(filename)[1][1:].upper()
    book.file_size = os.path.getsize(file_path)
    db.session.commit()
    
    return jsonify({'message': '文件上传成功', 'book': book.to_dict()}), 200


@app.route('/api/books/<int:book_id>/favorite', methods=['POST'])
@login_required
def api_toggle_favorite(book_id):
    """切换书籍收藏状态"""
    book = db.session.get(Book, book_id)
    if not book:
        return jsonify({'error': '书籍不存在'}), 404
    
    user_id = session.get('user_id')
    status = UserBookStatus.query.filter_by(user_id=user_id, book_id=book_id).first()
    
    if status:
        status.is_favorite = not status.is_favorite
    else:
        status = UserBookStatus(user_id=user_id, book_id=book_id, is_favorite=True)
        db.session.add(status)
    
    db.session.commit()
    return jsonify({'is_favorite': status.is_favorite}), 200


@app.route('/api/books/<int:book_id>/mark-read', methods=['POST'])
@login_required
def api_toggle_read(book_id):
    """切换书籍已读状态"""
    book = db.session.get(Book, book_id)
    if not book:
        return jsonify({'error': '书籍不存在'}), 404
    
    user_id = session.get('user_id')
    status = UserBookStatus.query.filter_by(user_id=user_id, book_id=book_id).first()
    
    if status:
        status.is_read = not status.is_read
    else:
        status = UserBookStatus(user_id=user_id, book_id=book_id, is_read=True)
        db.session.add(status)
    
    db.session.commit()
    return jsonify({'is_read': status.is_read}), 200


@app.route('/api/books/stats', methods=['GET'])
@login_required
def api_books_stats():
    """获取书籍统计信息"""
    total_books = Book.query.count()
    total_users = User.query.count()
    
    # 按语言统计
    books_by_language = db.session.query(
        Book.language, db.func.count(Book.id)
    ).group_by(Book.language).all()
    
    # 将None转换为"未知"，确保所有键都是字符串
    language_stats = {
        (lang if lang is not None else '未知'): count 
        for lang, count in books_by_language
    }
    
    return jsonify({
        'total_books': total_books,
        'total_users': total_users,
        'books_by_language': language_stats
    }), 200


@app.route('/api/books/<int:book_id>/cover', methods=['GET'])
@login_required
def api_get_book_cover(book_id):
    """获取书籍封面图片"""
    book = db.session.get(Book, book_id)
    if not book:
        return generate_default_cover("未知书籍")
    
    # 如果有封面路径且文件存在，返回实际封面
    if book.cover_image and os.path.exists(book.cover_image):
        try:
            return send_file(book.cover_image, mimetype='image/jpeg')
        except Exception as e:
            print(f"发送封面文件失败: {e}")
            return generate_default_cover(book.title or "无标题")
    
    # 否则返回默认封面
    return generate_default_cover(book.title or "无标题")


def generate_default_cover(title):
    """生成默认SVG封面"""
    # 截取标题前20个字符
    display_title = title[:20] + '...' if len(title) > 20 else title
    
    svg = f'''<svg width="400" height="600" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#e8dcc8;stop-opacity:1" />
                <stop offset="100%" style="stop-color:#d4c4b0;stop-opacity:1" />
            </linearGradient>
        </defs>
        <rect width="400" height="600" fill="url(#grad)"/>
        <rect x="20" y="20" width="360" height="560" fill="none" stroke="#a89880" stroke-width="2" rx="5"/>
        <text x="200" y="280" font-family="Arial, sans-serif" font-size="24" fill="#6b5d4f" text-anchor="middle" font-weight="bold">{display_title}</text>
        <text x="200" y="320" font-family="Arial, sans-serif" font-size="18" fill="#8b7a6a" text-anchor="middle">📚</text>
        <text x="200" y="360" font-family="Arial, sans-serif" font-size="14" fill="#9b8a7a" text-anchor="middle">暂无封面</text>
    </svg>'''
    
    from flask import Response
    return Response(svg, mimetype='image/svg+xml')


@app.route('/api/books/<int:book_id>/debug', methods=['GET'])
@login_required
def api_debug_book(book_id):
    """调试：查看书籍的完整信息"""
    book = db.session.get(Book, book_id)
    if not book:
        return jsonify({'error': '书籍不存在'}), 404
    
    return jsonify({
        'id': book.id,
        'title': book.title,
        'cover_image': book.cover_image,
        'cover_exists': os.path.exists(book.cover_image) if book.cover_image else False,
        'file_path': book.file_path,
        'file_exists': os.path.exists(book.file_path) if book.file_path else False
    }), 200


@app.route('/api/books/<int:book_id>/download', methods=['GET'])
@login_required
def api_download_book(book_id):
    """下载书籍文件"""
    book = db.session.get(Book, book_id)
    if not book:
        return jsonify({'error': '书籍不存在'}), 404
    
    if not book.file_path:
        return jsonify({'error': '没有可下载的文件'}), 404
    
    if not os.path.exists(book.file_path):
        return jsonify({'error': '文件不存在'}), 404
    
    try:
        # 生成安全的文件名
        filename = f"{book.title} - {book.author or 'Unknown'}.{book.file_format.lower()}"
        filename = secure_filename(filename)
        
        return send_file(
            book.file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/octet-stream'
        )
    except Exception as e:
        print(f"下载文件失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/books/<int:book_id>/preview', methods=['GET'])
@login_required
def api_preview_book(book_id):
    """预览书籍文件（在线阅读）"""
    book = db.session.get(Book, book_id)
    if not book:
        return jsonify({'error': '书籍不存在'}), 404
    
    if not book.file_path:
        return jsonify({'error': '没有可预览的文件'}), 404
    
    if not os.path.exists(book.file_path):
        return jsonify({'error': '文件不存在'}), 404
    
    try:
        # 根据文件类型设置不同的MIME类型
        mime_types = {
            'PDF': 'application/pdf',
            'EPUB': 'application/epub+zip',
            'MOBI': 'application/x-mobipocket-ebook',
            'TXT': 'text/plain; charset=utf-8',
            'AZW3': 'application/vnd.amazon.ebook'
        }
        
        mime_type = mime_types.get(book.file_format.upper(), 'application/octet-stream')
        
        return send_file(
            book.file_path,
            mimetype=mime_type,
            as_attachment=False
        )
    except Exception as e:
        print(f"预览文件失败: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== 封面搜索和下载功能 ====================

def search_and_download_cover(book, query):
    """搜索并下载书籍封面
    
    Args:
        book: Book对象
        query: 搜索关键词
    
    Returns:
        tuple: (success: bool, cover_path: str or None, message: str)
    """
    try:
        import requests
        from urllib.parse import quote
        
        # 1. 使用SearXNG搜索图片
        if not app.config.get('SEARXNG_ENABLED') or not app.config.get('SEARXNG_BASE_URL'):
            return False, None, "SearXNG未配置"
        
        # 搜索封面图片
        search_url = f"{app.config['SEARXNG_BASE_URL']}/search"
        params = {
            'q': f"{query} 封面 book cover",
            'format': 'json',
            'categories': 'images',
            'language': 'zh-CN'
        }
        
        response = requests.get(search_url, params=params, timeout=10)
        if response.status_code != 200:
            return False, None, "搜索请求失败"
        
        results = response.json().get('results', [])
        if not results:
            return False, None, "未找到封面图片"
        
        # 2. 尝试下载前3张图片，选择第一张成功下载的
        for i, result in enumerate(results[:3]):
            img_url = result.get('img_src') or result.get('url')
            if not img_url:
                continue
            
            try:
                # 下载图片
                img_response = requests.get(img_url, timeout=10, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                
                if img_response.status_code != 200:
                    continue
                
                # 检查是否为图片
                content_type = img_response.headers.get('Content-Type', '')
                if 'image' not in content_type:
                    continue
                
                # 确定文件扩展名
                if 'jpeg' in content_type or 'jpg' in content_type:
                    ext = '.jpg'
                elif 'png' in content_type:
                    ext = '.png'
                elif 'webp' in content_type:
                    ext = '.webp'
                else:
                    ext = '.jpg'  # 默认
                
                # 保存封面
                import uuid
                filename = f"cover_{book.id}_{uuid.uuid4().hex[:8]}{ext}"
                cover_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                with open(cover_path, 'wb') as f:
                    f.write(img_response.content)
                
                # 验证文件大小（至少1KB，最多10MB）
                file_size = os.path.getsize(cover_path)
                if file_size < 1024 or file_size > 10 * 1024 * 1024:
                    os.remove(cover_path)
                    continue
                
                app.logger.info(f"成功下载封面: {book.title}, URL: {img_url}, Size: {file_size} bytes")
                return True, cover_path, "封面下载成功"
                
            except Exception as e:
                app.logger.warning(f"下载封面失败 (尝试 {i+1}/3): {str(e)}")
                continue
        
        return False, None, "所有封面下载尝试均失败"
        
    except Exception as e:
        app.logger.error(f"搜索封面异常: {str(e)}")
        return False, None, f"搜索封面异常: {str(e)}"


def update_calibre_cover(book):
    """更新Calibre数据库中的书籍封面
    
    Args:
        book: Book对象，包含封面路径
    
    Returns:
        bool: 更新是否成功
    """
    if not book.cover_image or not book.calibre_id:
        return False
    
    calibre_db = get_calibre_db_path()
    if not calibre_db:
        return False
    
    try:
        # 获取Calibre库路径
        library_path = app.config.get('CALIBRE_LIBRARY_PATH')
        if not library_path:
            return False
        
        import sqlite3
        conn = sqlite3.connect(calibre_db)
        
        # 定义title_sort函数（Calibre的触发器需要）
        def title_sort(title):
            """Calibre的title_sort函数实现"""
            if not title:
                return ''
            # 移除开头的冠词
            for prefix in ['The ', 'A ', 'An ', 'the ', 'a ', 'an ']:
                if title.startswith(prefix):
                    return title[len(prefix):] + ', ' + prefix.strip()
            return title
        
        # 注册title_sort函数
        conn.create_function("title_sort", 1, title_sort)
        
        cursor = conn.cursor()
        
        # 获取书籍路径
        cursor.execute("SELECT path FROM books WHERE id = ?", (book.calibre_id,))
        result = cursor.fetchone()
        if not result:
            conn.close()
            return False
        
        book_path = result[0]
        calibre_book_dir = os.path.join(library_path, book_path)
        
        if not os.path.exists(calibre_book_dir):
            conn.close()
            return False
        
        # 复制封面到Calibre目录
        cover_dest = os.path.join(calibre_book_dir, 'cover.jpg')
        
        import shutil
        shutil.copy2(book.cover_image, cover_dest)
        
        # 更新数据库has_cover标记
        cursor.execute("UPDATE books SET has_cover = 1 WHERE id = ?", (book.calibre_id,))
        
        conn.commit()
        conn.close()
        
        app.logger.info(f"成功更新Calibre封面: {book.title} (calibre_id: {book.calibre_id})")
        return True
        
    except Exception as e:
        app.logger.error(f"更新Calibre封面失败: {str(e)}")
        return False


# ==================== Calibre数据库集成 ====================

def get_calibre_db_path():
    """获取Calibre数据库路径"""
    library_path = app.config['CALIBRE_LIBRARY_PATH']
    if library_path and os.path.exists(library_path):
        metadata_db = os.path.join(library_path, 'metadata.db')
        if os.path.exists(metadata_db):
            return metadata_db
    return None


def update_calibre_metadata(book):
    """更新Calibre数据库中的书籍元数据
    
    Args:
        book: Book对象，包含要更新的信息
    
    Returns:
        bool: 更新是否成功
    """
    calibre_db = get_calibre_db_path()
    if not calibre_db:
        return False
    
    try:
        import sqlite3
        conn = sqlite3.connect(calibre_db)
        
        # 注册Calibre需要的自定义函数
        def title_sort(title):
            """Calibre的title_sort函数实现"""
            if not title:
                return ''
            # 移除开头的冠词
            for prefix in ['The ', 'A ', 'An ', 'the ', 'a ', 'an ']:
                if title.startswith(prefix):
                    return title[len(prefix):] + ', ' + prefix.strip()
            return title
        
        conn.create_function("title_sort", 1, title_sort)
        
        cursor = conn.cursor()
        
        calibre_book_id = None
        match_method = None  # 记录匹配方式
        
        # 优先使用calibre_id字段查找（最准确的方式）
        if book.calibre_id:
            cursor.execute("SELECT id, title FROM books WHERE id = ?", (book.calibre_id,))
            result = cursor.fetchone()
            if result:
                calibre_book_id = result[0]
                match_method = 'calibre_id'
                app.logger.info(f"通过calibre_id匹配到书籍: {result[1]} (ID: {calibre_book_id})")
            else:
                # calibre_id存在但在Calibre数据库中找不到，可能已被删除
                app.logger.warning(f"书籍的calibre_id={book.calibre_id}在Calibre数据库中不存在，可能已被删除")
                book.calibre_id = None  # 清除无效的calibre_id
                db.session.commit()
        
        # 如果没有calibre_id或查找失败，尝试根据书名和作者查找
        if not calibre_book_id:
            cursor.execute("""
                SELECT b.id FROM books b
                LEFT JOIN books_authors_link bal ON b.id = bal.book
                LEFT JOIN authors a ON bal.author = a.id
                WHERE b.title = ? AND (a.name = ? OR (a.name IS NULL AND ? IS NULL))
                LIMIT 1
            """, (book.title, book.author, book.author))
            
            result = cursor.fetchone()
            if not result:
                conn.close()
                app.logger.warning(f"在Calibre数据库中找不到书籍: {book.title} (作者: {book.author})")
                app.logger.warning(f"提示: 该书籍可能是在本系统中手动添加的，不存在于Calibre数据库中")
                return False
            
            calibre_book_id = result[0]
            match_method = 'title_author'
            app.logger.info(f"通过书名和作者匹配到书籍 (ID: {calibre_book_id})")
            
            # 保存calibre_id到本地数据库，以便下次直接使用calibre_id匹配（更快更准确）
            if not book.calibre_id:
                book.calibre_id = calibre_book_id
                db.session.commit()
                app.logger.info(f"已保存calibre_id={calibre_book_id}到本地数据库，下次将直接使用ID匹配")
        
        # 更新书名
        if book.title:
            cursor.execute("UPDATE books SET title = ? WHERE id = ?", (book.title, calibre_book_id))
        
        # 更新作者
        if book.author:
            # 查找或创建作者
            cursor.execute("SELECT id FROM authors WHERE name = ?", (book.author,))
            author_row = cursor.fetchone()
            if author_row:
                author_id = author_row[0]
            else:
                cursor.execute("INSERT INTO authors (name, sort) VALUES (?, ?)", (book.author, book.author))
                author_id = cursor.lastrowid
            
            # 更新books_authors_link
            cursor.execute("DELETE FROM books_authors_link WHERE book = ?", (calibre_book_id,))
            cursor.execute("INSERT INTO books_authors_link (book, author) VALUES (?, ?)", (calibre_book_id, author_id))
        
        # 更新出版社
        if book.publisher:
            cursor.execute("SELECT id FROM publishers WHERE name = ?", (book.publisher,))
            publisher_row = cursor.fetchone()
            if publisher_row:
                publisher_id = publisher_row[0]
            else:
                cursor.execute("INSERT INTO publishers (name, sort) VALUES (?, ?)", (book.publisher, book.publisher))
                publisher_id = cursor.lastrowid
            
            cursor.execute("DELETE FROM books_publishers_link WHERE book = ?", (calibre_book_id,))
            cursor.execute("INSERT INTO books_publishers_link (book, publisher) VALUES (?, ?)", (calibre_book_id, publisher_id))
        
        # 更新ISBN
        if book.isbn:
            cursor.execute("DELETE FROM identifiers WHERE book = ? AND type = 'isbn'", (calibre_book_id,))
            cursor.execute("INSERT INTO identifiers (book, type, val) VALUES (?, 'isbn', ?)", (calibre_book_id, book.isbn))
        
        # 更新简介（包括清空操作）
        cursor.execute("DELETE FROM comments WHERE book = ?", (calibre_book_id,))
        if book.description:
            cursor.execute("INSERT INTO comments (book, text) VALUES (?, ?)", (calibre_book_id, book.description))
        
        # 更新标签（包括清空操作）
        cursor.execute("DELETE FROM books_tags_link WHERE book = ?", (calibre_book_id,))
        if book.tags:
            tags_list = [t.strip() for t in book.tags.split(',') if t.strip()]
            for tag_name in tags_list:
                cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
                tag_row = cursor.fetchone()
                if tag_row:
                    tag_id = tag_row[0]
                else:
                    cursor.execute("INSERT INTO tags (name) VALUES (?)", (tag_name,))
                    tag_id = cursor.lastrowid
                cursor.execute("INSERT INTO books_tags_link (book, tag) VALUES (?, ?)", (calibre_book_id, tag_id))
        
        # 更新语言
        if book.language:
            cursor.execute("SELECT id FROM languages WHERE lang_code = ?", (book.language.lower(),))
            lang_row = cursor.fetchone()
            if lang_row:
                lang_id = lang_row[0]
            else:
                cursor.execute("INSERT INTO languages (lang_code) VALUES (?)", (book.language.lower(),))
                lang_id = cursor.lastrowid
            
            cursor.execute("DELETE FROM books_languages_link WHERE book = ?", (calibre_book_id,))
            cursor.execute("INSERT INTO books_languages_link (book, lang_code) VALUES (?, ?)", (calibre_book_id, lang_id))
        
        # 更新评分
        if book.rating:
            calibre_rating = int(book.rating * 2)  # 转换为0-10
            cursor.execute("SELECT id FROM ratings WHERE rating = ?", (calibre_rating,))
            rating_row = cursor.fetchone()
            if rating_row:
                rating_id = rating_row[0]
            else:
                cursor.execute("INSERT INTO ratings (rating) VALUES (?)", (calibre_rating,))
                rating_id = cursor.lastrowid
            
            cursor.execute("DELETE FROM books_ratings_link WHERE book = ?", (calibre_book_id,))
            cursor.execute("INSERT INTO books_ratings_link (book, rating) VALUES (?, ?)", (calibre_book_id, rating_id))
        
        # 更新出版日期
        if book.publication_date:
            cursor.execute("UPDATE books SET pubdate = ? WHERE id = ?", 
                         (book.publication_date.strftime('%Y-%m-%d 00:00:00+00:00'), calibre_book_id))
        
        # 更新时间戳
        from datetime import datetime
        cursor.execute("UPDATE books SET last_modified = ? WHERE id = ?", 
                     (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S+00:00'), calibre_book_id))
        
        conn.commit()
        conn.close()
        
        app.logger.info(f"✓ 成功更新Calibre数据库 - 书籍: {book.title}, calibre_id: {calibre_book_id}, 匹配方式: {match_method}")
        return True
        
    except Exception as e:
        app.logger.error(f"✗ 更新Calibre数据库失败 - 书籍: {book.title}, 错误: {str(e)}")
        import traceback
        app.logger.error(f"详细错误信息: {traceback.format_exc()}")
        try:
            if 'conn' in locals():
                conn.close()
        except:
            pass
        return False


def import_from_calibre(limit=1000, offset=0):
    """从Calibre数据库导入书籍
    
    Args:
        limit: 每次导入的最大数量，默认1000本
        offset: 跳过的记录数，用于分批导入
    """
    calibre_db = get_calibre_db_path()
    if not calibre_db:
        print("未找到Calibre数据库，跳过导入")
        return {'imported': 0, 'total': 0, 'skipped': 0, 'updated': 0}
    
    print(f"正在从Calibre数据库导入: {calibre_db}")
    
    try:
        import sqlite3
        conn = sqlite3.connect(calibre_db)
        cursor = conn.cursor()
        
        # 首先测试数据库连接
        cursor.execute("SELECT COUNT(*) FROM books")
        total_books = cursor.fetchone()[0]
        print(f"Calibre书库中共有 {total_books} 本书")
        print(f"本次导入: 从第{offset}本开始，最多导入{limit}本")
        
        # 查询Calibre数据库中的书籍（兼容Calibre实际结构，添加分页）
        cursor.execute("""
            SELECT b.id, b.title, b.path, b.timestamp
            FROM books b
            LIMIT ? OFFSET ?
        """, (limit, offset))
        
        books = cursor.fetchall()
        imported_count = 0
        skipped_count = 0
        updated_count = 0
        failed_count = 0
        
        for idx, book_data in enumerate(books, 1):
            if idx % 100 == 0:
                print(f"处理进度: {idx}/{len(books)}")
            
            try:
                calibre_id, title, path, timestamp = book_data
                
                # 分别查询作者
                cursor.execute("""
                    SELECT a.name FROM authors a
                    JOIN books_authors_link bal ON a.id = bal.author
                    WHERE bal.book = ?
                    LIMIT 1
                """, (calibre_id,))
                author_row = cursor.fetchone()
                author = author_row[0] if author_row else None
                
                # 检查是否已存在（根据书名和作者）
                existing = Book.query.filter_by(title=title, author=author).first()
                
                if existing:
                    # 检查完整性并更新缺失信息
                    updated = update_book_completeness(existing, calibre_id, cursor, path)
                    if updated:
                        updated_count += 1
                    else:
                        skipped_count += 1
                    continue
                
                # 分别查询出版社
                cursor.execute("""
                    SELECT p.name FROM publishers p
                    JOIN books_publishers_link bpl ON p.id = bpl.publisher
                    WHERE bpl.book = ?
                    LIMIT 1
                """, (calibre_id,))
                publisher_row = cursor.fetchone()
                publisher = publisher_row[0] if publisher_row else None
                
                # 分别查询ISBN
                cursor.execute("""
                    SELECT val FROM identifiers
                    WHERE book = ? AND type = 'isbn'
                    LIMIT 1
                """, (calibre_id,))
                isbn_row = cursor.fetchone()
                isbn = isbn_row[0] if isbn_row else None
                
                # 查询标签
                cursor.execute("""
                    SELECT t.name FROM tags t
                    JOIN books_tags_link btl ON t.id = btl.tag
                    WHERE btl.book = ?
                """, (calibre_id,))
                tags = [row[0] for row in cursor.fetchall()]
                
                # 查询评分
                cursor.execute("""
                    SELECT r.rating FROM ratings r
                    JOIN books_ratings_link brl ON r.id = brl.rating
                    WHERE brl.book = ?
                    LIMIT 1
                """, (calibre_id,))
                rating_row = cursor.fetchone()
                rating = (rating_row[0] / 2.0) if rating_row and rating_row[0] else 0.0  # Calibre用0-10，转为0-5
                
                # 查询简介
                cursor.execute("""
                    SELECT text FROM comments
                    WHERE book = ?
                    LIMIT 1
                """, (calibre_id,))
                desc_row = cursor.fetchone()
                description = desc_row[0] if desc_row else None
                
                # 创建新书籍记录
                book = Book(
                    title=title,
                    author=author,
                    publisher=publisher,
                    isbn=isbn,
                    description=description,
                    rating=rating,
                    tags=','.join(tags) if tags else '',
                    calibre_id=calibre_id  # 保存Calibre书籍ID
                )
                
                # 设置文件路径（相对于Calibre书库）
                if path:
                    book_dir = os.path.join(app.config['CALIBRE_LIBRARY_PATH'], path)
                    if os.path.exists(book_dir):
                        # 查找封面图片
                        cover_path = os.path.join(book_dir, 'cover.jpg')
                        if os.path.exists(cover_path):
                            book.cover_image = cover_path
                        if idx <= 3:  # 只打印前3本的调试信息
                            print(f"  找到封面: {cover_path}")
                    else:
                        if idx <= 3:
                            print(f"  封面不存在: {cover_path}")
                    
                    # 查找电子书文件
                    for file in os.listdir(book_dir):
                        if file.lower().endswith(('.epub', '.pdf', '.mobi', '.azw3', '.txt')):
                            book.file_path = os.path.join(book_dir, file)
                            book.file_format = os.path.splitext(file)[1][1:].upper()
                            book.file_size = os.path.getsize(book.file_path)
                            break
                
                db.session.add(book)
                imported_count += 1
            
            except Exception as book_error:
                failed_count += 1
                error_msg = f"书籍: {title if 'title' in locals() else 'Unknown'} (Calibre ID: {calibre_id if 'calibre_id' in locals() else 'Unknown'})"
                error_detail = f"错误: {str(book_error)}"
                print(f"  导入失败 - {error_msg} - {error_detail}")
                import_logger.error(f"{error_msg} | {error_detail}")
                # 继续处理下一本书
                continue
        
        db.session.commit()
        conn.close()
        result = {
            'imported': imported_count,
            'total': total_books,
            'skipped': skipped_count,
            'updated': updated_count,
            'failed': failed_count,
            'processed': len(books)
        }
        if failed_count > 0:
            print(f"本次导入完成: 新增{imported_count}本，更新{updated_count}本，跳过{skipped_count}本，失败{failed_count}本，共处理{len(books)}本")
            print(f"失败详情已记录到日志文件: {log_file}")
        else:
            print(f"本次导入完成: 新增{imported_count}本，更新{updated_count}本，跳过{skipped_count}本，共处理{len(books)}本")
        return result
        
    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
        import_logger.error(f"数据库连接错误: {str(e)}")
        return {'imported': 0, 'total': 0, 'skipped': 0, 'updated': 0, 'failed': 0, 'error': str(e)}
    except Exception as e:
        print(f"从Calibre导入失败: {e}")
        import_logger.error(f"导入过程异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return {'imported': 0, 'total': 0, 'skipped': 0, 'updated': 0, 'failed': 0, 'error': str(e)}


def update_book_completeness(book, calibre_id, cursor, path):
    """检查并更新书籍信息的完整性"""
    updated = False
    
    # 保存calibre_id
    if not book.calibre_id:
        book.calibre_id = calibre_id
        updated = True
    
    # 检查封面
    if not book.cover_image or not os.path.exists(book.cover_image):
        if path:
            book_dir = os.path.join(app.config['CALIBRE_LIBRARY_PATH'], path)
            if os.path.exists(book_dir):
                cover_path = os.path.join(book_dir, 'cover.jpg')
                if os.path.exists(cover_path):
                    book.cover_image = cover_path
                    updated = True
                    print(f"更新封面: {book.title}")
    
    # 检查文件路径
    if not book.file_path or not os.path.exists(book.file_path):
        if path:
            book_dir = os.path.join(app.config['CALIBRE_LIBRARY_PATH'], path)
            if os.path.exists(book_dir):
                for file in os.listdir(book_dir):
                    if file.lower().endswith(('.epub', '.pdf', '.mobi', '.azw3', '.txt')):
                        book.file_path = os.path.join(book_dir, file)
                        book.file_format = os.path.splitext(file)[1][1:].upper()
                        book.file_size = os.path.getsize(book.file_path)
                        updated = True
                        print(f"更新文件: {book.title}")
                        break
    
    # 检查其他缺失信息
    if not book.description:
        cursor.execute("""
            SELECT text FROM comments
            WHERE book = ?
            LIMIT 1
        """, (calibre_id,))
        desc_row = cursor.fetchone()
        if desc_row:
            book.description = desc_row[0]
            updated = True
    
    if not book.tags:
        cursor.execute("""
            SELECT t.name FROM tags t
            JOIN books_tags_link btl ON t.id = btl.tag
            WHERE btl.book = ?
        """, (calibre_id,))
        tags = [row[0] for row in cursor.fetchall()]
        if tags:
            book.tags = ','.join(tags)
            updated = True
    
    if updated:
        book.updated_at = datetime.utcnow()
        db.session.commit()
    
    return updated


def batch_check_completeness():
    """批量检查所有书籍的完整性"""
    calibre_db = get_calibre_db_path()
    if not calibre_db:
        print("未找到Calibre数据库，跳过完整性检查")
        return 0
    
    try:
        import sqlite3
        conn = sqlite3.connect(calibre_db)
        cursor = conn.cursor()
        
        # 获取所有需要检查的书籍
        books = Book.query.all()
        updated_count = 0
        
        print(f"开始检查 {len(books)} 本书的完整性...")
        
        for book in books:
            # 查找对应的Calibre记录
            cursor.execute("""
                SELECT b.id, b.path FROM books b
                WHERE b.title = ?
                LIMIT 1
            """, (book.title,))
            
            calibre_row = cursor.fetchone()
            if calibre_row:
                calibre_id, path = calibre_row
                if update_book_completeness(book, calibre_id, cursor, path):
                    updated_count += 1
        
        conn.close()
        print(f"完整性检查完成：更新了 {updated_count} 本书")
        return updated_count
        
    except Exception as e:
        print(f"完整性检查失败: {e}")
        import traceback
        traceback.print_exc()
        return 0



def background_import_task():
    """后台导入任务 - 智能增量导入"""
    global import_status
    
    import_status['running'] = True
    import_status['start_time'] = datetime.utcnow()
    import_status['completed'] = False
    import_status['error'] = None
    import_status['acknowledged'] = False  # 重置确认状态，允许显示新的导入进度
    
    try:
        with app.app_context():
            BATCH_SIZE = 500
            offset = 0
            total_imported = 0
            total_updated = 0
            total_skipped = 0
            total_failed = 0
            
            # 先检查数据库中已有书籍数量
            existing_count = Book.query.count()
            print(f"当前数据库已有 {existing_count} 本书")
            
            # 获取Calibre书库总数
            calibre_db = get_calibre_db_path()
            if calibre_db:
                import sqlite3
                conn = sqlite3.connect(calibre_db)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM books")
                calibre_total = cursor.fetchone()[0]
                conn.close()
                print(f"Calibre书库共有 {calibre_total} 本书")
            else:
                calibre_total = 0
            
            # 根据数据库和Calibre书库的情况决定导入策略
            if existing_count == 0:
                print("数据库为空，开始完整导入...")
            elif existing_count < calibre_total:
                print(f"数据库已有 {existing_count} 本书，Calibre有 {calibre_total} 本书")
                print(f"开始检查所有 {calibre_total} 本书，跳过已存在的，导入新增的...")
                print("注意：由于书籍顺序可能不同，需要从头开始检查所有书籍")
            else:
                print(f"数据库已有 {existing_count} 本书，与Calibre书库数量相同或更多")
                print("开始检查所有书籍，确保完整性...")
            
            # 注意：不使用offset跳过，因为数据库中的书籍顺序可能与Calibre不同
            # 必须从头开始检查所有书籍，依靠书名+作者判断是否已存在
            offset = 0
            
            while True:
                import_status['current_book'] = f'处理第 {offset} - {offset + BATCH_SIZE} 本'
                
                result = import_from_calibre(limit=BATCH_SIZE, offset=offset)
                
                if 'error' in result:
                    import_status['error'] = result['error']
                    break
                
                total_imported += result['imported']
                total_updated += result['updated']
                total_skipped += result['skipped']
                total_failed += result.get('failed', 0)
                
                import_status['imported'] = total_imported
                import_status['updated'] = total_updated
                import_status['skipped'] = total_skipped
                import_status['failed'] = total_failed
                import_status['total'] = result['total']
                import_status['progress'] = offset + result['processed']
                
                # 如果这批没处理到足够的书，说明已经全部导入完毕
                if result['processed'] < BATCH_SIZE:
                    break
                
                offset += result['processed']
                
                # 每批之间稍微休息，避免占用太多CPU
                time.sleep(0.5)
            
            # 导入完成后检查书籍完整性（只要数据库中有书就进行检查）
            current_book_count = Book.query.count()
            if current_book_count > 0:
                print(f"导入完成，开始检查所有 {current_book_count} 本书的完整性...")
                batch_updated = batch_check_completeness()
                # 注意：batch_check_completeness可能会重复检查一些在导入时已经更新的书籍
                # 但为了确保所有书籍都被检查，这是可以接受的
                total_updated += batch_updated
                import_status['updated'] = total_updated
                print(f"完整性检查完成：批量检查额外更新了 {batch_updated} 本书")
            else:
                print("数据库中没有书籍，跳过完整性检查")
            
            import_status['completed'] = True
            if total_failed > 0:
                print(f"后台导入完成：新增{total_imported}本，更新{total_updated}本，跳过{total_skipped}本，失败{total_failed}本")
                print(f"失败详情请查看日志文件: {log_file}")
            else:
                print(f"后台导入完成：新增{total_imported}本，更新{total_updated}本，跳过{total_skipped}本")
            
    except Exception as e:
        import_status['error'] = str(e)
        print(f"后台导入失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        import_status['running'] = False


def import_from_calibre(limit=1000, offset=0):
    """从Calibre数据库导入书籍
    
    Args:
        limit: 每次导入的最大数量，默认1000本
        offset: 跳过的记录数，用于分批导入
    """
    calibre_db = get_calibre_db_path()
    if not calibre_db:
        print("未找到Calibre数据库，跳过导入")
        return {'imported': 0, 'total': 0, 'skipped': 0, 'updated': 0, 'processed': 0}
    
    print(f"正在从Calibre数据库导入: {calibre_db}")
    
    try:
        import sqlite3
        conn = sqlite3.connect(calibre_db)
        cursor = conn.cursor()
        
        # 首先测试数据库连接
        cursor.execute("SELECT COUNT(*) FROM books")
        total_books = cursor.fetchone()[0]
        print(f"Calibre书库中共有 {total_books} 本书")
        print(f"本次导入: 从第{offset}本开始，最多导入{limit}本")
        
        # 查询Calibre数据库中的书籍（兼容Calibre实际结构，添加分页）
        cursor.execute("""
            SELECT b.id, b.title, b.path, b.timestamp
            FROM books b
            LIMIT ? OFFSET ?
        """, (limit, offset))
        
        books = cursor.fetchall()
        imported_count = 0
        skipped_count = 0
        updated_count = 0
        failed_books = []  # 记录失败的图书
        skipped_books = []  # 记录跳过的图书
        
        for idx, book_data in enumerate(books, 1):
            if idx % 100 == 0:
                print(f"处理进度: {idx}/{len(books)}")
            
            try:
                calibre_id, title, path, timestamp = book_data
            
                # 分别查询作者
                cursor.execute("""
                    SELECT a.name FROM authors a
                    JOIN books_authors_link bal ON a.id = bal.author
                    WHERE bal.book = ?
                    LIMIT 1
                """, (calibre_id,))
                author_row = cursor.fetchone()
                author = author_row[0] if author_row else None
                
                # 分别查询出版社
                cursor.execute("""
                    SELECT p.name FROM publishers p
                    JOIN books_publishers_link bpl ON p.id = bpl.publisher
                    WHERE bpl.book = ?
                    LIMIT 1
                """, (calibre_id,))
                publisher_row = cursor.fetchone()
                publisher = publisher_row[0] if publisher_row else None
                
                # 分别查询ISBN
                cursor.execute("""
                    SELECT val FROM identifiers
                    WHERE book = ? AND type = 'isbn'
                    LIMIT 1
                """, (calibre_id,))
                isbn_row = cursor.fetchone()
                isbn = isbn_row[0] if isbn_row else None
                
                # 检查是否已存在
                existing = Book.query.filter_by(title=title, author=author).first()
                if existing:
                    # 检查并更新已存在书籍的完整性
                    updated = update_book_completeness(existing, calibre_id, cursor, path)
                    if updated:
                        updated_count += 1
                        skipped_books.append({
                            'calibre_id': calibre_id,
                            'title': title,
                            'author': author if author else '未知作者',
                            'reason': '已存在但已更新完整性'
                        })
                    else:
                        skipped_count += 1
                        skipped_books.append({
                            'calibre_id': calibre_id,
                            'title': title,
                            'author': author if author else '未知作者',
                            'reason': '数据库中已存在'
                        })
                    continue
                
                # 查询标签
                cursor.execute("""
                    SELECT t.name FROM tags t
                    JOIN books_tags_link btl ON t.id = btl.tag
                    WHERE btl.book = ?
                """, (calibre_id,))
                tags = [row[0] for row in cursor.fetchall()]
                
                # 查询评分
                cursor.execute("""
                    SELECT r.rating FROM ratings r
                    JOIN books_ratings_link brl ON r.id = brl.rating
                    WHERE brl.book = ?
                    LIMIT 1
                """, (calibre_id,))
                rating_row = cursor.fetchone()
                rating = (rating_row[0] / 2.0) if rating_row and rating_row[0] else 0.0  # Calibre用0-10，转为0-5
                
                # 查询简介
                cursor.execute("""
                    SELECT text FROM comments
                    WHERE book = ?
                    LIMIT 1
                """, (calibre_id,))
                desc_row = cursor.fetchone()
                description = desc_row[0] if desc_row else None
                
                # 创建新书籍记录
                book = Book(
                    title=title,
                    author=author,
                    publisher=publisher,
                    isbn=isbn,
                    description=description,
                    rating=rating,
                    tags=','.join(tags) if tags else ''
                )
                
                # 设置文件路径（相对于Calibre书库）
                if path:
                    book_dir = os.path.join(app.config['CALIBRE_LIBRARY_PATH'], path)
                    if os.path.exists(book_dir):
                        # 查找封面图片
                        cover_path = os.path.join(book_dir, 'cover.jpg')
                        if os.path.exists(cover_path):
                            book.cover_image = cover_path
                            if idx <= 3:  # 只打印前3本的调试信息
                                print(f"  找到封面: {cover_path}")
                        else:
                            if idx <= 3:
                                print(f"  封面不存在: {cover_path}")
                        
                        # 查找电子书文件
                        for file in os.listdir(book_dir):
                            if file.lower().endswith(('.epub', '.pdf', '.mobi', '.azw3', '.txt')):
                                book.file_path = os.path.join(book_dir, file)
                                book.file_format = os.path.splitext(file)[1][1:].upper()
                                book.file_size = os.path.getsize(book.file_path)
                                break
                
                db.session.add(book)
                imported_count += 1
                
            except Exception as e:
                # 记录导入失败的图书信息
                failed_books.append({
                    'calibre_id': calibre_id if 'calibre_id' in locals() else 'unknown',
                    'title': title if 'title' in locals() else 'unknown',
                    'author': author if 'author' in locals() else 'unknown',
                    'error': str(e)
                })
                print(f"[ERROR] 导入失败 - Calibre ID: {calibre_id if 'calibre_id' in locals() else 'unknown'}, "
                      f"书名: {title if 'title' in locals() else 'unknown'}, "
                      f"作者: {author if 'author' in locals() else 'unknown'}, "
                      f"错误: {str(e)}")
        
        db.session.commit()
        conn.close()
        
        # 输出跳过图书的汇总信息并记录到日志
        if skipped_books:
            print("\n" + "=" * 80)
            print(f"跳过的图书汇总 (共 {len(skipped_books)} 本):")
            print("=" * 80)
            for idx, book_info in enumerate(skipped_books, 1):
                info_msg = f"{idx}. Calibre ID: {book_info['calibre_id']} | 书名: {book_info['title']} | 作者: {book_info['author']} | 原因: {book_info['reason']}"
                print(info_msg)
                import_logger.info(f"[跳过] {info_msg}")
            print("=" * 80 + "\n")
        
        # 输出失败图书的汇总信息
        if failed_books:
            print("\n" + "=" * 80)
            print(f"导入失败的图书汇总 (共 {len(failed_books)} 本):")
            print("=" * 80)
            for idx, book_info in enumerate(failed_books, 1):
                print(f"{idx}. Calibre ID: {book_info['calibre_id']}")
                print(f"   书名: {book_info['title']}")
                print(f"   作者: {book_info['author']}")
                print(f"   错误: {book_info['error']}")
                print("-" * 80)
            print("=" * 80 + "\n")
        
        result = {
            'imported': imported_count,
            'total': total_books,
            'skipped': skipped_count,
            'updated': updated_count,
            'processed': len(books),
            'failed': len(failed_books)
        }
        print(f"本次导入完成: 新增{imported_count}本，更新{updated_count}本，跳过{skipped_count}本，失败{len(failed_books)}本，共处理{len(books)}本")
        return result
        
    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
        return {'imported': 0, 'total': 0, 'skipped': 0, 'updated': 0, 'processed': 0, 'failed': 0, 'error': str(e)}
    except Exception as e:
        print(f"从Calibre导入失败: {e}")
        import traceback
        traceback.print_exc()
        return {'imported': 0, 'total': 0, 'skipped': 0, 'updated': 0, 'processed': 0, 'failed': 0, 'error': str(e)}


@app.route('/api/calibre/import', methods=['POST'])
@admin_required
def api_import_calibre():
    """手动触发从Calibre导入（仅管理员）"""
    global import_status
    
    if import_status['running']:
        return jsonify({
            'error': '导入任务已在运行中',
            'status': import_status
        }), 400
    
    # 启动后台线程
    thread = threading.Thread(target=background_import_task, daemon=True)
    thread.start()
    
    return jsonify({
        'message': '后台导入已启动',
        'status': import_status
    }), 200


@app.route('/api/calibre/diff', methods=['GET'])
@admin_required
def api_calibre_diff():
    """分析本地数据库与Calibre数据库的差异（仅管理员）"""
    try:
        if app.debug:
            print("开始差异分析...")
        
        calibre_db = get_calibre_db_path()
        if not calibre_db:
            return jsonify({'error': '未找到Calibre数据库'}), 404
        
        import sqlite3
        conn = sqlite3.connect(calibre_db)
        cursor = conn.cursor()
        
        # 获取Calibre书籍总数和基本统计
        cursor.execute("SELECT COUNT(*) FROM books")
        calibre_total = cursor.fetchone()[0]
        
        if app.debug:
            print(f"Calibre书库共有 {calibre_total} 本书")
        
        # 获取本地书籍总数
        local_total = Book.query.count()
        
        if app.debug:
            print(f"本地数据库共有 {local_total} 本书，开始构建索引...")
        
        # 构建本地书籍字典（支持calibre_id和书名+作者两种查找方式）
        local_books = Book.query.all()
        local_dict_by_id = {}  # calibre_id -> book_info
        local_dict_by_key = {}  # (title, author) -> book_info
        local_keys = set()
        
        for book in local_books:
            book_info = {
                'id': book.id,
                'title': book.title,
                'author': book.author or '未知作者',
                'has_cover': bool(book.cover_image),
                'has_file': bool(book.file_path),
                'has_description': bool(book.description),
                'has_tags': bool(book.tags),
                'calibre_id': book.calibre_id
            }
            
            # 如果有calibre_id，建立ID索引
            if book.calibre_id:
                local_dict_by_id[book.calibre_id] = book_info
            
            # 同时建立书名+作者索引（作为备用匹配方式）
            key = (book.title, book.author or '')
            local_keys.add(key)
            local_dict_by_key[key] = book_info
        
        if app.debug:
            print(f"本地索引构建完成（ID索引: {len(local_dict_by_id)}, 书名索引: {len(local_dict_by_key)}），开始查询Calibre书库...")
        
        # 只查询Calibre中的书籍基本信息用于差异对比
        cursor.execute("""
            SELECT b.id, b.title, 
                   (SELECT a.name FROM authors a 
                    JOIN books_authors_link bal ON a.id = bal.author 
                    WHERE bal.book = b.id LIMIT 1) as author,
                   b.path
            FROM books b
        """)
        
        if app.debug:
            print("开始对比差异...")
        
        only_in_calibre = []
        only_in_local = []
        incomplete_books = []
        calibre_keys = set()
        matched_calibre_ids = set()  # 记录已匹配的calibre_id
        
        # 遍历Calibre书籍，优先使用calibre_id匹配
        for calibre_id, title, author, path in cursor.fetchall():
            key = (title, author or '')
            calibre_keys.add(key)
            
            local_info = None
            
            # 1. 优先使用calibre_id匹配
            if calibre_id in local_dict_by_id:
                local_info = local_dict_by_id[calibre_id]
                matched_calibre_ids.add(calibre_id)
            # 2. 如果ID匹配失败，尝试书名+作者匹配
            elif key in local_dict_by_key:
                local_info = local_dict_by_key[key]
                # 记录这个calibre_id，避免重复匹配
                if local_info.get('calibre_id'):
                    matched_calibre_ids.add(local_info['calibre_id'])
            
            if not local_info:
                # 只在Calibre中存在（待导入）
                only_in_calibre.append({
                    'calibre_id': calibre_id,
                    'title': title,
                    'author': author or '未知作者',
                    'path': path
                })
            else:
                # 检查是否信息不完整
                if not all([local_info['has_cover'], local_info['has_file'], 
                           local_info['has_description'], local_info['has_tags']]):
                    incomplete_books.append({
                        **local_info,
                        'calibre_id': calibre_id,
                        'calibre_path': path
                    })
        
        # 查找只在本地存在的书籍（Calibre中已删除或未关联）
        if app.debug:
            print("检查孤立书籍...")
        
        for key in local_keys:
            book_info = local_dict_by_key[key]
            # 检查这本书是否已通过ID或书名匹配到Calibre
            if key not in calibre_keys and book_info.get('calibre_id') not in matched_calibre_ids:
                only_in_local.append(book_info)
        
        conn.close()
        
        # 计算完整的书籍数量
        complete_count = local_total - len(incomplete_books) - len(only_in_local)
        
        if app.debug:
            print(f"差异分析完成: 仅在Calibre={len(only_in_calibre)}, 仅在本地={len(only_in_local)}, 不完整={len(incomplete_books)}")
        
        return jsonify({
            'summary': {
                'calibre_total': calibre_total,
                'local_total': local_total,
                'only_in_calibre': len(only_in_calibre),
                'only_in_local': len(only_in_local),
                'incomplete': len(incomplete_books),
                'complete': complete_count
            },
            'only_in_calibre': only_in_calibre[:100],  # 最多返回100条预览
            'only_in_local': only_in_local[:100],
            'incomplete_books': incomplete_books[:100],
            'has_more': {
                'only_in_calibre': len(only_in_calibre) > 100,
                'only_in_local': len(only_in_local) > 100,
                'incomplete': len(incomplete_books) > 100
            }
        }), 200
        
    except Exception as e:
        print(f"差异分析失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/calibre/import-selected', methods=['POST'])
@admin_required
def api_import_selected():
    """导入选定的书籍（仅管理员）"""
    global import_status
    
    if import_status['running']:
        return jsonify({
            'error': '导入任务已在运行中',
            'status': import_status
        }), 400
    
    data = request.get_json()
    action = data.get('action')  # 'import_new', 'update_incomplete', 'remove_orphaned'
    book_ids = data.get('book_ids', [])  # Calibre IDs 或 本地 IDs
    
    if not action:
        return jsonify({'error': '请指定操作类型'}), 400
    
    # 启动后台线程处理选定的操作
    def selective_import_task():
        global import_status
        import_status['running'] = True
        import_status['start_time'] = datetime.utcnow()
        import_status['completed'] = False
        import_status['error'] = None
        import_status['acknowledged'] = False
        
        try:
            with app.app_context():
                if action == 'import_new':
                    # 导入选定的新书
                    result = import_selected_books(book_ids)
                    import_status['imported'] = result.get('imported', 0)
                    import_status['failed'] = result.get('failed', 0)
                    
                elif action == 'update_incomplete':
                    # 更新不完整的书籍
                    result = update_selected_books(book_ids)
                    import_status['updated'] = result.get('updated', 0)
                    
                elif action == 'remove_orphaned':
                    # 删除孤立的书籍（只在本地有，Calibre中已删除）
                    result = remove_selected_books(book_ids)
                    import_status['skipped'] = result.get('removed', 0)
                
                import_status['completed'] = True
                print(f"选择性操作完成: {action}")
                
        except Exception as e:
            import_status['error'] = str(e)
            print(f"选择性操作失败: {e}")
            import traceback
            traceback.print_exc()
        finally:
            import_status['running'] = False
    
    thread = threading.Thread(target=selective_import_task, daemon=True)
    thread.start()
    
    return jsonify({
        'message': f'已启动{action}操作',
        'status': import_status
    }), 200


def import_selected_books(calibre_ids):
    """导入指定的Calibre书籍"""
    calibre_db = get_calibre_db_path()
    if not calibre_db:
        return {'imported': 0, 'failed': 0, 'error': '未找到Calibre数据库'}
    
    try:
        import sqlite3
        conn = sqlite3.connect(calibre_db)
        cursor = conn.cursor()
        
        imported = 0
        failed = 0
        
        for calibre_id in calibre_ids:
            try:
                # 查询书籍信息
                cursor.execute("""
                    SELECT b.id, b.title, b.path, b.timestamp
                    FROM books b
                    WHERE b.id = ?
                """, (calibre_id,))
                
                book_data = cursor.fetchone()
                if not book_data:
                    failed += 1
                    continue
                
                calibre_id, title, path, timestamp = book_data
                
                # 查询作者
                cursor.execute("""
                    SELECT a.name FROM authors a
                    JOIN books_authors_link bal ON a.id = bal.author
                    WHERE bal.book = ?
                    LIMIT 1
                """, (calibre_id,))
                author_row = cursor.fetchone()
                author = author_row[0] if author_row else None
                
                # 检查是否已存在
                existing = Book.query.filter_by(title=title, author=author).first()
                if existing:
                    continue
                
                # 查询其他信息
                cursor.execute("SELECT p.name FROM publishers p JOIN books_publishers_link bpl ON p.id = bpl.publisher WHERE bpl.book = ? LIMIT 1", (calibre_id,))
                publisher_row = cursor.fetchone()
                publisher = publisher_row[0] if publisher_row else None
                
                cursor.execute("SELECT val FROM identifiers WHERE book = ? AND type = 'isbn' LIMIT 1", (calibre_id,))
                isbn_row = cursor.fetchone()
                isbn = isbn_row[0] if isbn_row else None
                
                cursor.execute("SELECT t.name FROM tags t JOIN books_tags_link btl ON t.id = btl.tag WHERE btl.book = ?", (calibre_id,))
                tags = [row[0] for row in cursor.fetchall()]
                
                cursor.execute("SELECT r.rating FROM ratings r JOIN books_ratings_link brl ON r.id = brl.rating WHERE brl.book = ? LIMIT 1", (calibre_id,))
                rating_row = cursor.fetchone()
                rating = (rating_row[0] / 2.0) if rating_row and rating_row[0] else 0.0
                
                cursor.execute("SELECT text FROM comments WHERE book = ? LIMIT 1", (calibre_id,))
                desc_row = cursor.fetchone()
                description = desc_row[0] if desc_row else None
                
                # 创建书籍
                book = Book(
                    title=title,
                    author=author,
                    publisher=publisher,
                    isbn=isbn,
                    description=description,
                    rating=rating,
                    tags=','.join(tags) if tags else ''
                )
                
                # 设置文件路径
                if path:
                    book_dir = os.path.join(app.config['CALIBRE_LIBRARY_PATH'], path)
                    if os.path.exists(book_dir):
                        cover_path = os.path.join(book_dir, 'cover.jpg')
                        if os.path.exists(cover_path):
                            book.cover_image = cover_path
                        
                        for file in os.listdir(book_dir):
                            if file.lower().endswith(('.epub', '.pdf', '.mobi', '.azw3', '.txt')):
                                book.file_path = os.path.join(book_dir, file)
                                book.file_format = os.path.splitext(file)[1][1:].upper()
                                book.file_size = os.path.getsize(book.file_path)
                                break
                
                db.session.add(book)
                imported += 1
                
            except Exception as e:
                failed += 1
                print(f"导入书籍 {calibre_id} 失败: {e}")
        
        db.session.commit()
        conn.close()
        
        return {'imported': imported, 'failed': failed}
        
    except Exception as e:
        print(f"导入选定书籍失败: {e}")
        return {'imported': 0, 'failed': len(calibre_ids), 'error': str(e)}


def update_selected_books(local_ids):
    """更新指定的本地书籍"""
    calibre_db = get_calibre_db_path()
    if not calibre_db:
        return {'updated': 0, 'error': '未找到Calibre数据库'}
    
    try:
        import sqlite3
        conn = sqlite3.connect(calibre_db)
        cursor = conn.cursor()
        
        updated = 0
        
        for local_id in local_ids:
            book = db.session.get(Book, local_id)
            if not book:
                continue
            
            # 查找对应的Calibre记录
            cursor.execute("""
                SELECT b.id, b.path FROM books b
                WHERE b.title = ?
                LIMIT 1
            """, (book.title,))
            
            calibre_row = cursor.fetchone()
            if calibre_row:
                calibre_id, path = calibre_row
                if update_book_completeness(book, calibre_id, cursor, path):
                    updated += 1
        
        conn.close()
        return {'updated': updated}
        
    except Exception as e:
        print(f"更新选定书籍失败: {e}")
        return {'updated': 0, 'error': str(e)}


def remove_selected_books(local_ids):
    """删除指定的本地书籍"""
    try:
        removed = 0
        for local_id in local_ids:
            book = db.session.get(Book, local_id)
            if book:
                db.session.delete(book)
                removed += 1
        
        db.session.commit()
        return {'removed': removed}
        
    except Exception as e:
        print(f"删除选定书籍失败: {e}")
        return {'removed': 0, 'error': str(e)}


@app.route('/api/calibre/import-status', methods=['GET'])
@login_required
def api_import_status():
    """获取导入状态"""
    return jsonify(import_status), 200


@app.route('/api/calibre/acknowledge-import', methods=['POST'])
@login_required
def api_acknowledge_import():
    """确认导入状态，关闭进度提示"""
    global import_status
    import_status['acknowledged'] = True
    return jsonify({'success': True}), 200


@app.route('/api/calibre/config', methods=['GET'])
@login_required
def api_get_calibre_config():
    """获取Calibre配置"""
    return jsonify({
        'library_path': app.config['CALIBRE_LIBRARY_PATH'],
        'use_calibre_db': app.config['USE_CALIBRE_DB'],
        'db_exists': get_calibre_db_path() is not None
    }), 200


@app.route('/api/calibre/config', methods=['POST'])
@admin_required
def api_set_calibre_config():
    """设置Calibre配置（仅管理员）"""
    data = request.get_json()
    library_path = data.get('library_path', '')
    
    if library_path and not os.path.exists(library_path):
        return jsonify({'error': '指定的路径不存在'}), 400
    
    app.config['CALIBRE_LIBRARY_PATH'] = library_path
    
    # 可以选择写入配置文件或环境变量
    return jsonify({
        'message': 'Calibre书库路径已更新',
        'library_path': library_path
    }), 200


# ==================== 初始化数据库 ====================

def init_db():
    """初始化数据库"""
    with app.app_context():
        db.create_all()
        print("数据库初始化完成")
        
        # 如果配置了Calibre书库，提示用户可以手动导入
        if app.config['CALIBRE_LIBRARY_PATH']:
            calibre_db = get_calibre_db_path()
            if calibre_db:
                print("检测到Calibre书库配置")
                print("提示：可通过以下方式导入书籍：")
                print("  1. 访问 /calibre-diff 页面进行差异分析和选择性导入（推荐）")
                print("  2. 调用 /api/calibre/import 接口进行全量导入")
            else:
                print("提示：未找到Calibre数据库文件")


# ==================== AI辅助功能 ====================

@app.route('/api/ai/search-book-info', methods=['POST'])
@login_required
def api_ai_search_book_info():
    """使用AI搜索并填充书籍信息"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        
        if not query:
            return jsonify({'error': '请提供搜索关键词'}), 400
        
        # 检查配置
        if not app.config['OLLAMA_BASE_URL']:
            return jsonify({'error': 'Ollama未配置'}), 500
        
        import requests
        
        # 1. 如果启用了SearXNG，先搜索网络信息
        search_results = ''
        if app.config['SEARXNG_ENABLED'] and app.config['SEARXNG_BASE_URL']:
            try:
                searxng_url = f"{app.config['SEARXNG_BASE_URL']}/search"
                params = {
                    'q': f"{query} 书籍信息 作者 出版社 ISBN",
                    'format': 'json',
                    'categories': 'general',
                    'language': 'zh-CN'
                }
                resp = requests.get(searxng_url, params=params, timeout=10)
                if resp.status_code == 200:
                    results = resp.json().get('results', [])[:5]
                    search_results = '\n\n'.join([
                        f"标题: {r.get('title', '')}\n内容: {r.get('content', '')}\nURL: {r.get('url', '')}"
                        for r in results
                    ])
                    if app.debug:
                        print(f"SearXNG搜索结果: {len(results)} 条")
            except Exception as e:
                if app.debug:
                    print(f"SearXNG搜索失败: {e}")
        
        # 2. 构建Ollama提示词
        system_prompt = """你是一个图书信息助手。根据提供的信息，以JSON格式返回书籍的详细信息。
        
返回的JSON格式必须严格遵循以下结构：
{
    "title": "书名",
    "author": "作者名",
    "publisher": "出版社",
    "isbn": "ISBN号（如果有）",
    "publication_date": "出版日期（YYYY-MM-DD格式）",
    "description": "书籍简介（200-500字）",
    "language": "语言（如：中文、英文）",
    "tags": "标签1,标签2,标签3（用逗号分隔）"
}

注意事项：
1. 所有字段都是可选的，如果不确定就留空字符串
2. publication_date必须是YYYY-MM-DD格式，如果只知道年份就写YYYY-01-01
3. description应该包含书籍的主要内容、特色、读者群体等
4. tags应该包括书籍类型、主题、适用领域等
5. 只返回JSON，不要有其他文字说明"""
        
        user_prompt = f"书籍查询: {query}"
        if search_results:
            user_prompt += f"\n\n网络搜索结果:\n{search_results}"
        
        # 3. 调用Ollama API
        ollama_url = f"{app.config['OLLAMA_BASE_URL']}/api/generate"
        payload = {
            'model': app.config['OLLAMA_MODEL'],
            'prompt': f"{system_prompt}\n\n{user_prompt}",
            'stream': False,
            'options': {
                'temperature': 0.7,
                'top_p': 0.9,
            }
        }
        
        if app.debug:
            print(f"调用Ollama: {app.config['OLLAMA_MODEL']}")
        
        response = requests.post(
            ollama_url,
            json=payload,
            timeout=app.config['OLLAMA_TIMEOUT']
        )
        
        if response.status_code != 200:
            return jsonify({'error': f'Ollama API错误: {response.text}'}), 500
        
        result = response.json()
        ai_response = result.get('response', '')
        
        if app.debug:
            print(f"AI响应: {ai_response[:200]}...")
        
        # 4. 解析JSON响应
        try:
            # 尝试提取JSON（可能被包裹在代码块中）
            import re
            json_match = re.search(r'\{[\s\S]*\}', ai_response)
            if json_match:
                book_info = json.loads(json_match.group())
            else:
                book_info = json.loads(ai_response)
            
            # 验证和清理数据
            cleaned_info = {
                'title': book_info.get('title', '').strip(),
                'author': book_info.get('author', '').strip(),
                'publisher': book_info.get('publisher', '').strip(),
                'isbn': book_info.get('isbn', '').strip(),
                'publication_date': book_info.get('publication_date', '').strip(),
                'description': book_info.get('description', '').strip(),
                'language': book_info.get('language', '').strip(),
                'tags': book_info.get('tags', '').strip()
            }
            
            # 尝试搜索封面（如果请求包含book_id）
            book_id = data.get('book_id')
            cover_info = None
            if book_id:
                book = Book.query.get(book_id)
                if book and (not book.cover_image or not os.path.exists(book.cover_image)):
                    # 构建封面搜索查询
                    cover_query = query
                    if cleaned_info['title'] and cleaned_info['author']:
                        cover_query = f"{cleaned_info['title']} {cleaned_info['author']}"
                    elif cleaned_info['title']:
                        cover_query = cleaned_info['title']
                    
                    success, cover_path, message = search_and_download_cover(book, cover_query)
                    if success and cover_path:
                        # 更新封面路径
                        if book.cover_image and os.path.exists(book.cover_image):
                            try:
                                os.remove(book.cover_image)
                            except:
                                pass
                        
                        book.cover_image = cover_path
                        db.session.commit()
                        
                        # 同步到Calibre
                        calibre_synced = False
                        if book.calibre_id:
                            calibre_synced = update_calibre_cover(book)
                        
                        cover_info = {
                            'success': True,
                            'cover_url': url_for('uploaded_file', filename=os.path.basename(cover_path)),
                            'calibre_synced': calibre_synced
                        }
                    else:
                        cover_info = {
                            'success': False,
                            'message': message
                        }
            
            response_data = {
                'success': True,
                'book_info': cleaned_info,
                'source': 'ai_with_search' if search_results else 'ai_only'
            }
            
            if cover_info:
                response_data['cover'] = cover_info
            
            return jsonify(response_data), 200
            
        except json.JSONDecodeError as e:
            if app.debug:
                print(f"JSON解析失败: {e}")
                print(f"原始响应: {ai_response}")
            return jsonify({
                'error': 'AI返回的数据格式错误',
                'raw_response': ai_response[:500]
            }), 500
        
    except requests.exceptions.Timeout:
        return jsonify({'error': 'AI请求超时，请稍后重试'}), 504
    except requests.exceptions.ConnectionError:
        return jsonify({'error': '无法连接到Ollama服务，请检查配置'}), 503
    except Exception as e:
        if app.debug:
            import traceback
            traceback.print_exc()
        return jsonify({'error': f'AI辅助失败: {str(e)}'}), 500


@app.route('/api/ai/config', methods=['GET'])
@admin_required
def api_ai_config():
    """获取AI配置状态"""
    try:
        import requests
        
        # 检查Ollama连接
        ollama_status = 'disconnected'
        ollama_models = []
        if app.config['OLLAMA_BASE_URL']:
            try:
                resp = requests.get(
                    f"{app.config['OLLAMA_BASE_URL']}/api/tags",
                    timeout=5
                )
                if resp.status_code == 200:
                    ollama_status = 'connected'
                    ollama_models = [m['name'] for m in resp.json().get('models', [])]
            except:
                pass
        
        # 检查SearXNG连接
        searxng_status = 'disabled'
        if app.config['SEARXNG_ENABLED'] and app.config['SEARXNG_BASE_URL']:
            try:
                resp = requests.get(
                    f"{app.config['SEARXNG_BASE_URL']}/",
                    timeout=5
                )
                if resp.status_code == 200:
                    searxng_status = 'connected'
                else:
                    searxng_status = 'disconnected'
            except:
                searxng_status = 'disconnected'
        
        return jsonify({
            'ollama': {
                'status': ollama_status,
                'base_url': app.config['OLLAMA_BASE_URL'],
                'model': app.config['OLLAMA_MODEL'],
                'available_models': ollama_models
            },
            'searxng': {
                'status': searxng_status,
                'enabled': app.config['SEARXNG_ENABLED'],
                'base_url': app.config['SEARXNG_BASE_URL']
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# 批量AI补充任务状态存储
batch_ai_tasks = {}

# 自动后台补充配置
auto_fill_config = {
    'enabled': False,           # 是否启用自动补充
    'idle_threshold': 300,      # 空闲时间阈值（秒），默认5分钟
    'batch_size': 10,           # 每批处理数量
    'interval': 60,             # 检查间隔（秒）
    'running': False,           # 是否正在运行
    'paused': False,            # 是否暂停
    'last_activity': None,      # 最后活动时间
    'task_id': None             # 当前任务ID
}

import threading
import time
from datetime import datetime, timedelta

def update_last_activity():
    """更新最后活动时间"""
    auto_fill_config['last_activity'] = datetime.utcnow()

def is_system_idle():
    """检测系统是否空闲"""
    if auto_fill_config['last_activity'] is None:
        return False
    
    idle_time = (datetime.utcnow() - auto_fill_config['last_activity']).total_seconds()
    return idle_time >= auto_fill_config['idle_threshold']

def auto_fill_background_task():
    """后台自动补充任务"""
    while auto_fill_config['enabled']:
        try:
            # 等待间隔时间
            time.sleep(auto_fill_config['interval'])
            
            # 检查是否暂停
            if auto_fill_config['paused']:
                continue
            
            # 检查系统是否空闲
            if not is_system_idle():
                # 如果有任务在运行，暂停它
                if auto_fill_config['task_id']:
                    task = batch_ai_tasks.get(auto_fill_config['task_id'])
                    if task and task['status'] == 'running':
                        task['status'] = 'paused'
                        app.logger.info("检测到用户活动，暂停自动补充任务")
                continue
            
            # 系统空闲，检查是否有任务在运行
            if auto_fill_config['task_id']:
                task = batch_ai_tasks.get(auto_fill_config['task_id'])
                if task:
                    if task['status'] == 'paused':
                        # 恢复暂停的任务
                        task['status'] = 'running'
                        app.logger.info("系统空闲，恢复自动补充任务")
                    elif task['status'] in ['completed', 'failed']:
                        # 任务已完成，清除任务ID
                        auto_fill_config['task_id'] = None
                    else:
                        # 任务正在运行，继续等待
                        continue
            
            # 没有任务在运行，启动新任务
            if not auto_fill_config['task_id']:
                with app.app_context():
                    # 查询需要补充的书籍
                    query = Book.query.filter(
                        db.or_(
                            Book.author == None,
                            Book.author == '',
                            Book.publisher == None,
                            Book.publisher == '',
                            Book.description == None,
                            Book.description == ''
                        )
                    )
                    
                    from sqlalchemy import func
                    query = query.order_by(func.random())
                    books = query.limit(auto_fill_config['batch_size']).all()
                    
                    if books:
                        # 生成任务ID
                        import uuid
                        task_id = str(uuid.uuid4())
                        
                        # 初始化任务
                        batch_ai_tasks[task_id] = {
                            'status': 'running',
                            'total': len(books),
                            'processed': 0,
                            'success_count': 0,
                            'failed_count': 0,
                            'current_book': '',
                            'logs': [],
                            'book_ids': [b.id for b in books],
                            'auto': True  # 标记为自动任务
                        }
                        
                        auto_fill_config['task_id'] = task_id
                        
                        # 启动处理线程
                        thread = threading.Thread(target=process_batch_ai_task, args=(task_id,))
                        thread.daemon = True
                        thread.start()
                        
                        app.logger.info(f"启动自动补充任务: {len(books)}本书")
                    
        except Exception as e:
            app.logger.error(f"自动补充任务异常: {e}")
            time.sleep(60)  # 发生错误时等待1分钟

@app.route('/api/ai/auto-fill/config', methods=['GET'])
@admin_required
def api_get_auto_fill_config():
    """获取自动补充配置"""
    return jsonify({
        'success': True,
        'config': {
            'enabled': auto_fill_config['enabled'],
            'idle_threshold': auto_fill_config['idle_threshold'],
            'batch_size': auto_fill_config['batch_size'],
            'interval': auto_fill_config['interval'],
            'running': auto_fill_config['running'],
            'paused': auto_fill_config['paused'],
            'last_activity': auto_fill_config['last_activity'].isoformat() if auto_fill_config['last_activity'] else None
        }
    }), 200

@app.route('/api/ai/auto-fill/config', methods=['POST'])
@admin_required
def api_update_auto_fill_config():
    """更新自动补充配置"""
    try:
        data = request.get_json()
        
        if 'enabled' in data:
            auto_fill_config['enabled'] = bool(data['enabled'])
            
            if auto_fill_config['enabled'] and not auto_fill_config['running']:
                # 启动后台线程
                auto_fill_config['running'] = True
                auto_fill_config['last_activity'] = datetime.utcnow()
                thread = threading.Thread(target=auto_fill_background_task)
                thread.daemon = True
                thread.start()
                app.logger.info("已启动自动补充后台任务")
            elif not auto_fill_config['enabled']:
                auto_fill_config['running'] = False
                app.logger.info("已停止自动补充后台任务")
        
        if 'idle_threshold' in data:
            auto_fill_config['idle_threshold'] = int(data['idle_threshold'])
        
        if 'batch_size' in data:
            auto_fill_config['batch_size'] = int(data['batch_size'])
        
        if 'interval' in data:
            auto_fill_config['interval'] = int(data['interval'])
        
        return jsonify({
            'success': True,
            'message': '配置已更新'
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ai/auto-fill/pause', methods=['POST'])
@admin_required
def api_pause_auto_fill():
    """暂停/恢复自动补充"""
    try:
        data = request.get_json()
        paused = bool(data.get('paused', False))
        auto_fill_config['paused'] = paused
        
        return jsonify({
            'success': True,
            'message': '已暂停' if paused else '已恢复'
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ai/batch-fill', methods=['POST'])
@admin_required
def api_ai_batch_fill():
    """启动批量AI补充书籍信息任务"""
    try:
        data = request.get_json()
        scope = data.get('scope', 'missing_info')
        limit = int(data.get('limit', 50))
        
        # 查询需要补充的书籍
        query = Book.query
        
        if scope == 'missing_info':
            # 只查询缺失关键信息的书籍
            query = query.filter(
                db.or_(
                    Book.author == None,
                    Book.author == '',
                    Book.publisher == None,
                    Book.publisher == '',
                    Book.description == None,
                    Book.description == ''
                )
            )
        
        # 随机排序选取书籍
        from sqlalchemy import func
        query = query.order_by(func.random())
        
        books = query.limit(limit).all()
        
        if not books:
            return jsonify({'success': False, 'error': '没有找到需要补充信息的书籍'}), 400
        
        # 生成任务ID
        import uuid
        task_id = str(uuid.uuid4())
        
        # 初始化任务状态
        batch_ai_tasks[task_id] = {
            'status': 'running',
            'total': len(books),
            'processed': 0,
            'success_count': 0,
            'failed_count': 0,
            'current_book': '',
            'logs': [],
            'book_ids': [b.id for b in books]
        }
        
        # 启动后台线程处理
        import threading
        thread = threading.Thread(target=process_batch_ai_task, args=(task_id,))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'total': len(books)
        }), 200
        
    except Exception as e:
        app.logger.error(f"启动批量AI补充任务失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


def process_batch_ai_task(task_id):
    """后台处理批量AI补充任务"""
    import requests
    
    task = batch_ai_tasks.get(task_id)
    if not task:
        return
    
    def add_log(message, log_type='info'):
        task['logs'].append({'message': message, 'type': log_type})
    
    try:
        book_ids = task['book_ids']
        
        for i, book_id in enumerate(book_ids):
            with app.app_context():
                book = db.session.get(Book, book_id)
                if not book:
                    task['processed'] += 1
                    task['failed_count'] += 1
                    add_log(f'书籍ID {book_id} 不存在', 'error')
                    continue
                
                task['current_book'] = book.title or f'ID:{book.id}'
                add_log(f'正在处理: {task["current_book"]}')
                
                try:
                    # 构建搜索查询（过滤无效值）
                    invalid_values = ['未知', 'unknown', 'null', 'none', '无', 'n/a', '']
                    query_parts = []
                    
                    if book.title and book.title.strip().lower() not in invalid_values:
                        query_parts.append(book.title.strip())
                    if book.author and book.author.strip().lower() not in invalid_values:
                        query_parts.append(book.author.strip())
                    if book.isbn and book.isbn.strip().lower() not in invalid_values:
                        query_parts.append(book.isbn.strip())
                    
                    query = ' '.join(query_parts) if query_parts else f'书籍ID{book.id}'
                    
                    # 调用AI搜索API
                    search_results = ''
                    if app.config['SEARXNG_ENABLED'] and app.config['SEARXNG_BASE_URL']:
                        try:
                            resp = requests.get(
                                f"{app.config['SEARXNG_BASE_URL']}/search",
                                params={'q': query, 'format': 'json', 'categories': 'general'},
                                timeout=10
                            )
                            if resp.status_code == 200:
                                results = resp.json().get('results', [])[:3]
                                search_results = '\n'.join([
                                    f"{i+1}. {r.get('title', '')}: {r.get('content', '')}"
                                    for i, r in enumerate(results)
                                ])
                        except:
                            pass
                    
                    # 构建Ollama提示
                    search_section = f'搜索结果:\n{search_results}\n' if search_results else ''
                    prompt = f"""请根据以下信息，帮我整理这本书的详细信息：

查询关键词：{query}

{search_section}

请返回JSON格式的书籍信息，包含以下字段（如果无法确定某个字段，返回null）：
- title: 书名
- author: 作者
- publisher: 出版社
- isbn: ISBN号
- publication_date: 出版日期(YYYY-MM-DD格式)
- language: 语言
- tags: 标签（多个用逗号分隔）
- description: 简介

只返回JSON，不要其他内容。"""
                    
                    # 调用Ollama
                    resp = requests.post(
                        f"{app.config['OLLAMA_BASE_URL']}/api/generate",
                        json={
                            'model': app.config['OLLAMA_MODEL'],
                            'prompt': prompt,
                            'stream': False,
                            'format': 'json'
                        },
                        timeout=app.config['OLLAMA_TIMEOUT']
                    )
                    
                    if resp.status_code == 200:
                        result = resp.json()
                        response_text = result.get('response', '{}')
                        
                        import json
                        book_info = json.loads(response_text)
                        
                        # 定义无效值列表
                        invalid_values = ['未知', 'unknown', 'null', 'none', '无', 'n/a', '']
                        
                        # 辅助函数：判断字段是否为有效值（不为空且不是无效值）
                        def is_valid(value):
                            if not value:
                                return False
                            if isinstance(value, str) and value.strip().lower() in invalid_values:
                                return False
                            return True
                        
                        # 更新书籍信息（只更新空缺或无效的字段）
                        updated = False
                        if book_info.get('title') and is_valid(book_info.get('title')) and not is_valid(book.title):
                            book.title = book_info['title']
                            updated = True
                        if book_info.get('author') and is_valid(book_info.get('author')) and not is_valid(book.author):
                            book.author = book_info['author']
                            updated = True
                        if book_info.get('publisher') and is_valid(book_info.get('publisher')) and not is_valid(book.publisher):
                            book.publisher = book_info['publisher']
                            updated = True
                        if book_info.get('isbn') and is_valid(book_info.get('isbn')) and not is_valid(book.isbn):
                            book.isbn = book_info['isbn']
                            updated = True
                        if book_info.get('publication_date') and not book.publication_date:
                            from datetime import datetime
                            try:
                                book.publication_date = datetime.strptime(book_info['publication_date'], '%Y-%m-%d').date()
                                updated = True
                            except:
                                pass
                        if book_info.get('language') and is_valid(book_info.get('language')) and not is_valid(book.language):
                            book.language = book_info['language']
                            updated = True
                        if book_info.get('tags') and is_valid(book_info.get('tags')) and not is_valid(book.tags):
                            book.tags = book_info['tags']
                            updated = True
                        if book_info.get('description') and is_valid(book_info.get('description')) and not is_valid(book.description):
                            book.description = book_info['description']
                            updated = True
                        
                        if updated:
                            db.session.commit()
                            
                            # 同步更新到Calibre数据库
                            calibre_updated = update_calibre_metadata(book)
                            if calibre_updated:
                                task['success_count'] += 1
                                add_log(f'✓ {task["current_book"]} - 成功更新（已同步到Calibre）', 'success')
                            else:
                                task['success_count'] += 1
                                add_log(f'✓ {task["current_book"]} - 成功更新（Calibre同步失败或未配置）', 'warning')
                        else:
                            add_log(f'○ {task["current_book"]} - 无需更新', 'info')
                        
                        # 检查并补充封面
                        if not book.cover_image or not os.path.exists(book.cover_image):
                            add_log(f'🖼️ 正在搜索封面: {task["current_book"]}', 'info')
                            success, cover_path, message = search_and_download_cover(book, query)
                            
                            if success and cover_path:
                                # 删除旧封面（如果存在）
                                if book.cover_image and os.path.exists(book.cover_image):
                                    try:
                                        os.remove(book.cover_image)
                                    except:
                                        pass
                                
                                # 更新封面路径
                                book.cover_image = cover_path
                                db.session.commit()
                                
                                # 同步到Calibre
                                if book.calibre_id:
                                    cover_synced = update_calibre_cover(book)
                                    if cover_synced:
                                        add_log(f'✓ {task["current_book"]} - 封面已更新并同步到Calibre', 'success')
                                    else:
                                        add_log(f'✓ {task["current_book"]} - 封面已更新（Calibre同步失败）', 'warning')
                                else:
                                    add_log(f'✓ {task["current_book"]} - 封面已更新', 'success')
                            else:
                                add_log(f'○ {task["current_book"]} - 封面搜索失败: {message}', 'info')
                        
                    else:
                        task['failed_count'] += 1
                        add_log(f'✗ {task["current_book"]} - AI调用失败', 'error')
                
                except Exception as e:
                    task['failed_count'] += 1
                    add_log(f'✗ {task["current_book"]} - 处理失败: {str(e)}', 'error')
                
                task['processed'] += 1
                
                # 小延迟避免API限流
                import time
                time.sleep(0.5)
        
        task['status'] = 'completed'
        add_log('批量任务完成', 'success')
        
    except Exception as e:
        task['status'] = 'failed'
        add_log(f'任务异常终止: {str(e)}', 'error')


@app.route('/api/ai/batch-progress/<task_id>', methods=['GET'])
@admin_required
def api_ai_batch_progress(task_id):
    """获取批量AI补充任务进度"""
    task = batch_ai_tasks.get(task_id)
    
    if not task:
        return jsonify({'success': False, 'error': '任务不存在'}), 404
    
    # 获取新日志
    logs = task['logs']
    task['logs'] = []  # 清空已读日志
    
    return jsonify({
        'success': True,
        'status': task['status'],
        'total': task['total'],
        'processed': task['processed'],
        'success_count': task['success_count'],
        'failed_count': task['failed_count'],
        'current_book': task['current_book'],
        'logs': logs
    }), 200


if __name__ == '__main__':
    init_db()
    
    # 从环境变量读取配置
    port = int(os.getenv('PORT', 5000))
    host = os.getenv('HOST', '0.0.0.0')
    debug = os.getenv('DEBUG', 'True').lower() == 'true'
    
    print("=" * 50)
    print("Calibre Web 管理系统已启动")
    print(f"访问地址: http://localhost:{port}")
    print("=" * 50)
    app.run(debug=debug, host=host, port=port)
