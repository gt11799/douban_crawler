# douban_crawler

登录豆瓣、抓取小组话题评论、按已抓取评论回复。  
已从 MySQL 改为本地 SQLite（`douban.sqlite3`），降低依赖维护成本。

## 依赖

- Python 3.9+
- requests
- beautifulsoup4

安装：

```bash
pip install requests beautifulsoup4
```

## 快速检查（是否可运行）

```bash
python3 -m py_compile douban_crawler.py
```

## 使用示例

```python
from douban_crawler import DoubanSpider

spider = DoubanSpider("your_email", "your_password")
spider.crawl_comments("https://www.douban.com/group/topic/<topic_id>/")
# spider.post_comment("你好", comment_id=1)
```

## 变更说明

- 数据库存储由 MySQL 改为 SQLite。
- 默认登录地址更新为：`https://accounts.douban.com/passport/login`。
- 项目脚本改为 Python 3 语法。

> 注意：豆瓣登录、验证码、反爬策略可能随时间变化，实际登录流程可能需要继续调整。
