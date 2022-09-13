import random

from kindle_download_helper.user_agents import USER_AGENTS

DEFAULT_OUT_DIR = "DOWNLOADS"
DEFAULT_OUT_DEDRM_DIR = "DEDRMS"
DEFAULT_SESSION_FILE = ".kindle_session"

KINDLE_HEADER = {
    "User-Agent": random.choice(USER_AGENTS),
}

CONTENT_TYPES = {
    "EBOK": "Ebook",
    "PDOC": "KindlePDoc",
}

KINDLE_URLS = {
    "cn": {
        "bookall": "https://www.amazon.cn/hz/mycd/myx#/home/content/booksAll",
        "download": "https://cde-ta-g7g.amazon.com/FionaCDEServiceEngine/FSDownloadContent?type={}&key={}&fsn={}&device_type={}&customerId={}&authPool=AmazonCN",
        "payload": "https://www.amazon.cn/hz/mycd/ajax",
        "insights": "https://www.amazon.cn/kindle/reading/insights/data",
        "book_url": "https://www.amazon.cn/dp/{book_id}",
    },
    "jp": {
        "bookall": "https://www.amazon.jp/hz/mycd/myx#/home/content/booksAll",
        "download": "https://cde-ta-g7g.amazon.com/FionaCDEServiceEngine/FSDownloadContent?type={}&key={}&fsn={}&device_type={}&customerId={}",
        "payload": "https://www.amazon.co.jp/hz/mycd/ajax",
        "insights": "https://www.amazon.co.jp/kindle/reading/insights/data",
        "book_url": "https://www.amazon.co.jp/dp/{book_id}",
    },
    "de": {
        "bookall": "https://www.amazon.de/hz/mycd/myx#/home/content/booksAll",
        "download": "https://cde-ta-g7g.amazon.com/FionaCDEServiceEngine/FSDownloadContent?type={}&key={}&fsn={}&device_type={}&customerId={}",
        "payload": "https://www.amazon.de/hz/mycd/ajax",
        "insights": "https://www.amazon.de/kindle/reading/insights/data",
        "book_url": "https://www.amazon.de/dp/{book_id}",
    },
    "com": {
        "bookall": "https://www.amazon.com/hz/mycd/myx#/home/content/booksAll",
        "download": "https://cde-ta-g7g.amazon.com/FionaCDEServiceEngine/FSDownloadContent?type={}&key={}&fsn={}&device_type={}&customerId={}&authPool=Amazon",
        "payload": "https://www.amazon.com/hz/mycd/ajax",
        "insights": "https://www.amazon.com/kindle/reading/insights/data",
        "book_url": "https://www.amazon.com/dp/{book_id}",
    },
}

# for kindle stats
GITHUB_README_COMMENTS = (
    "(<!--START_SECTION:{name}-->\n)(.*)(<!--END_SECTION:{name}-->\n)"
)
MY_KINDLE_STATS_INFO_HEAD = "## My Kindle Stats\n"
MY_KINDLE_STATS_INFO = "- I bought {books_len} books\n- I pushed {pdocs_len} docks\n- My first book is {first_book_title}, bought on {first_book_bought_date}\n- My first doc is {first_doc_title}, pushed on {first_doc_push_date}\n\n"

KINDLE_TABLE_HEAD = "| ID | Title | Authors | Acquired | Read | \n | ---- | ---- | ---- | ---- | ---- |\n"
KINDLE_STAT_TEMPLATE = "| {id} | {title} | {authors} | {acquired} | {read} |\n"
