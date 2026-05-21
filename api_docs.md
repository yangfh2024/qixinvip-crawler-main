# 启信宝爬虫 API 接口文档

**基础地址：** `http://localhost:8000`
**Content-Type：** `application/json`

---

## 接口一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/crawl/single` | 爬取单个公司（需浏览器） |
| POST | `/crawl/advanced` | 高级搜索（无需浏览器） |
| POST | `/crawl/batch` | 批量爬取（异步，需浏览器） |
| GET | `/crawl/task/{task_id}` | 查询批量任务状态 |
| GET | `/crawl/download/{filename}` | 下载结果文件 |
| POST | `/cookie/check` | 检查 Cookie 状态 |
| POST | `/cookie/update` | 更新 Cookie |

---

## 1. 健康检查

```
GET /health
```

检查服务运行状态和 Cookie 配置。

### 返回示例

```json
{
  "status": "ok",
  "browser_ready": false,
  "cookie_valid": true,
  "cookie_count": 9,
  "version": "2.0.0",
  "timestamp": "2026-05-21T11:00:00.000000"
}
```

### 返回字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | string | 服务状态 `"ok"` |
| `browser_ready` | bool | 浏览器是否已启动（按需懒加载） |
| `cookie_valid` | bool | Cookie 是否包含登录凭证 |
| `cookie_count` | int | 已配置的 Cookie 数量 |
| `version` | string | API 版本号 |
| `timestamp` | string | 当前时间 |

---

## 2. 爬取单个公司

```
POST /crawl/single
```

通过 Playwright 浏览器打开启信宝，搜索公司并提取详细信息。**首次调用会自动启动浏览器，耗时较长。**

### 请求参数

| 参数 | 类型 | 必填 | 说明 | 默认值 |
|------|------|------|------|--------|
| `company_name` | string | 是 | 公司全称或关键词 | - |
| `timeout` | int | 否 | 超时时间（秒），范围 30-300 | 120 |

### 请求示例

```bash
curl -X POST http://localhost:8001/crawl/single \
  -H "Content-Type: application/json" \
  -d '{"company_name": "腾讯科技（深圳）有限公司"}'
```

```python
import requests

resp = requests.post("http://localhost:8001/crawl/single", json={
    "company_name": "腾讯科技（深圳）有限公司",
    "timeout": 120,
})
data = resp.json()
```

### 返回示例

```json
{
  "success": true,
  "data": {
    "company_name": "腾讯科技（深圳）有限公司",
    "legal_person": "马化腾",
    "registered_capital": "200万美元",
    "establish_date": "2000-02-24",
    "status": "存续",
    "organization_code": "91440300708722081F",
    "business_scope": "从事计算机软硬件...",
    "industry": "软件和信息技术服务业",
    "taxpayer_type": "一般纳税人",
    "phone": "0755-86013388",
    "email": "tencent@tencent.com",
    "address": "深圳市南山区粤海街道麻岭社区科技中一路腾讯大厦",
    "shareholders": "腾讯控股有限公司",
    "executives": "马化腾(董事长), 刘炽平(董事)",
    "crawl_time": "2026-05-21 11:00:00"
  }
}
```

### 返回字段

| 字段 | 说明 |
|------|------|
| `success` | 是否成功 |
| `data.company_name` | 公司名称 |
| `data.legal_person` | 法定代表人 |
| `data.registered_capital` | 注册资本 |
| `data.establish_date` | 成立日期 |
| `data.status` | 经营状态 |
| `data.organization_code` | 统一社会信用代码 |
| `data.business_scope` | 经营范围 |
| `data.industry` | 所属行业 |
| `data.taxpayer_type` | 纳税人资质 |
| `data.phone` | 联系电话 |
| `data.email` | 企业邮箱 |
| `data.address` | 注册地址 |
| `data.shareholders` | 股东信息（多个用分号分隔） |
| `data.executives` | 主要人员（多个用分号分隔） |
| `data.crawl_time` | 爬取时间 |
| `error` | 失败时的错误信息 |

### 注意事项

- **首次请求会启动浏览器**，可能需要 5-10 秒初始化
- Cookie 过期会导致爬取失败，请先通过 `/cookie/check` 验证
- 单个公司爬取通常需要 3-8 秒

---

## 3. 高级搜索

```
POST /crawl/advanced
```

直接调用启信宝 API 进行多维度企业搜索，**无需启动浏览器**，响应时间通常 0.1-0.5 秒。

### 请求参数

| 参数 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|--------|
| `keyword` | string | 否 | 关键词（企业名、人名、品牌） | `"科技"` |
| `status` | int[] | 否 | 经营状态（多选） | `[1]`、`[1,2]` |
| `province` | string[] | 否 | 省份地区代码 | `["44"]`（广东） |
| `industry` | string[] | 否 | 行业分类代码 | `["I65"]`（软件） |
| `reg_capi` | string[] | 否 | 注册资本 | `["1000-"]` |
| `paid_capi` | string[] | 否 | 实缴资本 | `["has"]` |
| `establish` | string[] | 否 | 成立年限 | `["1-5y"]` |
| `company_type` | string[] | 否 | 公司类型 | `["有限责任公司"]` |
| `org_type` | string[] | 否 | 组织类型 | `["listed"]` |
| `employee` | string[] | 否 | 员工人数 | `["100-499"]` |
| `insured` | string[] | 否 | 参保人数 | `["<50"]` |
| `listing` | string[] | 否 | 上市状态 | `["a-share"]` |
| `scale` | string[] | 否 | 规上企业 | `["high-tech"]` |
| `page` | int | 否 | 页码（默认 1） | `1` |
| `page_size` | int | 否 | 每页条数（默认 10，最大 100） | `20` |

> **注意：** 不用的筛选项不要传，传 `null` 或不传即可。传无效值（如 `["string"]`）会导致匹配不到数据。

### 各枚举字段可选值

#### status — 经营状态

| 值 | 含义 |
|----|------|
| `1` | 存续 |
| `2` | 注销 |
| `3` | 吊销 |
| `4` | 撤销 |
| `5` | 迁出 |
| `6` | 设立中 |
| `7` | 清算中 |
| `8` | 停业 |

#### reg_capi — 注册资本

| 值 | 含义 |
|----|------|
| `"0-100"` | 0万 - 100万 |
| `"100-200"` | 100万 - 200万 |
| `"200-500"` | 200万 - 500万 |
| `"500-1000"` | 500万 - 1000万 |
| `"1000-"` | 1000万以上 |

#### paid_capi — 实缴资本

| 值 | 含义 |
|----|------|
| `"has"` | 有实缴资本 |
| `"no"` | 无实缴资本 |
| `"0-100"` | 0万 - 100万 |
| `"100-200"` | 100万 - 200万 |
| `"200-500"` | 200万 - 500万 |
| `"500-1000"` | 500万 - 1000万 |
| `"1000-5000"` | 1000万 - 5000万 |
| `"5000-"` | 5000万以上 |

#### establish — 成立年限

| 值 | 含义 |
|----|------|
| `"1y"` | 1年内 |
| `"1-5y"` | 1-5年 |
| `"5-10y"` | 5-10年 |
| `"10-15y"` | 10-15年 |
| `"15y+"` | 15年以上 |

#### company_type — 公司类型（可多选）

```
"国有企业", "集体所有制企业", "股份合作企业", "联营企业",
"有限责任公司", "普通合伙", "有限合伙", "股份有限公司",
"私营企业", "民营企业", "个体工商户", "港澳台投资",
"外商投资", "全民所有制", "个人独资企业",
"农民专业合作社（联合社）", "其他"
```

#### org_type — 组织类型（可多选）

| 值 | 含义 |
|----|------|
| `"new三板"` | 新三板 |
| `"listed"` | 上市公司 |
| `"social"` | 社会组织 |
| `"law-firm"` | 律师事务所 |
| `"hk"` | 香港企业 |
| `"tw"` | 台湾企业 |
| `"government"` | 机关单位 |
| `"institution"` | 事业单位 |
| `"school"` | 学校 |

#### employee / insured — 员工/参保人数

| 值 | 含义 |
|----|------|
| `"<50"` | 小于50人 |
| `"50-99"` | 50-99人 |
| `"100-499"` | 100-499人 |
| `"500+"` | 500人以上 |

#### listing — 上市状态

| 值 | 含义 |
|----|------|
| `"a-share"` | A股 |
| `"us-stock"` | 中概股 |
| `"hk-stock"` | 港股 |
| `"star-market"` | 科创板 |
| `"new三板"` | 新三板 |

#### scale — 规上企业

| 值 | 含义 |
|----|------|
| `"construction"` | 有资质的建筑业 |
| `"service"` | 规模以上服务业 |
| `"industrial"` | 规模以上工业 |
| `"retail-wholesale"` | 限额以上批发和零售业 |
| `"real-estate"` | 房地产开发经营业 |
| `"accommodation-catering"` | 限额以上住宿和餐饮业 |

### 请求示例

#### 示例 1：关键词搜索

```bash
curl -X POST http://localhost:8001/crawl/advanced \
  -H "Content-Type: application/json" \
  -d '{"keyword":"科技","page":1,"page_size":10}'
```

#### 示例 2：多维度筛选

```python
import requests

resp = requests.post("http://localhost:8001/crawl/advanced", json={
    "keyword": "科技",       # 关键词
    "status": [1],           # 存续
    "province": ["44"],      # 广东
    "reg_capi": ["1000-"],   # 注册资本 1000 万以上
    "page": 1,
    "page_size": 20,
})
```

#### 示例 3：A 股上市制造企业

```python
resp = requests.post("http://localhost:8001/crawl/advanced", json={
    "listing": ["a-share"],
    "industry": ["C"],       # 制造业
    "employee": ["500+"],    # 员工 500 人以上
    "page": 1,
    "page_size": 10,
})
```

#### 示例 4：有限责任公司 + 成立 1-5 年

```python
resp = requests.post("http://localhost:8001/crawl/advanced", json={
    "company_type": ["有限责任公司"],
    "status": [1],
    "establish": ["1-5y"],
    "province": ["44"],      # 广东
    "page": 1,
    "page_size": 10,
})
```

### 返回格式

```json
{
  "success": true,
  "total": "1000万+",
  "total_num": 14781450,
  "search_time": 0.21,
  "has_next": true,
  "page": 1,
  "items": [
    {
      "company_name": "蓝思科技股份有限公司",
      "legal_person": "周群飞",
      "registered_capital": "528466.4981万元",
      "establish_date": "2006-12-21",
      "status": "存续",
      "credit_code": "91430000796852865Y",
      "phone": "0731-83285001",
      "email": "lsgf@hnlens.com",
      "address": "湖南浏阳生物医药园",
      "industry": "其他电子器件制造",
      "eid": "353d7119-..."
    }
  ]
}
```

### 返回字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | bool | 是否成功 |
| `total` | string | 格式化总数（如 `"1000万+"`） |
| `total_num` | int | 精确总数 |
| `search_time` | float | 搜索耗时（秒） |
| `has_next` | bool | 是否有下一页 |
| `page` | int | 当前页码 |
| `items[]` | array | 企业列表 |
| `items[].company_name` | string | 企业名称 |
| `items[].legal_person` | string | 法定代表人 |
| `items[].registered_capital` | string | 注册资本 |
| `items[].establish_date` | string | 成立日期 |
| `items[].status` | string | 经营状态 |
| `items[].credit_code` | string | 统一社会信用代码 |
| `items[].phone` | string | 联系电话 |
| `items[].email` | string | 企业邮箱 |
| `items[].address` | string | 注册地址 |
| `items[].industry` | string | 所属行业 |
| `items[].eid` | string | 企业唯一 ID（用于后续详情查询） |
| `error` | string/null | 错误信息 |

### 错误码说明

| 响应 | 含义 |
|------|------|
| `success: true, total_num: >0` | 正常返回结果 |
| `success: true, total_num: 0` | 无匹配数据（或 Cookie 过期，会自动检测并提示） |
| `success: false, error: "Cookie 已过期..."` | Cookie 失效，需要重新登录更新 |

---

## 4. 批量爬取

```
POST /crawl/batch
```

异步批量爬取多个公司。**需要浏览器支持**，提交后立即返回 `task_id`，通过查询接口获取进度和结果。

### 请求参数

| 参数 | 类型 | 必填 | 说明 | 默认值 |
|------|------|------|------|--------|
| `companies` | string[] | 是 | 公司名称列表（1-200 个） | - |
| `export_format` | string | 否 | 导出格式：`"excel"` 或 `"csv"` | `"excel"` |
| `timeout` | int | 否 | 单个公司超时（秒），范围 30-300 | 120 |

### 请求示例

```python
import requests

resp = requests.post("http://localhost:8001/crawl/batch", json={
    "companies": [
        "腾讯科技（深圳）有限公司",
        "阿里巴巴（中国）有限公司",
        "百度在线网络技术公司"
    ],
    "export_format": "excel",
})
task = resp.json()
# {"task_id": "a1b2c3d4e5f6", "status": "queued", "message": "已加入队列，共 3 个公司"}
task_id = task["task_id"]
```

### 返回字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_id` | string | 任务 ID（12 位十六进制） |
| `status` | string | `"queued"` |
| `message` | string | 提示信息 |

---

## 5. 查询任务状态

```
GET /crawl/task/{task_id}
```

查询批量爬取任务的执行进度。轮询此接口直到 `status` 变为 `"completed"` 或 `"failed"`。

### 请求示例

```python
import time

# 轮询直到完成
while True:
    resp = requests.get(f"http://localhost:8001/crawl/task/{task_id}")
    status = resp.json()
    print(f"[{status['status']}] {status['progress']}/{status['total']}")
    
    if status['status'] in ('completed', 'failed'):
        break
    time.sleep(3)

# 下载结果文件
if status['status'] == 'completed' and status['result_file']:
    download_url = f"http://localhost:8001/crawl/download/{status['result_file']}"
    print(f"下载地址: {download_url}")
```

### 返回字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_id` | string | 任务 ID |
| `status` | string | `"queued"` / `"running"` / `"completed"` / `"failed"` |
| `progress` | int | 已完成数量 |
| `total` | int | 总数量 |
| `result_file` | string/null | 结果文件名（完成后有值） |
| `error` | string/null | 失败时的错误信息 |

---

## 6. 下载结果文件

```
GET /crawl/download/{filename}
```

下载批量爬取生成的结果文件（Excel 或 CSV）。

### 请求示例

```bash
curl -O http://localhost:8001/crawl/download/qixinbao_companies_20260521_120000.xlsx
```

---

## 7. 检查 Cookie 状态

```
POST /cookie/check
```

检查当前配置的 Cookie 是否有效（包含登录凭证）。

### 返回示例

```json
{
  "valid": true,
  "cookie_count": 9,
  "has_auth_cookies": true,
  "message": "Cookie 有效，包含登录凭证"
}
```

### 返回字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `valid` | bool | 是否包含登录凭证 |
| `cookie_count` | int | Cookie 条目数 |
| `has_auth_cookies` | bool | 是否有认证 Cookie |
| `message` | string | 文本描述 |

---

## 8. 更新 Cookie

```
POST /cookie/update
```

手动更新 Cookie 字符串，直接写入 `cookie.txt` 文件，下次请求生效。

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `cookie_str` | string | 是 | 完整的 Cookie 字符串（长度 >= 10） |

### 请求示例

```bash
curl -X POST "http://localhost:8001/cookie/update?cookie_str=acw_tc=xxx;%20pdid=s%3Axxx"
```

```python
requests.post("http://localhost:8001/cookie/update", params={
    "cookie_str": "acw_tc=xxx; pdid=s%3Axxx"
})
```

### 返回示例

```json
{
  "success": true,
  "message": "Cookie 已更新",
  "length": 256
}
```

---

## 通用说明

### Cookie 配置

Cookie 有两种配置方式：

1. **`cookie.txt`**（推荐）：从浏览器 DevTools → Network → 任意 API 请求的 Request Headers 中复制整段 Cookie 字符串
2. **`config.json`** 的 `"cookie"` 字段

`cookie.txt` 优先级高于 `config.json`。

Cookie 中的 `acw_tc`（阿里云 WAF 令牌）约 30 分钟过期，过期后需要重新获取。

### 分页说明

| 端点 | 最大页码 | 每页最大条数 |
|------|----------|-------------|
| `/crawl/advanced` | 1000 | 100 |
| `/crawl/batch` | 单次最多 200 个公司 | - |

### 错误处理

所有接口统一返回格式：

```json
// 业务成功
{ "success": true, "data": {...} }

// 业务失败（HTTP 200）
{ "success": false, "error": "错误描述" }

// 请求错误（HTTP 4xx）
{ "detail": "错误描述" }
```

### 数据流方案

1. 使用 `/crawl/advanced` 搜索企业列表，获取 `eid`（企业唯一 ID）
2. 需要详情时，通过 `/crawl/single` 传入企业名称获取详细信息
3. 大批量数据使用 `/crawl/batch` 异步处理

### 请求限速

高级搜索接口 `/crawl/advanced` 内置自适应请求限速：
- 默认请求间隔：**300ms**
- 触发限速后自动翻倍（最高 5 秒）
- 平稳运行后逐步回退到 200ms
