from setuptools import find_packages, setup

setup(
    name="kindle_download",
    author="yihong0618",
    author_email="zouzou0208@gmail.com",
    url="https://github.com/yihong0618/kindle_download_helper",
    license="GPL V3",
    version="1.1.1",
    description="Download all your kindle books and `DeDRM` script.",
    long_description="Download all your kindle books and `DeDRM` script.",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "requests",
        "browser-cookie3",
        "faker",
        "pywin32 ; sys_platform == 'win32'"
    ],
    entry_points={
        "console_scripts": ["kindle_download = kindle_download_helper.cli:main"],
    },
)
