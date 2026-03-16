# AI辅助填写书籍信息功能

## 功能概述

AI辅助功能可以帮助您快速填写书籍信息，只需输入书名或关键词，AI会自动搜索并填充详细信息。

## 前置要求

### 1. 安装 Ollama

Ollama 是本地运行的大语言模型服务。

**Windows/Mac/Linux:**
```bash
# 访问 https://ollama.ai 下载安装

# 安装后拉取模型（推荐使用中文模型）
ollama pull qwen2.5:latest

# 或者使用其他模型
ollama pull llama3:latest
ollama pull mistral:latest
```

**验证安装:**
```bash
# 检查Ollama服务是否运行
curl http://localhost:11434/api/tags

# 测试模型
ollama run qwen2.5:latest "你好"
```

### 2. 安装 SearXNG（可选但推荐）

SearXNG 是开源的元搜索引擎，让AI能够搜索网络获取准确信息。

**使用Docker安装（推荐）:**
```bash
# 克隆SearXNG-Docker
git clone https://github.com/searxng/searxng-docker.git
cd searxng-docker

# 启动服务
docker-compose up -d
```

**访问测试:**
访问 `http://localhost:8080` 查看SearXNG是否正常运行。

**或者手动安装:**
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3-searx

# 配置并启动
searx-run
```

## 配置说明

在 `.env` 文件中配置AI服务：

```bash
# AI辅助功能配置
# Ollama API配置
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:latest
OLLAMA_TIMEOUT=60

# SearXNG配置（用于AI搜索网络信息）
SEARXNG_BASE_URL=http://localhost:8080
SEARXNG_ENABLED=True
```

### 配置项说明

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama服务地址 |
| `OLLAMA_MODEL` | `qwen2.5:latest` | 使用的模型名称 |
| `OLLAMA_TIMEOUT` | `60` | 请求超时时间（秒） |
| `SEARXNG_BASE_URL` | `http://localhost:8080` | SearXNG服务地址 |
| `SEARXNG_ENABLED` | `True` | 是否启用网络搜索 |

### 推荐模型配置

**中文书籍（推荐）:**
```bash
OLLAMA_MODEL=qwen2.5:latest        # 通义千问，中文理解好
```

**英文书籍:**
```bash
OLLAMA_MODEL=llama3:latest         # Meta的Llama3
OLLAMA_MODEL=mistral:latest        # Mistral，速度快
```

**平衡性能:**
```bash
OLLAMA_MODEL=qwen2.5:7b           # 较小模型，速度快
OLLAMA_MODEL=qwen2.5:14b          # 中等模型
OLLAMA_MODEL=qwen2.5:32b          # 大模型，准确度高
```

## 使用方法

### 1. 在编辑图书页面使用

1. 打开任意图书的编辑页面
2. 找到"🤖 AI辅助填写"按钮
3. 在弹出的对话框中输入书籍关键词（如：书名、作者名、ISBN等）
4. 点击"搜索"
5. AI会自动填充以下信息：
   - 书名
   - 作者
   - 出版社
   - ISBN
   - 出版日期
   - 书籍简介
   - 语言
   - 标签

### 2. 工作流程

```
用户输入关键词
    ↓
[启用SearXNG] → 搜索网络获取书籍信息（前5条结果）
    ↓
将搜索结果和关键词发送给Ollama
    ↓
Ollama分析并生成结构化的书籍信息
    ↓
自动填充到表单中
    ↓
用户可以修改后保存
```

### 3. 使用技巧

**精确搜索：**
- 输入完整书名：`深入理解计算机系统`
- 书名+作者：`深入理解计算机系统 Randal E. Bryant`
- ISBN：`9787111544937`

**模糊搜索：**
- 主题+类型：`Python编程入门`
- 关键词：`机器学习 实战`

**提高准确度：**
1. 尽量提供完整信息
2. 启用SearXNG获取网络数据
3. 使用更大的模型（如qwen2.5:32b）
4. 中文书籍用中文模型，英文书籍用英文模型

## API接口

### 搜索书籍信息

```http
POST /api/ai/search-book-info
Content-Type: application/json

{
  "query": "深入理解计算机系统"
}
```

**响应示例：**
```json
{
  "success": true,
  "book_info": {
    "title": "深入理解计算机系统",
    "author": "Randal E. Bryant, David R. O'Hallaron",
    "publisher": "机械工业出版社",
    "isbn": "9787111544937",
    "publication_date": "2016-11-01",
    "description": "本书从程序员的视角详细阐述计算机系统的本质概念...",
    "language": "中文",
    "tags": "计算机科学,系统编程,经典教材"
  },
  "source": "ai_with_search"
}
```

### 获取AI配置状态

```http
GET /api/ai/config
```

**响应示例：**
```json
{
  "ollama": {
    "status": "connected",
    "base_url": "http://localhost:11434",
    "model": "qwen2.5:latest",
    "available_models": [
      "qwen2.5:latest",
      "llama3:latest"
    ]
  },
  "searxng": {
    "status": "connected",
    "enabled": true,
    "base_url": "http://localhost:8080"
  }
}
```

## 故障排除

### Ollama无法连接

**错误信息：** `无法连接到Ollama服务`

**解决方法：**
1. 检查Ollama是否运行：
   ```bash
   curl http://localhost:11434/api/tags
   ```

2. 检查端口是否正确
3. 如果在远程服务器，修改 `OLLAMA_BASE_URL`

### 模型未找到

**错误信息：** `model not found`

**解决方法：**
```bash
# 拉取模型
ollama pull qwen2.5:latest

# 查看已安装的模型
ollama list
```

### SearXNG连接失败

**错误信息：** SearXNG status: `disconnected`

**解决方法：**
1. 检查SearXNG是否运行：
   ```bash
   curl http://localhost:8080
   ```

2. 如果不需要网络搜索，可以禁用：
   ```bash
   SEARXNG_ENABLED=False
   ```

### AI响应超时

**错误信息：** `AI请求超时`

**解决方法：**
1. 增加超时时间：
   ```bash
   OLLAMA_TIMEOUT=120
   ```

2. 使用更小的模型
3. 检查服务器性能

### 返回数据格式错误

**错误信息：** `AI返回的数据格式错误`

**解决方法：**
1. 更换模型（qwen2.5对结构化输出支持更好）
2. 查看控制台日志中的原始响应
3. 调整提示词（在app.py中修改system_prompt）

## 性能优化

### 响应速度

| 模型大小 | 响应时间 | 准确度 | 推荐场景 |
|---------|---------|--------|---------|
| 7B | 2-5秒 | 中等 | 快速填充 |
| 14B | 5-10秒 | 良好 | 日常使用 |
| 32B | 10-20秒 | 优秀 | 重要书籍 |

### GPU加速

**启用GPU（NVIDIA）：**
```bash
# 安装CUDA版本的Ollama
# Ollama会自动检测并使用GPU

# 检查GPU使用情况
nvidia-smi
```

**CPU优化：**
```bash
# 设置线程数
export OLLAMA_NUM_THREADS=8
```

## 安全建议

1. **不要暴露端口**：Ollama和SearXNG仅本地使用
2. **API访问控制**：已限制为登录用户
3. **数据验证**：AI生成的数据需要人工确认
4. **隐私保护**：数据不会发送到外部服务

## 最佳实践

1. **批量导入时**：先使用AI填充基本信息，后续可以批量修正
2. **关键书籍**：使用大模型+SearXNG获取最准确信息
3. **快速录入**：使用小模型快速填充，后续手动修正细节
4. **定期更新模型**：`ollama pull qwen2.5:latest` 获取最新版本

## 示例场景

### 场景1：添加新书

```
1. 点击"添加图书"
2. 点击"AI辅助填写"
3. 输入："深入理解计算机系统"
4. AI自动填充所有字段
5. 确认后保存
```

### 场景2：补全信息

```
1. 发现某本书信息不全
2. 点击"编辑"
3. 点击"AI辅助填写"
4. 输入书名
5. AI补充缺失的字段
6. 保存更新
```

### 场景3：外文书籍

```
1. 输入："The Pragmatic Programmer"
2. 切换模型为 llama3:latest
3. AI填充英文书籍信息
4. 自动翻译简介（如使用qwen2.5）
```

---

**版本**: v2.0  
**更新日期**: 2026年1月31日
