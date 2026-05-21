---
name: qixin-company-info
description: 启信宝企业信息查询 - 打开网站搜索企业并保存基本信息到CSV文件
allowed-tools: Bash(playwright-cli:*) Bash(eval:*)
---

# 启信宝企业信息查询

## 功能说明
使用 playwright-cli 打开启信宝网站，搜索指定企业名称，提取企业基本信息并保存为CSV文件。

## 使用方式
```
/qixin-company-info
```
运行后会要求输入企业名称，然后自动执行完整流程。

## 重要：浏览器可见性

**必须使用 `--headed` 参数**，否则浏览器窗口不可见：
```bash
playwright-cli open www.qixin.com --persistent --headed
```

## 完整操作流程

### 第一步：打开浏览器并等待用户登录

```bash
# 1. 用 headed + persistent 模式打开浏览器（窗口可见）
playwright-cli open www.qixin.com --persistent --headed

# 2. 询问用户是否已登录，如果未登录则等待登录
# 用户在浏览器窗口中手动登录启信宝

# 3. 登录完成后确认，继续执行查询
```

**关键点：**
- `--persistent` = 持久化配置，登录状态会保存
- `--headed` = 可见窗口模式，用户能看到浏览器
- 登录完成后用户告知，继续下一步

### 第二步：搜索企业

```bash
# 1. 获取页面快照确认搜索框
playwright-cli snapshot

# 2. 填充搜索框（搜索框 ref 通常是 e45）
playwright-cli fill e45 "企业名称"

# 3. 按回车执行搜索
playwright-cli press Enter
```

### 第三步：进入企业详情页

**方法A：从搜索建议直接点击**
```bash
# 如果搜索建议列表中出现目标企业，点击进入
playwright-cli click eXX  # eXX 是搜索结果中的链接ref
```

**方法B：直接从URL进入（推荐，更可靠）**
```bash
# 1. 获取企业链接的URL
playwright-cli eval "el => el.href" eXX

# 2. 使用URL直接导航
playwright-cli goto https://www.qixin.com/company/{企业ID}
```

### 第四步：获取完整信息

```bash
# 获取页面所有文本内容（推荐，一次获取全部信息）
playwright-cli eval "document.body.innerText.substring(0, 15000)"
```

### 第五步：保存为CSV文件

根据获取的信息，整理成CSV格式保存：
```csv
项目,内容
企业名称,xxx
蓝色标签-经营状态,存续
蓝色标签-发票抬头,是
...
```

## 遇到的问题及解决方案

### 问题1：浏览器窗口不可见
**原因：** 缺少 `--headed` 参数

**解决方案：**
```bash
# 重新用 headed 模式打开
playwright-cli open www.qixin.com --persistent --headed
```

### 问题2：弹窗遮挡导致点击失败
**错误信息：**
```
<div class="z-modal fade-in">…</div> intercepts pointer events
```

**解决方案：**
1. 使用 `press Escape` 尝试关闭弹窗
2. 直接使用 `goto` 命令导航到目标页面，绕过弹窗
3. 使用 `--persistent` 参数重新打开浏览器

```bash
# 直接导航到企业详情页
playwright-cli goto https://www.qixin.com/company/企业ID
```

### 问题3：搜索建议列表中点击企业无响应
**原因：** 弹窗或浮层遮挡了可点击元素

**解决方案：**
1. 从URL直接进入：获取链接的href属性
```bash
playwright-cli eval "el => el.href" eXX
```
2. 使用 `goto` 直接访问获取到的URL

### 问题4：需要登录才能查看详细信息
**表现：** 页面跳转到登录页，或部分信息显示"登录查看"

**原因：** 启信保存在持久化配置文件中的登录状态没有生效

**解决方案：**
1. 关闭所有浏览器窗口
2. 使用 `--persistent --headed` 重新打开
3. 让用户在可见的浏览器窗口中手动登录一次
4. 登录状态会被持久化，下次无需再登录

```bash
# 关闭浏览器
playwright-cli close

# 重新打开，等待用户登录
playwright-cli open www.qixin.com --persistent --headed
```

### 问题5：快照文件过大
**解决方案：**
```bash
playwright-cli snapshot --depth=6
```

## 提取的企业信息字段

### 蓝色标签（页面标题下方）
- 经营状态（如：存续、注销）
- 发票抬头
- 曾用名
- 上市情况
- 税务信用等级
- 纳税人资格
- 企业类型（小微企业、民营企业等）
- 高新企业
- 国家级技术创新示范企业
- 启信分
- 自身风险数量

### 基本信息
- 法定代表人
- 注册资本
- 成立日期
- 统一社会信用代码
- 实缴资本
- 电话
- 网址
- 邮箱
- 疑似实控人
- 所属行业
- 企业规模
- 企业员工数量
- 社保人数
- 地址
- 英文名
- 历史名称
- 简介
- 股东信息
- 对外投资
- 分支机构

## CSV保存格式

```csv
项目,内容
企业名称,xxx
蓝色标签-经营状态,存续
蓝色标签-发票抬头,是
蓝色标签-曾用名,xxx
蓝色标签-税务信用,xxx
蓝色标签-纳税人资格,xxx
蓝色标签-企业类型,xxx
蓝色标签-启信分,xxx
蓝色标签-自身风险,xxx条
法定代表人,xxx
注册资本,xxx万元
成立日期,xxxx-xx-xx
统一社会信用代码,xxxxxxxx
实缴资本,xxx万元
电话,xxx
网址,xxx
邮箱,xxx
疑似实控人,xxx
所属行业,xxx
企业规模,xxx
企业员工,xxx人
地址,xxx
简介,xxx
股东信息,xxx
对外投资,xxx家
分支机构,xxx家
```

## 注意事项

1. **必须使用 `--headed` 参数**让浏览器窗口可见，用户才能登录
2. **第一次使用需要登录**：登录状态会保存在持久化配置中，之后无需重复登录
3. 使用 `snapshot` 确认页面状态后再进行下一步操作
4. 企业ID是UUID格式，如：`534472fd-7d53-4958-8132-d6a6242423d8`
5. 部分财务数据（营业收入、利润总额、总资产）需要VIP权限才能查看
6. 如果登录状态失效，关闭浏览器后重新用 `--persistent --headed` 打开即可
