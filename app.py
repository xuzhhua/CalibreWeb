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

db = SQLAlchemy(app)

# 确保上传文件夹存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 导入状态跟踪
import_status = {
    'running': False,
    'progress': 0,
    'total': 0,
    'imported': 0,
    'updated': 0,
    'skipped': 0,
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
    """需要管理员权限的装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': '请先登录'}), 401
        user = db.session.get(User, session['user_id'])
        if not user or not user.is_admin:
            return jsonify({'error': '需要管理员权限'}), 403
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
    
    return jsonify({'message': '书籍更新成功', 'book': book.to_dict()}), 200


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
    
    return jsonify({
        'total_books': total_books,
        'total_users': total_users,
        'books_by_language': dict(books_by_language)
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


# ==================== Calibre数据库集成 ====================

def get_calibre_db_path():
    """获取Calibre数据库路径"""
    library_path = app.config['CALIBRE_LIBRARY_PATH']
    if library_path and os.path.exists(library_path):
        metadata_db = os.path.join(library_path, 'metadata.db')
        if os.path.exists(metadata_db):
            return metadata_db
    return None


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
        
        for idx, book_data in enumerate(books, 1):
            if idx % 100 == 0:
                print(f"处理进度: {idx}/{len(books)}")
            
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
        
        db.session.commit()
        conn.close()
        result = {
            'imported': imported_count,
            'total': total_books,
            'skipped': skipped_count,
            'updated': updated_count,
            'processed': len(books)
        }
        print(f"本次导入完成: 新增{imported_count}本，更新{updated_count}本，跳过{skipped_count}本，共处理{len(books)}本")
        return result
        
    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
        return {'imported': 0, 'total': 0, 'skipped': 0, 'updated': 0, 'error': str(e)}
    except Exception as e:
        print(f"从Calibre导入失败: {e}")
        import traceback
        traceback.print_exc()
        return {'imported': 0, 'total': 0, 'skipped': 0, 'updated': 0, 'error': str(e)}


def update_book_completeness(book, calibre_id, cursor, path):
    """检查并更新书籍信息的完整性"""
    updated = False
    
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
            
            # 如果数据库为空，进行完整导入
            if existing_count == 0:
                print("数据库为空，开始完整导入...")
            # 如果数据库已有数据但数量少于Calibre书库，先检查完整性，再导入新书
            elif existing_count > 0 and existing_count < calibre_total:
                print(f"数据库已有 {existing_count} 本书，Calibre有 {calibre_total} 本书")
                print("先检查现有书籍的完整性...")
                updated = batch_check_completeness()
                print(f"完整性检查完成：更新了 {updated} 本书")
                print(f"继续导入剩余的 {calibre_total - existing_count} 本书...")
                # 从已有数量开始继续导入
                offset = existing_count
            # 如果数量相同，只做完整性检查
            else:
                print("数据库已有数据，仅检查和更新不完整的记录...")
                updated = batch_check_completeness()
                import_status['updated'] = updated
                import_status['imported'] = 0
                import_status['skipped'] = existing_count - updated
                import_status['progress'] = existing_count
                import_status['total'] = existing_count
                import_status['completed'] = True
                print(f"完整性检查完成：更新 {updated} 本书")
                return
            
            while True:
                import_status['current_book'] = f'处理第 {offset} - {offset + BATCH_SIZE} 本'
                
                result = import_from_calibre(limit=BATCH_SIZE, offset=offset)
                
                if 'error' in result:
                    import_status['error'] = result['error']
                    break
                
                total_imported += result['imported']
                total_updated += result['updated']
                total_skipped += result['skipped']
                
                import_status['imported'] = total_imported
                import_status['updated'] = total_updated
                import_status['skipped'] = total_skipped
                import_status['total'] = result['total']
                import_status['progress'] = offset + result['processed']
                
                # 如果这批没处理到足够的书，说明已经全部导入完毕
                if result['processed'] < BATCH_SIZE:
                    break
                
                offset += result['processed']
                
                # 每批之间稍微休息，避免占用太多CPU
                time.sleep(0.5)
            
            import_status['completed'] = True
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
        failed_books = []  # 记录失败的图书
        
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
                    skipped_count += 1
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
            'updated': 0,
            'processed': len(books),
            'failed': len(failed_books)
        }
        print(f"本次导入完成: 新增{imported_count}本，跳过{skipped_count}本，失败{len(failed_books)}本，共处理{len(books)}本")
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
        
        # 如果配置了Calibre书库，自动在后台开始导入
        if app.config['CALIBRE_LIBRARY_PATH']:
            calibre_db = get_calibre_db_path()
            if calibre_db:
                print("检测到Calibre书库，5秒后将自动开始后台导入...")
                # 延迟5秒启动，确保init完成
                def delayed_start():
                    time.sleep(5)
                    print("开始后台导入任务...")
                    background_import_task()
                
                thread = threading.Thread(target=delayed_start, daemon=True)
                thread.start()
            else:
                print("提示：未找到Calibre数据库文件")


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
