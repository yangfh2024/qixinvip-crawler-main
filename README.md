# 启信宝企业数据爬虫

> **当前版本**: v2.0.0 | **状态**: 稳定可用

基于 Playwright + FastAPI 的启信宝企业信息查询服务，提供 **HTTP API 高级搜索**（毫秒级，无需浏览器）和 **Playwright 浏览器爬取**（完整工商信息）双模式。

## 系统架构

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
│  HTTP 请求    │ ──▶ │  FastAPI 服务     │ ──▶ │  高级搜索 API │
│  (curl/代码)  │     │  (port 8004)     │     │  (毫秒级响应) │
└──────────────┘     └──────────────────┘     └──────────────┘
                            │
                            ▼
                     ┌──────────────────┐
                     │  Playwright 浏览器 │
                     │  (单公司详情爬取)   │
                     └──────────────────┘
```

**典型流程：** 先用高级搜索 API 筛选目标企业列表 → 再对目标企业逐条爬取详细信息。

## 特性

- **双模式数据获取**：高级搜索 API（毫秒级） + 浏览器爬取（完整工商信息）
- **多维筛选**：支持行业、地区、注册资本、成立年限、经营状态等 15+ 筛选条件
- **异步批量任务**：提交公司列表后异步处理，支持进度查询和结果下载
- **VIP 权限利用**：支持 Cookie 登录和扫码登录
- **一键部署**：Windows 双击 `.bat`，macOS/Linux 运行 `.sh`
- **自动限速与重试**：内置请求频率控制，WAF 拦截自动检测和重试
- **Swagger 交互式文档**：访问 `http://localhost:8004/docs` 即可在线调试

## 系统要求

- Python 3.10 ~ 3.12（3.13/3.14 不兼容）
- Windows / macOS / Linux
- 稳定的网络连接
- 启信宝 VIP 账号（用于获取 Cookie）

## 安装部署

### 方式一：一键部署（推荐）

**Windows：** 双击 `setup.bat`，等待 3~10 分钟完成安装。

**macOS / Linux：**
```bash
bash setup.sh
```

### 方式二：手动部署

```bash
# 1. 创建虚拟环境
python3 -m venv venv

# 2. 安装依赖（Windows）
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python -m playwright install chromium

# 2. 安装依赖（macOS / Linux）
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## 配置 Cookie

### 方式 A：扫码登录（推荐）

```bash
# Windows 双击 qr_login.bat，或终端执行：
python qr_login.py
```

在弹出的浏览器窗口中用启信宝 App 扫码登录，脚本自动保存 Cookie 到 `cookie.txt`。

### 方式 B：手动从浏览器复制

1. Chrome 打开 [qixin.com](https://www.qixin.com) 并登录 VIP 账号
2. `F12` → **Network** 标签 → 勾选 **Preserve log**
3. 搜索任意公司，在 Network 中找到 API 请求
4. 点击该请求 → **Request Headers** → 找到 `cookie:` 行 → **右键 → Copy value**
5. 粘贴到 `cookie.txt` 文件覆盖保存

> **提示：** 从 Network 复制的 Cookie 包含 `acw_tc`（WAF 令牌，约 30 分钟有效），API 提示过期时重新复制一次即可。

## 启动服务

### Windows

双击 `start.bat`，终端显示：

```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8004
```

### 命令行（所有平台）

```bash
venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8004
```

浏览器访问 `http://localhost:8004/docs` 查看交互式 API 文档。

## API 接口一览

| 接口 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查，查看服务和 Cookie 状态 |
| `/crawl/advanced` | POST | 高级搜索（毫秒级，无需浏览器） |
| `/crawl/single` | POST | 爬取单个公司完整信息 |
| `/crawl/batch` | POST | 批量爬取（异步任务） |
| `/crawl/task/{task_id}` | GET | 查询批量任务进度 |
| `/crawl/download/{filename}` | GET | 下载结果文件 |
| `/cookie/check` | POST | 检查 Cookie 有效性 |
| `/cookie/update` | POST | 在线更新 Cookie |

## 快速上手

### 健康检查

```bash
curl http://localhost:8004/health
```

返回示例：
```json
{"status":"ok","cookie_valid":true,"cookie_count":9,"version":"2.0.0"}
```

### 高级搜索（筛选企业列表）

```bash
curl -X POST http://localhost:8004/crawl/advanced \
  -H "Content-Type: application/json" \
  -d '{"keyword":"科技","status":[1],"province":["44"],"reg_capi":["1000-"],"page":1,"page_size":10}'
```

### 爬取单个公司详情

```bash
curl -X POST http://localhost:8004/crawl/single \
  -H "Content-Type: application/json" \
  -d '{"company_name": "腾讯科技（深圳）有限公司"}'
```

### 检查 Cookie

```bash
curl -X POST http://localhost:8004/cookie/check
```

### 更新 Cookie

```bash
curl -X POST "http://localhost:8004/cookie/update?cookie_str=acw_tc=xxx;%20pdid=s%3Axxx"
```

## 高级搜索筛选参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `keyword` | 企业关键词 | `"科技"` |
| `status` | 经营状态 | `[1]`（存续） |
| `province` | 省份代码 | `["44"]`（广东） |
| `industry` | 行业代码 | `["I65"]`（软件） |
| `reg_capi` | 注册资本范围 | `["1000-"]`（1000万以上） |
| `establish` | 成立年限 | `["1-5y"]`（1-5年） |
| `company_type` | 公司类型 | `["有限责任公司"]` |
| `org_type` | 组织类型 | `["企业"]` |
| `listing` | 上市状态 | `["a-share"]`（A股） |
| `page` | 页码（最大 1000） | `1` |
| `page_size` | 每页条数（最大 100） | `20` |

完整参数说明见 [api_docs.md](api_docs.md)。

## 项目结构

```
qixinvip-crawler/
├── app/
│   ├── main.py              # FastAPI 服务入口
│   └── schemas.py           # API 请求/响应数据模型
├── main.py                  # CLI 命令行版入口（三种模式）
├── crawler.py               # 爬虫核心逻辑
├── browser.py               # Playwright 浏览器管理
├── exporter.py              # 数据导出（Excel/CSV）
├── utils.py                 # 工具函数（含签名算法）
├── qr_login.py              # 扫码登录工具
├── config.json              # 运行时配置
├── cookie.txt               # Cookie 文件（扫码登录自动生成）
├── selectors.json           # CSS 选择器配置
├── requirements.txt         # Python 依赖
├── api_docs.md              # 完整 API 接口文档
├── README.md                # 本文件
├── setup.bat / setup.sh     # 一键部署脚本
├── start.bat / start.sh     # 启动 API 服务
├── qr_login.bat             # 扫码登录快捷方式
└── output/                  # 爬取结果输出目录
```

## 爬取字段说明

### 浏览器爬取（完整信息）
- 公司名称、法定代表人、注册资本、成立日期、经营状态
- 统一社会信用代码、经营范围、所属行业、纳税人资质
- 联系电话、企业邮箱、注册地址
- 股东信息、主要人员

### 高级搜索 API（列表信息）
- 公司名称、法定代表人、注册资本、成立日期、经营状态
- 统一社会信用代码、联系电话、邮箱、地址、行业

## 常见问题

**端口被占用？**
```bash
venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
```

**高级搜索返回 total_num=0？**
- 筛选项参数无效——检查是否传了 `"string"` 等错误值
- Cookie 过期——重新扫码登录或复制 Cookie

**Cookie 多久更新一次？**
- `acw_tc`（WAF 令牌）约 30 分钟有效
- `pdid`（登录会话）约 7~30 天
- API 提示过期时重新复制完整 Cookie 即可

**爬取返回 N/A？**
- Cookie 过期——更新后重试
- 公司名称不准确——使用全称
- 网站结构变化——需更新 CSS 选择器

**批量爬取如何拿结果？**
1. `POST /crawl/batch` → 获取 `task_id`
2. 轮询 `GET /crawl/task/{task_id}` 直到 `status="completed"`
3. 根据 `result_file` 调用 `GET /crawl/download/{filename}` 下载

## 注意事项

### 法律合规
- 本工具仅用于个人研究、学习目的
- 使用自己的 VIP 账号，访问有权限的内容
- 遵守启信宝服务条款
- 不得用于商业目的或转售数据
- 不得过度频繁请求，避免对服务器造成压力

### 使用建议
- 先用高级搜索 API 筛选目标企业，再对需要的企业逐条爬取
- 保持合理的请求频率，内置限速机制会自动调整
- 批量任务数建议控制在 200 以内

## 许可证

本项目仅供学习交流使用，请勿用于非法用途。使用本工具产生的一切后果由使用者自行承担。
