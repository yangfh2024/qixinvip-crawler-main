"""
API 数据模型——请求/响应的格式定义

这个文件用 Pydantic 库定义了 API 接口的数据格式，
它的作用：
1. 自动校验请求参数的格式（比如公司名称不能为空，超时时间不能小于30秒）
2. 自动生成 API 文档（Swagger 会读取这些定义）
3. 自动把 Python 字典序列化成 JSON

Pydantic 是 FastAPI 的核心依赖，通过 BaseModel 定义数据模型，
一个类就完成了校验 + 文档 + 序列化三件事。
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict


class SingleCrawlRequest(BaseModel):
    """单公司爬取的请求格式"""
    company_name: str = Field(..., min_length=1, description="公司名称（必填）")
    timeout: int = Field(default=120, ge=30, le=300, description="超时时间，单位秒（30-300之间）")


class BatchCrawlRequest(BaseModel):
    """批量爬取的请求格式"""
    companies: List[str] = Field(..., min_length=1, max_length=200, description="公司名称列表（一次最多200个）")
    export_format: str = Field(default="excel", pattern="^(excel|csv)$", description="导出格式：excel 或 csv")
    timeout: int = Field(default=120, ge=30, le=300, description="每个公司的超时时间（秒）")


class CrawlTaskResponse(BaseModel):
    """创建批量任务后的响应格式"""
    task_id: str
    status: str = "queued"   # queued=排队中, running=运行中, completed=已完成, failed=失败
    message: str


class CrawlTaskStatus(BaseModel):
    """查询批量任务进度的响应格式"""
    task_id: str
    status: str              # queued | running | completed | failed
    progress: int = 0        # 已处理数量
    total: int = 0           # 总数量
    result_file: Optional[str] = None  # 结果文件名（完成后才有）
    error: Optional[str] = None        # 错误信息（失败时才有）


class CompanyData(BaseModel):
    """公司数据——返回给用户的完整公司信息"""
    company_name: str = "N/A"        # 公司名称
    legal_person: str = "N/A"        # 法定代表人
    registered_capital: str = "N/A"  # 注册资本
    establish_date: str = "N/A"      # 成立日期
    status: str = "N/A"              # 经营状态
    organization_code: str = "N/A"   # 统一社会信用代码
    business_scope: str = "N/A"      # 经营范围
    industry: str = "N/A"            # 所属行业
    taxpayer_type: str = "N/A"       # 纳税人资质
    phone: str = "N/A"               # 联系电话
    email: str = "N/A"               # 企业邮箱
    address: str = "N/A"             # 注册地址
    shareholders: str = "N/A"        # 股东信息
    executives: str = "N/A"          # 主要人员
    crawl_time: str = "N/A"          # 爬取时间


class SingleCrawlResponse(BaseModel):
    """单公司爬取的响应格式"""
    success: bool                    # 是否成功
    data: Optional[CompanyData] = None  # 公司数据（成功时才有）
    error: Optional[str] = None      # 错误信息（失败时才有）


class CookieStatusResponse(BaseModel):
    """Cookie 状态检查的响应格式"""
    valid: bool                      # Cookie 是否有效
    cookie_count: int                # Cookie 数量
    has_auth_cookies: bool           # 是否包含登录凭证
    message: str                     # 文字描述


# ── 高级搜索 ──────────────────────────────────────────


class AdvancedSearchRequest(BaseModel):
    """高级搜索的请求格式"""
    keyword: str = Field(default="", description="搜索关键词（必填，只传省份/行业等筛选条件不返回数据）")
    status: Optional[List[int]] = Field(default=None, description="经营状态: 1=存续 2=注销 3=吊销 4=撤销 5=迁出 6=设立中 7=清算中 8=停业")
    province: Optional[List[str]] = Field(default=None, description="省份代码列表")
    industry: Optional[List[str]] = Field(default=None, description="行业代码列表")
    establish: Optional[List[str]] = Field(default=None, description="成立年限: 1y, 1-5y, 5-10y, 10-15y, 15y+")
    reg_capi: Optional[List[str]] = Field(default=None, description="注册资本范围: 0-100, 100-200, 200-500, 500-1000, 1000-")
    paid_capi: Optional[List[str]] = Field(default=None, description="实缴资本范围")
    company_type: Optional[List[str]] = Field(default=None, description="公司类型")
    org_type: Optional[List[str]] = Field(default=None, description="组织类型")
    employee: Optional[List[str]] = Field(default=None, description="员工人数: <50, 50-99, 100-499, 500+")
    insured: Optional[List[str]] = Field(default=None, description="参保人数")
    listing: Optional[List[str]] = Field(default=None, description="上市状态: a-share, us-stock, hk-stock, star-market, new三板")
    scale: Optional[List[str]] = Field(default=None, description="规上企业类型")
    page: int = Field(default=1, ge=1, le=1000, description="页码")
    page_size: int = Field(default=10, ge=1, le=100, description="每页条数")


class AdvancedSearchItem(BaseModel):
    """高级搜索返回的单条公司数据"""
    company_name: str = "N/A"        # 公司名称
    legal_person: str = "N/A"        # 法定代表人
    registered_capital: str = "N/A"  # 注册资本
    establish_date: str = "N/A"      # 成立日期
    status: str = "N/A"              # 经营状态
    credit_code: str = "N/A"         # 统一社会信用代码
    phone: str = "N/A"               # 联系电话
    email: str = "N/A"               # 邮箱
    address: str = "N/A"             # 地址
    industry: str = "N/A"            # 行业
    eid: str = ""                    # 企业 ID（可用于后续查询）


class AdvancedSearchResponse(BaseModel):
    """高级搜索的响应格式"""
    success: bool
    total: str | int = "0"           # 总数（字符串或数字）
    total_num: int = 0               # 总数（数字）
    search_time: float = 0           # 搜索耗时（秒）
    items: List[AdvancedSearchItem] = []  # 公司列表
    page: int = 1
    has_next: bool = False           # 是否有下一页
    error: Optional[str] = None
