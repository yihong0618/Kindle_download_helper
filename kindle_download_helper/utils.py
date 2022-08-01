import re
from kindle_download_helper.config import GITHUB_README_COMMENTS


def replace_readme_comments(file_name, comment_str, comments_name):
    with open(file_name, "r+", encoding="UTF-8") as f:
        text = f.read()
        # regrex sub from github readme comments
        text = re.sub(
            GITHUB_README_COMMENTS.format(name=comments_name),
            r"\1{}\n\3".format(comment_str),
            text,
            flags=re.DOTALL,
        )
        f.seek(0)
        f.write(text)
        f.truncate()
