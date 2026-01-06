# Calibre Web 管理系统

一个优雅、现代化的个人数字图书馆管理系统，基于 Flask 构建。

## ✨ 功能特性

### 📚 图书管理
- ✅ **完整的图书管理**：添加、编辑、删除图书
- ✅ **智能搜索**：支持书名、作者、ISBN、标签等多维度搜索
- ✅ **分页显示**：优化大量图书的浏览体验
- ✅ **标签管理**：为图书添加多个标签
- ✅ **文件上传**：支持电子书文件上传和管理
- ✅ **封面显示**：支持图书封面图片展示
- ✅ **文件下载**：支持电子书文件下载
- ✅ **在线预览**：支持特定格式的在线阅读

### 👥 用户系统
- ✅ **用户注册登录**：完整的用户认证系统
- ✅ **用户审核机制**：管理员可以审核、批准或拒绝新用户
- ✅ **权限管理**：管理员权限设置和管理
- ✅ **个性化功能**：
  - 收藏图书
  - 标记已读状态
  - 个人阅读统计

### 📖 Calibre 集成
- ✅ **Calibre 书库导入**：支持从现有 Calibre 书库导入图书
- ✅ **智能同步**：自动同步 Calibre 数据库中的书籍信息
- ✅ **封面和文件处理**：自动导入封面和电子书文件
- ✅ **增量导入**：支持增量导入和更新

### 🎨 界面体验
- ✅ **现代化设计**：美观的响应式界面
- ✅ **统计面板**：图书数量、用户数量、阅读统计等
- ✅ **实时更新**：动态加载和更新内容

## 🛠️ 技术栈

- **后端框架**：Flask 3.0.0
- **数据库 ORM**：Flask-SQLAlchemy 3.1.1 + SQLAlchemy 2.0.23
- **数据库**：SQLite
- **前端技术**：HTML5 + CSS3 + JavaScript
- **用户认证**：Session + Werkzeug 3.0.1 密码哈希
- **环境配置**：python-dotenv 1.0.0
- **文件处理**：支持多种电子书格式

## 🚀 快速开始

### 环境要求

- Python 3.8+
- pip 包管理器
- （可选）现有的 Calibre 书库

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量（可选）

创建 `.env` 文件来配置应用：

```bash
# 复制配置文件模板
copy .env.example .env  # Windows
cp .env.example .env    # Linux/Mac
```

编辑 `.env` 文件设置：

```env
# 应用密钥（生产环境务必修改）
SECRET_KEY=your-secret-key-change-in-production

# 数据库配置
DATABASE_URI=sqlite:///calibre_web.db

# Calibre 书库配置（如果有现有的 Calibre 书库）
CALIBRE_LIBRARY_PATH=D:\My Calibre Library
USE_CALIBRE_DB=True
```

### 3. 运行应用

```bash
python app.py
```

应用将在 http://localhost:5000 启动。

### 4. 首次使用

1. 访问 http://localhost:5000
2. 点击"注册"创建账号
3. **第一个注册的用户自动成为管理员**
4. 后续用户需要管理员审核通过才能使用

## 📖 使用说明

### 用户管理

#### 新用户注册
1. 访问首页，点击"注册"
2. 填写用户名、邮箱和密码
3. 提交注册申请
4. 等待管理员审核通过（首个用户自动通过）

#### 管理员功能
- 查看所有用户列表
- 审核新用户注册申请（批准/拒绝）
- 设置其他用户为管理员
- 删除用户账号
- 从 Calibre 导入图书

### 图书管理

#### 添加图书
1. 在仪表板点击"+ 添加图书"按钮
2. 填写图书信息：
   - **必填项**：书名
   - **可选项**：作者、出版社、ISBN、出版日期、评分、标签、简介等
3. 点击"保存"完成添加
4. （可选）稍后上传电子书文件和封面图片

#### 搜索和筛选
- 在搜索框中输入关键词
- 系统自动搜索：书名、作者、ISBN、出版社、标签等字段
- 实时显示搜索结果
- 支持分页浏览

#### 编辑和删除
- 点击图书卡片上的"编辑"按钮修改信息
- 点击"删除"按钮删除图书（需确认）
- 上传或更换电子书文件
- 上传或更换封面图片

#### 个性化功能
- **收藏图书**：点击收藏按钮标记喜欢的书籍
- **标记已读**：记录已读书籍
- **下载图书**：下载电子书文件到本地
- **在线阅读**：支持部分格式的在线预览

### Calibre 集成

#### 导入 Calibre 书库
1. 管理员登录系统
2. 在设置中配置 Calibre 书库路径
3. 点击"从 Calibre 导入"
4. 等待导入完成
5. 系统会：
   - 导入所有书籍的元数据
   - 复制封面图片
   - 复制电子书文件
   - 保留原有书库不变

#### 导入状态
- 实时查看导入进度
- 查看导入统计：已导入、已更新、已跳过
- 导入完成后查看详细报告

## 📁 目录结构

```
CalibreWeb/
├── app.py                    # 主应用文件（1400+ 行）
├── requirements.txt          # Python 依赖列表
├── .env.example             # 环境变量配置模板
├── .gitignore               # Git 忽略文件配置
├── README.md                # 项目文档
│
├── instance/                # 实例文件夹（自动创建）
│   └── calibre_web.db      # SQLite 数据库
│
├── templates/               # HTML 模板
│   ├── index.html          # 欢迎页
│   ├── login.html          # 登录页
│   ├── register.html       # 注册页
│   ├── dashboard.html      # 主仪表板
│   ├── reader.html         # 在线阅读器
│   └── test_dashboard.html # 测试页面
│
└── uploads/                 # 上传文件目录（自动创建）
    ├── covers/             # 图书封面
    └── books/              # 电子书文件
```

## 🔌 API 接口文档

### 用户认证

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/register` | POST | 用户注册 |
| `/api/login` | POST | 用户登录 |
| `/api/logout` | POST | 用户登出 |
| `/api/current-user` | GET | 获取当前用户信息 |

### 用户管理（管理员）

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/admin/users` | GET | 获取所有用户列表 |
| `/api/admin/users/<id>/approve` | POST | 批准用户注册 |
| `/api/admin/users/<id>/reject` | POST | 拒绝用户注册 |
| `/api/admin/users/<id>/set-admin` | POST | 设置用户为管理员 |
| `/api/admin/users/<id>` | DELETE | 删除用户 |

### 图书管理

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/books` | GET | 获取图书列表（支持搜索和分页） |
| `/api/books/<id>` | GET | 获取单本图书详情 |
| `/api/books` | POST | 创建新图书 |
| `/api/books/<id>` | PUT | 更新图书信息 |
| `/api/books/<id>` | DELETE | 删除图书 |
| `/api/books/stats` | GET | 获取统计信息 |
| `/api/books/<id>/cover` | GET | 获取图书封面 |
| `/api/books/<id>/download` | GET | 下载电子书文件 |
| `/api/books/<id>/preview` | GET | 在线预览图书 |

### 图书文件上传

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/upload-book-file/<id>` | POST | 上传电子书文件 |

### 个性化功能

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/books/<id>/favorite` | POST | 收藏/取消收藏图书 |
| `/api/books/<id>/mark-read` | POST | 标记已读/未读 |

### Calibre 集成

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/calibre/config` | GET | 获取 Calibre 配置 |
| `/api/calibre/config` | POST | 设置 Calibre 书库路径（管理员） |
| `/api/calibre/import` | POST | 从 Calibre 导入图书（管理员） |
| `/api/calibre/import-status` | GET | 获取导入进度状态 |
| `/api/calibre/acknowledge-import` | POST | 确认导入完成 |

## 💾 数据模型

### User（用户表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| username | String(80) | 用户名（唯一） |
| email | String(120) | 邮箱（唯一） |
| password_hash | String(200) | 密码哈希 |
| is_admin | Boolean | 是否为管理员 |
| is_approved | Boolean | 是否通过审核 |
| created_at | DateTime | 创建时间 |

### Book（图书表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| title | String(200) | 书名（必填） |
| author | String(200) | 作者 |
| publisher | String(200) | 出版社 |
| isbn | String(20) | ISBN |
| publication_date | Date | 出版日期 |
| description | Text | 简介 |
| cover_image | String(300) | 封面图片路径 |
| file_path | String(500) | 文件路径 |
| file_format | String(10) | 文件格式 |
| file_size | Integer | 文件大小（字节） |
| language | String(50) | 语言 |
| tags | String(500) | 标签（逗号分隔） |
| rating | Float | 评分（0-5） |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

### UserBookStatus（用户书籍状态表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| user_id | Integer | 用户 ID（外键） |
| book_id | Integer | 图书 ID（外键） |
| is_favorite | Boolean | 是否收藏 |
| is_read | Boolean | 是否已读 |
| reading_progress | Integer | 阅读进度（百分比） |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

**注意**：`user_id` 和 `book_id` 组合唯一。

## ⚙️ 配置说明

### 环境变量

在 `.env` 文件中可以配置以下参数：

```env
# 应用密钥（必须修改）
SECRET_KEY=your-secret-key-here

# 数据库配置
DATABASE_URI=sqlite:///calibre_web.db

# Calibre 集成
CALIBRE_LIBRARY_PATH=D:\My Calibre Library
USE_CALIBRE_DB=True
```

### 上传限制

默认配置：
- 最大文件大小：50MB
- 支持的文件格式：常见电子书格式（EPUB、PDF、MOBI 等）

可在 [app.py](app.py#L25) 中修改 `MAX_CONTENT_LENGTH` 调整限制。

### 会话时长

默认会话保持 7 天，可在 [app.py](app.py#L26) 中修改 `PERMANENT_SESSION_LIFETIME`。

## 🔒 安全说明

## 🔒 安全说明

⚠️ **生产环境部署前请务必**：

1. **修改密钥**：更改 `.env` 文件中的 `SECRET_KEY` 为强随机字符串
2. **密码策略**：建议实施更强的密码复杂度要求
3. **HTTPS**：配置 SSL/TLS 证书，使用 HTTPS 协议
4. **文件上传**：
   - 验证上传文件类型
   - 设置合理的文件大小限制
   - 扫描上传文件的安全性
5. **数据库**：生产环境建议使用 PostgreSQL 或 MySQL
6. **备份**：定期备份数据库和上传文件
7. **日志**：配置适当的日志记录和监控
8. **防火墙**：限制不必要的端口访问
9. **更新**：及时更新依赖包的安全补丁

## 🚧 开发计划

### 已完成功能 ✅
- [x] 用户注册登录系统
- [x] 用户审核机制
- [x] 图书增删改查
- [x] 图书搜索和分页
- [x] 标签管理
- [x] 图书封面显示
- [x] 电子书文件上传下载
- [x] 收藏和已读标记
- [x] Calibre 书库导入
- [x] 在线阅读预览
- [x] 统计面板

### 计划中功能 🎯
- [ ] 阅读进度追踪和同步
- [ ] 书评和读书笔记
- [ ] 图书分类和系列管理
- [ ] 更多电子书格式支持
- [ ] 图书推荐系统
- [ ] 导出功能（CSV、JSON）
- [ ] 多语言界面支持
- [ ] 移动端 APP
- [ ] 社交分享功能
- [ ] API 文档（Swagger/OpenAPI）
- [ ] Docker 容器化部署
- [ ] 全文搜索（Elasticsearch）
- [ ] 主题切换（深色模式）

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 👨‍💻 关于

本项目由 GitHub Copilot 协助开发，旨在提供一个简单易用的个人图书管理解决方案。

---

**版本**：1.0.0  
**最后更新**：2026年1月6日

享受您的数字图书馆之旅！📚✨
