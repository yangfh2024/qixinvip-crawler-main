"""
快速单公司爬取测试脚本

比 main.py 更轻量，专门用来测试单个公司能不能爬成功。
适合开发调试时用——不用进菜单选模式，直接改公司名就能跑。

用法：python test_single.py
"""

import asyncio
import sys
import io
import json
from crawler import QixinbaoCrawler
from exporter import get_exporter
from utils import load_config

# 设置 UTF-8 编码，解决 Windows 控制台中文乱码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

async def test_single_company():
    """测试单个公司爬取"""
    print("=" * 60)
    print("启信宝爬虫 - 单公司测试")
    print("=" * 60)

    # 加载配置
    config = load_config()

    # 检查 Cookie
    if config.get('cookie') == 'your_cookie_string_here' or not config.get('cookie'):
        print("\n[!] 错误: 请先配置 Cookie")
        print("\n请编辑 cookie.txt 或 config.json 文件")
        return

    # 测试公司（可以改成你要测的公司名）
    test_company = "景煜熙曜（上海）创业投资管理中心（有限合伙）"
    print(f"\n测试公司: {test_company}")
    print("-" * 60)

    # 手动管理爬虫生命周期（不用 async with，更灵活）
    crawler = QixinbaoCrawler()
    await crawler.browser_manager.start()

    try:
        data = await crawler.crawl_single_company(test_company)

        if data:
            print("\n" + "=" * 60)
            print("[OK] 爬取成功! 数据如下:")
            print("=" * 60)
            print(json.dumps(data, ensure_ascii=False, indent=2))

            # 导出到 Excel
            print("\n正在导出到 Excel...")
            exporter = get_exporter(config)
            exporter.add_company(data)
            exporter.save()

            print("\n[OK] 测试完成!")
        else:
            print("\n[!] 爬取失败，请检查:")
            print("1. Cookie 是否正确配置")
            print("2. VIP 账号是否有效")
            print("3. 网络连接是否正常")
            print("4. 公司名称是否正确")
            print("5. 选择器是否需要调整")
    finally:
        # 确保浏览器关闭
        print("\n正在关闭浏览器...")
        await crawler.browser_manager.stop()

if __name__ == "__main__":
    try:
        asyncio.run(test_single_company())
    except KeyboardInterrupt:
        print("\n\n用户中断")
    except Exception as e:
        print(f"\n发生错误: {e}")
        import traceback
        traceback.print_exc()
