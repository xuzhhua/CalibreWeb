# Calibre Web 管理系统

一个优雅、现代化的个人数字图书馆管理系统，基于 Flask 构建。

## 功能特性

- ✅ **用户认证系统**：注册、登录、权限管理
- ✅ **图书管理**：添加、编辑、删除图书
- ✅ **智能搜索**：支持书名、作者、ISBN、标签等多维度搜索
- ✅ **分页显示**：优化大量图书的浏览体验
- ✅ **美观界面**：现代化、响应式设计
- ✅ **统计信息**：图书数量、用户数量等统计
- ✅ **标签管理**：为图书添加多个标签
- ✅ **Calibre 集成**：从现有 Calibre 书库导入图书
- ✅ **智能增量导入**：自动检测新书和更新不完整的记录
- ✅ **导入日志记录**：记录导入失败的书籍到日志文件

## 技术栈

- **后端**：Flask + SQLAlchemy
- **数据库**：SQLite
- **前端**：HTML5 + CSS3 + JavaScript
- **认证**：Session + Werkzeug 密码哈希

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置Calibre书库（可选）

如果您已有Calibre书库，可以配置路径以导入现有书籍：

**方法一：环境变量**
```bash
# Windows (cmd)
set CALIBRE_LIBRARY_PATH=D:\My Calibre Library
set USE_CALIBRE_DB=True

# Linux/Mac
export CALIBRE_LIBRARY_PATH="/home/user/Calibre Library"
export USE_CALIBRE_DB=True
```

**方法二：.env 文件**
```bash
# 复制配置文件模板
cp .env.example .env

# 编辑 .env 文件，设置您的Calibre书库路径
```

详细配置说明请查看 [CALIBRE_CONFIG.md](CALIBRE_CONFIG.md)

### 3. 运行应用

```bash
python app.py
```

### 4. 访问应用

在浏览器中打开：http://localhost:5000

## 使用说明

### 首次使用

1. 访问首页，点击"注册"创建账号
2. 第一个注册的用户将自动成为管理员
3. 登录后即可开始管理您的图书

### 添加图书

1. 在仪表板点击"+ 添加图书"按钮
2. 填写图书信息（书名为必填项）
3. 可选添加：作者、出版社、ISBN、出版日期、评分、标签、简介等
4. 点击"保存"完成添加

### 搜索图书

- 在搜索框中输入关键词
- 系统会自动搜索书名、作者、ISBN、出版社、标签等字段
- 实时显示搜索结果

### 编辑/删除图书

- 在图书卡片上点击"编辑"按钮可修改图书信息
- 点击"删除"按钮可删除图书（需确认）

## 目录结构

```
CalibreWeb/
├── app.py                  # 主应用文件
├── requirements.txt        # 依赖列表
├── calibre_web.db         # SQLite 数据库（自动创建）
├── uploads/               # 上传文件目录（自动创建）
├── logs/                  # 日志目录（自动创建）
│   └── import_failures.log # 导入失败日志
├── static/                # 静态资源
└── templates/             # HTML 模板
    ├── index.html         # 欢迎页
    ├── login.html         # 登录页
    ├── register.html      # 注册页
    └── dashboard.html     # 仪表板（主界面）
```

## API 接口

### 用户认证

- `POST /api/register` - 用户注册
- `POST /api/login` - 用户登录
- `POST /api/logout` - 用户登出
- `GET /api/current-user` - 获取当前用户信息

### 图书管理

- `GET /api/books` - 获取图书列表（支持搜索和分页）
- `GET /api/books/<id>` - 获取单本图书详情
- `POST /api/books` - 创建新图书
- `PUT /api/books/<id>` - 更新图书信息
- `DELETE /api/books/<id>` - 删除图书
- `GET /api/books/stats` - 获取统计信息

### Calibre 集成（管理员）

- `GET /api/calibre/config` - 获取Calibre配置
- `POST /api/calibre/config` - 设置Calibre书库路径
- `POST /api/calibre/import` - 触发后台导入任务
- `GET /api/calibre/import-status` - 获取导入进度状态

### 用户管理（管理员）

- `GET /api/users` - 获取用户列表
- `DELETE /api/users/<id>` - 删除用户

## 数据模型

### User（用户）
- id: 主键
- username: 用户名（唯一）
- email: 邮箱（唯一）
- password_hash: 密码哈希
- is_admin: 是否为管理员
- created_at: 创建时间

### Book（图书）
- id: 主键
- title: 书名
- author: 作者
- publisher: 出版社
- isbn: ISBN
- publication_date: 出版日期
- description: 简介
- cover_image: 封面图片路径
- file_path: 文件路径
- file_format: 文件格式
- file_size: 文件大小
- language: 语言
- tags: 标签
- rating: 评分
- created_at: 创建时间
- updated_at: 更新时间

## 安全说明

⚠️ **生产环境部署前请务必**：

1. 修改 `app.py` 中的 `SECRET_KEY`
2. 使用更强的密码策略
3. 配置 HTTPS
4. 设置适当的文件上传限制
5. 考虑使用专业数据库（PostgreSQL、MySQL）

## 导入日志说明

系统会自动记录Calibre导入过程中失败的书籍：

- **日志位置**：`logs/import_failures.log`
- **日志格式**：时间戳 - 级别 - 书籍信息 | 错误详情
- **日志轮转**：最大10MB，保留5个备份文件
- **编码格式**：UTF-8（支持中文）

**日志示例**：
```
2026-01-30 10:15:32 - ERROR - 书籍: Python编程 (Calibre ID: 123) | 错误: 文件路径不存在
2026-01-30 10:15:35 - ERROR - 数据库连接错误: unable to open database file
```

导入完成后，控制台会显示失败数量和日志文件路径。

## 后续扩展计划

- [x] Calibre书库集成
- [x] 智能增量导入
- [x] 导入日志记录
- [ ] 图书封面上传
- [ ] 电子书文件上传和在线阅读
- [ ] 书籍分类和系列管理
- [ ] 阅读进度跟踪
- [ ] 书评和笔记功能
- [ ] 导出功能
- [ ] 多语言支持

## 许可证

MIT License

## 作者

GitHub Copilot

---

享受您的数字图书馆之旅！📚
