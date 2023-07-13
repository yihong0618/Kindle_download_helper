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


def trim_title_suffix(title):
    new_title = re.sub(r"(（[^）]+）?|【[^】]+】?)", "", title)
    for ch in '\/:*?"<>|':
        new_title = new_title.replace(ch, "-")
    return new_title
