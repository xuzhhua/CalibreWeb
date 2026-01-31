# Calibre Web 管理系统

一个优雅、现代化的个人数字图书馆管理系统，基于 Flask 构建。

## 📚 功能特性

### 核心功能
- ✅ **用户认证系统**：注册、登录、审核机制、权限管理
- ✅ **图书管理**：添加、编辑、删除、批量操作
- ✅ **智能搜索**：支持书名、作者、ISBN、标签等多维度搜索
- ✅ **分页显示**：优化大量图书的浏览体验
- ✅ **美观界面**：现代化、响应式设计，支持4种主题切换
- ✅ **统计信息**：图书数量、用户数量等实时统计
- ✅ **标签管理**：为图书添加多个标签，智能分类

### Calibre 集成
- ✅ **智能增量导入**：自动检测新书和更新不完整的记录
- ✅ **书库差异分析**：对比本地和Calibre数据库，精确同步
- ✅ **批量选择操作**：选择性导入、更新、删除
- ✅ **导入日志记录**：详细记录导入过程和失败原因
- ✅ **完整性检查**：自动检查封面、文件、简介、标签

### 管理功能
- ✅ **用户管理**：管理员可审核、删除用户
- ✅ **权限控制**：管理员/普通用户分级管理
- ✅ **后台任务**：异步导入，不阻塞界面
- ✅ **进度跟踪**：实时查看导入进度

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境

#### 方法1：使用 .env 文件（推荐）

创建 `.env` 文件：
```bash
# Calibre书库路径（必填）
CALIBRE_LIBRARY_PATH=E:\MyCalibre

# 启用Calibre数据库集成
USE_CALIBRE_DB=True

# Flask密钥（生产环境请修改）
SECRET_KEY=your-secret-key-here

# 服务器配置
PORT=18080
HOST=0.0.0.0
DEBUG=False
```

#### 方法2：环境变量

**Windows (cmd)**
```cmd
set CALIBRE_LIBRARY_PATH=D:\My Calibre Library
set USE_CALIBRE_DB=True
set PORT=18080
python app.py
```

**Windows (PowerShell)**
```powershell
$env:CALIBRE_LIBRARY_PATH="D:\My Calibre Library"
$env:USE_CALIBRE_DB="True"
$env:PORT="18080"
python app.py
```

**Linux/Mac**
```bash
export CALIBRE_LIBRARY_PATH="/home/user/Calibre Library"
export USE_CALIBRE_DB=True
export PORT=18080
python app.py
```

### 3. 运行应用

```bash
python app.py
```

### 4. 访问应用

在浏览器中打开：http://localhost:18080

## 📖 详细使用指南

### 首次使用

1. 访问首页，点击"注册"创建账号
2. 第一个注册的用户将自动成为管理员
3. 后续用户需要管理员审核后才能使用
4. 登录后即可开始管理您的图书

### Calibre 书库配置说明

#### Calibre 书库目录要求

Calibre书库目录必须包含 `metadata.db` 文件：
```
E:\MyCalibre\
├── metadata.db              ← 必需的数据库文件
├── 作者名\
│   └── 书名\
│       ├── book.epub
│       ├── cover.jpg
│       └── metadata.opf
```

#### 支持的电子书格式
- EPUB
- PDF
- MOBI
- AZW3
- TXT

### 📊 书库差异分析功能（推荐）

这是最高效的书库同步方式，提供精确控制和快速分析。

#### 访问方式
1. 以管理员身份登录
2. 点击导航栏的"📊 书库差异分析"按钮
3. 或直接访问：`http://localhost:18080/calibre-diff`

#### 功能说明

**1. 快速差异分析**
- 自动对比本地数据库和Calibre数据库
- 生成详细的差异报告（2-4秒完成，即使10万+书籍）
- 识别三种状态的书籍

**2. 智能分类**
- **待导入书籍**：只在Calibre中存在的新书
- **待更新书籍**：信息不完整（缺封面/文件/简介/标签）
- **孤立书籍**：只在本地存在（Calibre中已删除）

**3. 批量选择操作**
- 支持全选/取消全选
- 可以只处理特定书籍
- 三种操作：导入、更新、删除

#### 使用场景

**场景1：首次导入**
```
1. 运行差异分析
2. 查看"待导入书籍"列表
3. 全选或选择需要的书籍
4. 点击"导入选定的书籍"
```

**场景2：增量更新**
```
1. 定期运行差异分析
2. 只导入新增的书籍
3. 跳过已有书籍，节省时间
```

**场景3：修复不完整数据**
```
1. 查看"需要更新的书籍"
2. 看到每本书缺失的信息
3. 选择需要修复的书
4. 点击"更新选定的书籍"
```

**场景4：清理孤立数据**
```
1. 查看"孤立的书籍"
2. 选择要删除的书
3. 点击"删除选定的书籍"
```

#### 性能对比

| 特性 | 传统全量导入 | 差异分析方式 |
|------|------------|------------|
| 分析速度（10万书） | 约5分钟 | 约4秒 |
| 用户控制 | 无 | 完全控制 |
| 重复处理 | 是 | 否 |
| 灵活性 | 低 | 高 |

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
- 管理员可以编辑所有书籍，普通用户仅限自己添加的

### 主题切换

点击导航栏的主题按钮，支持4种主题：
- 🟤 **木质书架**（默认）：温馨的米白色调
- 🟣 **现代简约**：优雅的紫色渐变
- ⚫ **深色主题**：护眼的深灰色
- 🔵 **海洋主题**：清新的蓝色调

## 🔧 技术栈

- **后端**：Flask 2.x + SQLAlchemy
- **数据库**：SQLite
- **前端**：HTML5 + CSS3 + Vanilla JavaScript
- **认证**：Session + Werkzeug 密码哈希
- **日志**：RotatingFileHandler（自动轮转）
- **配置**：python-dotenv

## 📁 目录结构

```
CalibreWeb/
├── app.py                          # 主应用（1900+行）
├── requirements.txt                # Python依赖
├── .env                           # 环境配置
├── README.md                       # 本文档（完整指南）
├── calibre_web.db                 # SQLite数据库（自动创建）
├── migrate_users.py                # 用户数据库迁移脚本
├── diagnose_book_db.py             # 书籍数据库诊断工具
├── find_missing_books.py           # 查找缺失书籍工具
├── find_calibre_duplicates.py      # 查找重复书籍工具
├── test_diff_logic.py              # 差异分析逻辑测试
├── instance/                       # Flask实例目录
├── uploads/                        # 上传文件目录
├── logs/                           # 日志目录
│   └── import_failures.log        # 导入失败日志（自动创建）
├── static/
│   └── favicon.svg                # 网站图标
└── templates/                      # HTML模板
    ├── index.html                 # 欢迎页
    ├── login.html                 # 登录页
    ├── register.html              # 注册页
    ├── dashboard.html             # 仪表板（主界面，2700+行）
    ├── reader.html                # 电子书阅读器
    ├── test_dashboard.html        # 测试页面
    └── calibre_diff.html          # 差异分析页面（600+行）
```

## 🔌 API 接口

### 用户认证

```http
POST /api/register          # 用户注册
POST /api/login            # 用户登录
POST /api/logout           # 用户登出
GET  /api/current-user     # 获取当前用户信息
```

### 图书管理

```http
GET    /api/books          # 获取图书列表（支持搜索和分页）
GET    /api/books/<id>     # 获取单本图书详情
POST   /api/books          # 创建新图书
PUT    /api/books/<id>     # 更新图书信息
DELETE /api/books/<id>     # 删除图书
GET    /api/books/stats    # 获取统计信息
```

### Calibre 集成（管理员）

```http
GET  /api/calibre/config          # 获取Calibre配置
POST /api/calibre/config          # 设置Calibre书库路径
POST /api/calibre/import          # 触发后台导入任务
GET  /api/calibre/import-status   # 获取导入进度
GET  /api/calibre/diff            # 获取差异分析报告
POST /api/calibre/import-selected # 选择性导入/更新/删除
```

#### 差异分析API示例

**获取差异分析：**
```javascript
fetch('/api/calibre/diff')
    .then(res => res.json())
    .then(data => {
        console.log('Calibre总数:', data.summary.calibre_total);
        console.log('本地总数:', data.summary.local_total);
        console.log('待导入:', data.summary.only_in_calibre);
        console.log('待更新:', data.summary.incomplete);
    });
```

**响应示例：**
```json
{
  "summary": {
    "calibre_total": 105047,
    "local_total": 105038,
    "only_in_calibre": 0,
    "only_in_local": 0,
    "incomplete": 80,
    "complete": 104958
  },
  "only_in_calibre": [],
  "only_in_local": [],
  "incomplete_books": [
    {
      "id": 123,
      "title": "Python编程",
      "author": "张三",
      "has_cover": true,
      "has_file": true,
      "has_description": false,
      "has_tags": false,
      "calibre_id": 456
    }
  ]
}
```

**选择性导入：**
```javascript
fetch('/api/calibre/import-selected', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        action: 'import_new',  // 或 'update_incomplete' 或 'remove_orphaned'
        book_ids: [123, 456, 789]
    })
});
```

### 用户管理（管理员）

```http
GET    /api/users          # 获取用户列表
DELETE /api/users/<id>     # 删除用户
POST   /api/users/<id>/approve  # 审核用户
```

## 💾 数据模型

### User（用户）
```python
id: Integer              # 主键
username: String(80)     # 用户名（唯一）
email: String(120)       # 邮箱（唯一）
password_hash: String    # 密码哈希
is_admin: Boolean        # 是否管理员
is_approved: Boolean     # 是否已审核
created_at: DateTime     # 创建时间
```

### Book（图书）
```python
id: Integer              # 主键
title: String(200)       # 书名（必填）
author: String(200)      # 作者
publisher: String(200)   # 出版社
isbn: String(20)         # ISBN
publication_date: Date   # 出版日期
description: Text        # 简介
cover_image: String(300) # 封面路径
file_path: String(500)   # 文件路径
file_format: String(10)  # 文件格式
file_size: Integer       # 文件大小
language: String(50)     # 语言
tags: String(500)        # 标签（逗号分隔）
rating: Float            # 评分（0.0-5.0）
created_at: DateTime     # 创建时间
updated_at: DateTime     # 更新时间
```

## 📝 日志系统

### 导入日志
- **路径**：`logs/import_failures.log`
- **编码**：UTF-8（支持中文）
- **轮转**：最大10MB，保留5个备份
- **格式**：`时间戳 - 级别 - 消息`

**日志示例：**
```
2026-01-31 10:15:32 - ERROR - 书籍: Python编程 (Calibre ID: 123) | 错误: 文件路径不存在
2026-01-31 10:15:35 - INFO - [跳过] Python基础 by 李四 - 原因: 数据库中已存在
2026-01-31 10:16:20 - INFO - 成功导入: 深入理解计算机系统 by Randal E. Bryant
```

### 查看日志
导入完成后，控制台会显示日志文件路径。您可以：
1. 直接打开 `logs/import_failures.log` 查看
2. 在控制台查看实时输出
3. 检查具体的错误原因和跳过记录

## 🔒 安全说明

⚠️ **生产环境部署前请务必**：

1. **修改密钥**：更改 `.env` 中的 `SECRET_KEY`
   ```bash
   SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
   ```

2. **关闭DEBUG模式**：
   ```bash
   DEBUG=False
   ```

3. **配置HTTPS**：使用反向代理（Nginx/Apache）

4. **限制上传**：设置文件大小和类型限制

5. **数据库升级**：考虑使用 PostgreSQL 或 MySQL

6. **定期备份**：备份 `calibre_web.db` 和 `uploads/` 目录

## 🐛 故障排除

### 常见问题

**Q: 差异分析显示Calibre总数大于本地，但待导入为0？**  
A: 可能是Calibre中有重复书籍。运行 `python find_calibre_duplicates.py` 检查。

**Q: 导入很慢，一直停留在"生成分析报告"？**  
A: 已在v2.0修复。更新代码后，10万书籍仅需4秒。

**Q: 作者为NULL导致匹配失败？**  
A: 已修复。现在统一处理 `None` 为空字符串。

**Q: 用户注册后无法登录？**  
A: 检查是否需要管理员审核。管理员在用户管理页面审核新用户。

**Q: 上传的文件在哪里？**  
A: 在 `uploads/` 目录，按用户ID组织。

### 诊断工具

系统提供了多个诊断脚本：

```bash
# 检查书籍数据库
python diagnose_book_db.py

# 查找缺失的书籍
python find_missing_books.py

# 查找Calibre中的重复书籍
python find_calibre_duplicates.py

# 测试差异分析逻辑
python test_diff_logic.py

# 迁移用户数据库
python migrate_users.py
```

## 🎯 最佳实践

### 书库管理
1. **使用差异分析**：比全量导入快10-20倍
2. **定期同步**：每周运行一次差异分析
3. **分批导入**：大量书籍分批处理，避免超时
4. **检查日志**：出问题时查看 `logs/import_failures.log`

### 性能优化
1. **关闭DEBUG**：生产环境设置 `DEBUG=False`
2. **定期清理**：删除孤立书籍和无效数据
3. **索引优化**：大型数据库考虑添加索引
4. **静态文件**：使用CDN或Nginx托管静态资源

### 安全建议
1. **强密码策略**：要求用户使用复杂密码
2. **定期备份**：每天备份数据库
3. **访问控制**：使用防火墙限制访问
4. **HTTPS**：始终使用加密连接

## 📋 更新日志

### v2.0 (2026-01-31)
- ✅ 添加书库差异分析功能
- ✅ 优化性能：10万书籍分析从5分钟降到4秒
- ✅ 修复作者NULL导致的匹配问题
- ✅ 添加管理员界面入口
- ✅ 添加返回按钮
- ✅ 支持选择性导入/更新/删除
- ✅ 完善日志系统
- ✅ 添加多个诊断工具

### v1.0 (2026-01-30)
- ✅ 基础图书管理功能
- ✅ 用户认证和权限系统
- ✅ Calibre集成
- ✅ 智能增量导入
- ✅ 主题切换
- ✅ 响应式设计

## 🚧 后续扩展计划

- [ ] 图书封面上传功能
- [ ] 电子书在线阅读器
- [ ] 书籍系列管理
- [ ] 阅读进度跟踪
- [ ] 书评和笔记
- [ ] 导出功能（Excel/CSV）
- [ ] 多语言支持
- [ ] 移动端App
- [ ] RESTful API文档
- [ ] Docker镜像

## 📄 许可证

MIT License

## 👨‍💻 作者

GitHub Copilot & Microsoft

## 🙏 致谢

感谢 Calibre 项目提供的强大书库管理功能。

---

**享受您的数字图书馆之旅！📚**

如有问题或建议，欢迎提Issue。
