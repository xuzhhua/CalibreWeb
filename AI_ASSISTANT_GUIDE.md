# AI辅助填写书籍信息功能

## 功能概述

AI辅助功能可以帮助您快速填写书籍信息，只需输入书名或关键词，AI会自动搜索并填充详细信息。

## 前置要求

AI辅助功能支持两种本地大语言模型服务，**二选一**即可：

### 方式A：安装 Ollama

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

### 方式B：安装 LM Studio

LM Studio 提供图形界面，内置 OpenAI 兼容 API，默认端口为 1234。

**Windows/Mac/Linux:**
```bash
# 访问 https://lmstudio.ai 下载安装

# 在 LM Studio 中：
# 1. 搜索并下载模型（如 Qwen2.5、Llama3 等）
# 2. 加载模型
# 3. 在"开发者"选项卡中启动本地服务器（默认端口 1234）
```

**验证安装:**
```bash
# 检查LM Studio服务是否运行
curl http://localhost:1234/v1/models
```

### 安装 SearXNG（可选但推荐）

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

在 `.env` 文件中配置AI服务。**AI_PROVIDER 决定使用哪个服务，ollama 和 lmstudio 二选一。**

### 使用 Ollama 的配置

```bash
# AI服务提供商（二选一）
AI_PROVIDER=ollama

# Ollama配置
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:latest
OLLAMA_TIMEOUT=60

# SearXNG配置（用于AI搜索网络信息）
SEARXNG_BASE_URL=http://localhost:8080
SEARXNG_ENABLED=True
```

### 使用 LM Studio 的配置

```bash
# AI服务提供商（二选一）
AI_PROVIDER=lmstudio

# LM Studio配置（OpenAI兼容API，默认端口1234）
LMSTUDIO_BASE_URL=http://localhost:1234
LMSTUDIO_MODEL=auto          # 'auto' 自动使用已加载的模型，或填写具体模型名称
LMSTUDIO_TIMEOUT=60

# SearXNG配置
SEARXNG_BASE_URL=http://localhost:8080
SEARXNG_ENABLED=True
```

### 配置项说明

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `AI_PROVIDER` | `ollama` | AI服务提供商：`ollama` 或 `lmstudio`（二选一） |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama服务地址 |
| `OLLAMA_MODEL` | `qwen2.5:latest` | Ollama使用的模型名称 |
| `OLLAMA_TIMEOUT` | `60` | Ollama请求超时时间（秒） |
| `LMSTUDIO_BASE_URL` | `http://localhost:1234` | LM Studio服务地址 |
| `LMSTUDIO_MODEL` | `auto` | LM Studio模型名称，`auto` 自动使用已加载模型 |
| `LMSTUDIO_TIMEOUT` | `60` | LM Studio请求超时时间（秒） |
| `SEARXNG_BASE_URL` | `http://localhost:8080` | SearXNG服务地址 |
| `SEARXNG_ENABLED` | `True` | 是否启用网络搜索 |

### 推荐模型配置

#### Ollama

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

#### LM Studio

在 LM Studio 中搜索并下载模型后，在 `.env` 中配置：
```bash
# 使用当前已加载的模型
LMSTUDIO_MODEL=auto

# 或指定具体模型名称
LMSTUDIO_MODEL=qwen2.5-7b-instruct
LMSTUDIO_MODEL=llama-3.2-3b-instruct
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
将搜索结果和关键词发送给AI服务（Ollama 或 LM Studio）
    ↓
AI分析并生成结构化的书籍信息
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

**响应示例（使用 Ollama 时）：**
```json
{
  "provider": "ollama",
  "llm": {
    "status": "connected",
    "base_url": "http://localhost:11434",
    "model": "qwen2.5:latest",
    "available_models": [
      "qwen2.5:latest",
      "llama3:latest"
    ]
  },
  "ollama": {
    "status": "connected",
    "base_url": "http://localhost:11434",
    "model": "qwen2.5:latest",
    "available_models": ["qwen2.5:latest", "llama3:latest"]
  },
  "searxng": {
    "status": "connected",
    "enabled": true,
    "base_url": "http://localhost:8080"
  }
}
```

**响应示例（使用 LM Studio 时）：**
```json
{
  "provider": "lmstudio",
  "llm": {
    "status": "connected",
    "base_url": "http://localhost:1234",
    "model": "auto",
    "available_models": ["qwen2.5-7b-instruct"]
  },
  "lmstudio": {
    "status": "connected",
    "base_url": "http://localhost:1234",
    "model": "auto",
    "available_models": ["qwen2.5-7b-instruct"]
  },
  "searxng": {
    "status": "connected",
    "enabled": true,
    "base_url": "http://localhost:8080"
  }
}
```

## 故障排除

### AI服务无法连接

**错误信息：** `无法连接到AI服务` 或 `无法连接到Ollama服务`

**解决方法：**

**Ollama：**
1. 检查Ollama是否运行：
   ```bash
   curl http://localhost:11434/api/tags
   ```
2. 检查端口是否正确
3. 如果在远程服务器，修改 `OLLAMA_BASE_URL`

**LM Studio：**
1. 确保 LM Studio 已启动并加载了模型
2. 在"开发者"选项卡中确认本地服务器已启动（默认端口 1234）
3. 验证连接：
   ```bash
   curl http://localhost:1234/v1/models
   ```
4. 检查端口是否正确，修改 `LMSTUDIO_BASE_URL`

### 模型未找到

**Ollama：**
```bash
ollama pull qwen2.5:latest
ollama list
```

**LM Studio：**
1. 在 LM Studio 中搜索并下载所需模型
2. 确保模型已加载（在聊天界面中选择并加载模型）
3. 将 `LMSTUDIO_MODEL` 设为 `auto` 自动检测已加载的模型
4. 或填写具体的模型名称（如 `qwen2.5-7b-instruct`）

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
   # Ollama
   OLLAMA_TIMEOUT=120
   # LM Studio
   LMSTUDIO_TIMEOUT=120
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

**Ollama：**
```bash
# Ollama会自动检测并使用GPU
# 检查GPU使用情况
nvidia-smi

# CPU优化 - 设置线程数
export OLLAMA_NUM_THREADS=8
```

**LM Studio：**
LM Studio 在图形界面中自动管理 GPU 加速，无需额外配置。

## 安全建议

1. **不要暴露端口**：AI服务和SearXNG仅本地使用
2. **API访问控制**：已限制为登录用户
3. **数据验证**：AI生成的数据需要人工确认
4. **隐私保护**：数据不会发送到外部服务（Ollama/LM Studio均为本地运行）

## 切换 AI 服务

如果需要从 Ollama 切换到 LM Studio（或反过来），只需修改 `.env` 中的 `AI_PROVIDER`：

```bash
# 从 Ollama 切换到 LM Studio
AI_PROVIDER=lmstudio

# 从 LM Studio 切换回 Ollama
AI_PROVIDER=ollama
```

修改后重启应用即可生效。

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
2. 使用英文模型（如 Llama3 或 Mistral）
3. AI填充英文书籍信息
```
```

---

**版本**: v2.0  
**更新日期**: 2026年1月31日
