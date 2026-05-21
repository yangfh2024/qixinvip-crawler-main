"""
数据导出模块

负责把爬取到的公司数据保存为 Excel 或 CSV 文件。
支持两种导出格式，通过工厂函数 get_exporter() 自动选择。

核心依赖是 pandas（Python 数据分析库），
它让数据导出变得非常简单——把字典列表转成 DataFrame 就能直接存 Excel。
"""

import pandas as pd
from datetime import datetime
from typing import List, Dict
from utils import generate_timestamp, sanitize_filename


class ExcelExporter:
    """Excel 导出器——把公司数据保存为 .xlsx 文件"""

    def __init__(self, config: Dict):
        """
        初始化导出器

        Args:
            config: 配置字典（来自 config.json）
        """
        self.config = config
        self.output_config = config.get('output', {})
        self.data: List[Dict] = []  # 存储所有公司数据的列表

        # 生成文件名（默认格式：qixinbao_companies_20250101_143025.xlsx）
        base_filename = self.output_config.get('filename', 'qixinbao_companies')
        if self.output_config.get('timestamp', True):
            self.filename = f"{base_filename}_{generate_timestamp()}.xlsx"
        else:
            self.filename = f"{base_filename}.xlsx"

        # 清理文件名中的非法字符
        self.filename = sanitize_filename(self.filename)

    def add_company(self, company_data: Dict):
        """
        添加一条公司数据到列表

        Args:
            company_data: 公司数据字典（来自爬虫）
        """
        self.data.append(company_data)
        print(f"已添加: {company_data.get('company_name', 'Unknown')}")

    def save(self):
        """把数据保存为 Excel 文件"""
        if not self.data:
            print("没有数据需要保存")
            return

        # 把字典列表转成 pandas DataFrame（表格）
        df = pd.DataFrame(self.data)

        # 定义英文列名 → 中文列名的映射
        # 这样导出的 Excel 表头就是中文的，方便阅读
        column_mapping = {
            'company_name': '公司名称',
            'legal_person': '法定代表人',
            'registered_capital': '注册资本',
            'establish_date': '成立日期',
            'status': '经营状态',
            'phone': '联系电话',
            'email': '企业邮箱',
            'address': '注册地址',
            'business_scope': '经营范围',
            'industry': '所属行业',
            'taxpayer_type': '纳税人资质',
            'organization_code': '统一社会信用代码',
            'shareholders': '股东信息',
            'executives': '主要人员',
            'branches': '分支机构',
            'crawl_time': '爬取时间'
        }

        # 只保留 DataFrame 中存在的列（避免报错）
        existing_columns = [col for col in column_mapping.keys() if col in df.columns]
        if existing_columns:
            df = df[existing_columns]
            df.rename(columns=column_mapping, inplace=True)  # 把英文列名换成中文

        # 写入 Excel 文件
        try:
            df.to_excel(self.filename, index=False, engine='openpyxl')
            print(f"\n[OK] 数据已成功保存到: {self.filename}")
            print(f"[OK] 共保存 {len(self.data)} 条记录")
            print(f"[OK] 包含 {len(df.columns)} 个字段")
        except Exception as e:
            print(f"保存失败: {e}")
            raise

    def get_summary(self) -> Dict:
        """获取数据摘要（总数/成功数/失败数）"""
        if not self.data:
            return {'total': 0, 'successful': 0, 'failed': 0}

        total = len(self.data)
        successful = sum(1 for item in self.data if item.get('company_name') != 'N/A')
        failed = total - successful

        return {
            'total': total,
            'successful': successful,
            'failed': failed
        }


class CSVExporter:
    """CSV 导出器——把公司数据保存为 .csv 文件"""

    def __init__(self, config: Dict):
        """
        初始化 CSV 导出器

        Args:
            config: 配置字典
        """
        self.config = config
        self.output_config = config.get('output', {})
        self.data: List[Dict] = []

        # 生成文件名
        base_filename = self.output_config.get('filename', 'qixinbao_companies')
        if self.output_config.get('timestamp', True):
            self.filename = f"{base_filename}_{generate_timestamp()}.csv"
        else:
            self.filename = f"{base_filename}.csv"

    def add_company(self, company_data: Dict):
        """添加公司数据"""
        self.data.append(company_data)

    def save(self):
        """保存为 CSV 文件（UTF-8 编码，带 BOM 头，Excel 打开不乱码）"""
        if not self.data:
            print("没有数据需要保存")
            return

        df = pd.DataFrame(self.data)

        # 列名映射（英文 → 中文）
        column_mapping = {
            'company_name': '公司名称',
            'legal_person': '法定代表人',
            'registered_capital': '注册资本',
            'establish_date': '成立日期',
            'status': '经营状态',
            'phone': '联系电话',
            'email': '企业邮箱',
            'address': '注册地址',
            'shareholders': '股东信息',
            'executives': '主要人员'
        }

        existing_columns = [col for col in column_mapping.keys() if col in df.columns]
        if existing_columns:
            df = df[existing_columns]
            df.rename(columns=column_mapping, inplace=True)

        # utf-8-sig 编码会在文件开头加 BOM 头，Excel 打开中文不乱码
        df.to_csv(self.filename, index=False, encoding='utf-8-sig')
        print(f"数据已保存到: {self.filename}")


def get_exporter(config: Dict):
    """
    工厂函数——根据配置自动选择导出器

    这是设计模式中的"工厂模式"：根据条件返回不同的类实例。
    config.json 中 output.format 设为 "csv" 就返回 CSV 导出器，
    默认返回 Excel 导出器。

    Args:
        config: 配置字典

    Returns:
        ExcelExporter 或 CSVExporter 的实例
    """
    output_format = config.get('output', {}).get('format', 'excel').lower()

    if output_format == 'csv':
        return CSVExporter(config)
    else:
        return ExcelExporter(config)
