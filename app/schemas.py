"""API 请求/响应模型"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict


class SingleCrawlRequest(BaseModel):
    """单公司爬取请求"""
    company_name: str = Field(..., min_length=1, description="公司名称")
    timeout: int = Field(default=120, ge=30, le=300, description="超时时间（秒）")


class BatchCrawlRequest(BaseModel):
    """批量爬取请求"""
    companies: List[str] = Field(..., min_length=1, max_length=200, description="公司名称列表")
    export_format: str = Field(default="excel", pattern="^(excel|csv)$", description="导出格式")
    timeout: int = Field(default=120, ge=30, le=300, description="单个公司超时时间（秒）")


class CrawlTaskResponse(BaseModel):
    """任务创建响应"""
    task_id: str
    status: str = "queued"
    message: str


class CrawlTaskStatus(BaseModel):
    """任务状态查询响应"""
    task_id: str
    status: str  # queued | running | completed | failed
    progress: int = 0
    total: int = 0
    result_file: Optional[str] = None
    error: Optional[str] = None


class CompanyData(BaseModel):
    """公司数据"""
    company_name: str = "N/A"
    legal_person: str = "N/A"
    registered_capital: str = "N/A"
    establish_date: str = "N/A"
    status: str = "N/A"
    organization_code: str = "N/A"
    business_scope: str = "N/A"
    industry: str = "N/A"
    taxpayer_type: str = "N/A"
    phone: str = "N/A"
    email: str = "N/A"
    address: str = "N/A"
    shareholders: str = "N/A"
    executives: str = "N/A"
    crawl_time: str = "N/A"


class SingleCrawlResponse(BaseModel):
    """单公司爬取响应"""
    success: bool
    data: Optional[CompanyData] = None
    error: Optional[str] = None


class CookieStatusResponse(BaseModel):
    """Cookie 状态响应"""
    valid: bool
    cookie_count: int
    has_auth_cookies: bool
    message: str


# ── 高级搜索 ──────────────────────────────────────────


class AdvancedSearchRequest(BaseModel):
    """高级搜索请求"""
    keyword: str = Field(default="", description="关键词（非必填）")
    status: Optional[List[int]] = Field(default=None, description="经营状态: 1=存续 2=注销 3=吊销 4=撤销 5=迁出 6=设立中 7=清算中 8=停业")
    province: Optional[List[str]] = Field(default=None, description="省份地区代码列表")
    industry: Optional[List[str]] = Field(default=None, description="行业分类代码列表")
    establish: Optional[List[str]] = Field(default=None, description="成立年限: 1y, 1-5y, 5-10y, 10-15y, 15y+")
    reg_capi: Optional[List[str]] = Field(default=None, description="注册资本: 0-100, 100-200, 200-500, 500-1000, 1000-")
    paid_capi: Optional[List[str]] = Field(default=None, description="实缴资本: has, no, 0-100, 100-200, 200-500, 500-1000, 1000-5000, 5000-")
    company_type: Optional[List[str]] = Field(default=None, description="公司类型")
    org_type: Optional[List[str]] = Field(default=None, description="组织类型")
    employee: Optional[List[str]] = Field(default=None, description="员工人数: <50, 50-99, 100-499, 500+")
    insured: Optional[List[str]] = Field(default=None, description="参保人数: <50, 50-99, 100-499, 500+")
    listing: Optional[List[str]] = Field(default=None, description="上市状态: a-share, us-stock, hk-stock, star-market, new-三板")
    scale: Optional[List[str]] = Field(default=None, description="规上企业")
    page: int = Field(default=1, ge=1, le=1000, description="页码")
    page_size: int = Field(default=10, ge=1, le=100, description="每页条数")


class AdvancedSearchItem(BaseModel):
    """高级搜索返回的单条公司数据"""
    company_name: str = "N/A"
    legal_person: str = "N/A"
    registered_capital: str = "N/A"
    establish_date: str = "N/A"
    status: str = "N/A"
    credit_code: str = "N/A"
    phone: str = "N/A"
    email: str = "N/A"
    address: str = "N/A"
    industry: str = "N/A"
    eid: str = ""


class AdvancedSearchResponse(BaseModel):
    """高级搜索响应"""
    success: bool
    total: str = "0"
    total_num: int = 0
    search_time: float = 0
    items: List[AdvancedSearchItem] = []
    page: int = 1
    has_next: bool = False
    error: Optional[str] = None
