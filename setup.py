import os
from setuptools import find_packages, setup


def read_requirements(path):
    results = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        req, _, comment = line.partition("#")
        results.append(req.strip())
    return results


setup(
    name="kindle_download",
    author="yihong0618",
    author_email="zouzou0208@gmail.com",
    url="https://github.com/yihong0618/kindle_download_helper",
    license="GPL-3.0-or-later",
    version="1.1.2",
    description="Download all your kindle books and `DeDRM` script.",
    long_description="Download all your kindle books and `DeDRM` script.",
    packages=find_packages(),
    include_package_data=True,
    install_requires=read_requirements(
        os.path.join(os.path.dirname(__file__), "requirements.txt")
    ),
    entry_points={
        "console_scripts": ["kindle_download = kindle_download_helper.cli:main"],
    },
)
