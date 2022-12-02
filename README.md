# Kindle_download_helper

Download all your kindle books script.

![image](https://user-images.githubusercontent.com/15976103/172113700-7be0ae1f-1aae-4b50-8377-13047c63411b.png)


## 安装 Kindle_download_helper

### GUI 程序下载

到 [Release](https://github.com/yihong0618/Kindle_download_helper/releases) 页面查看最新版本，获取对应系统的二进制文件下载解压即可。

### Help

- 若打开二进制遇到问题，请参考 [#25](https://github.com/yihong0618/Kindle_download_helper/issues/25)
- kindle 无法下载问题，触发了亚马逊风控见 [#69](https://github.com/yihong0618/Kindle_download_helper/issues/69)
- Mac 新手指南 by @chongiscool，见 [#76](https://github.com/yihong0618/Kindle_download_helper/issues/76)

### Cli 安装使用

1. python3
2. requirements

```python
python3 --version  # 查看 python 版本
```

```python
pip3 install kindle_download  # 使用 pip 安装
```

```bash
git clone https://github.com/yihong0618/Kindle_download_helper.git && cd Kindle_download_helper
```

```python
pip3 install -r requirements.txt
```

```python
python3 kindle.py --h  #查看使用参数

usage: kindle.py [-h] [--cookie COOKIE | --cookie-file COOKIE_FILE] [--cn] [--jp] [--de] [--resume-from INDEX]
                 [--cut-length CUT_LENGTH] [-o OUTDIR] [-od OUTDEDRMDIR] [-s SESSION_FILE] [--pdoc] [--resolve_duplicate_names]
                 [--readme] [--dedrm] [--list]
                 [csrf_token]

positional arguments:
  csrf_token            amazon or amazon cn csrf token

options:
  -h, --help            show this help message and exit
  --cookie COOKIE       amazon or amazon cn cookie
  --cookie-file COOKIE_FILE
                        load cookie local file
  --cn                  if your account is an amazon.cn account
  --jp                  if your account is an amazon.jp account
  --de                  if your account is an amazon.de account
  --resume-from INDEX   resume from the index if download failed
  --cut-length CUT_LENGTH
                        truncate the file name
  -o OUTDIR, --outdir OUTDIR
                        dwonload output dir
  -od OUTDEDRMDIR, --outdedrmdir OUTDEDRMDIR
                        dwonload output dedrm dir
  -s SESSION_FILE, --session-file SESSION_FILE
                        The reusable session dump file
  --pdoc                to download personal documents or ebook
  --resolve_duplicate_names
                        Resolve duplicate names files to download
  --readme              If you want to generate kindle readme stats
  --dedrm               If you want to `dedrm` directly
  --list                just list books/pdoc, not to download
```


### 下载 kindle 书籍

尝试[自动获取 cookie](#%E8%87%AA%E5%8A%A8%E8%8E%B7%E5%8F%96-cookie)、csrfToken 进行下载

```python
python3 kindle.py  --dedrm --cn  ## --dedrm 移除 DRM
```

(推荐) [手动输入 cookie](#%E8%8E%B7%E5%8F%96-cookie)、csrfToken 进行下载

```python
python3 kindle.py ${csrfToken} --cookie ${cookie} --dedrm --cn #下载国区 Kindle 书籍并移除 DRM
python3 kindle.py ${csrfToken} --cookie ${cookie} --dedrm #下载美区 Kindle 书籍
```

### 获取 cookie

若默认情况下提示 cookie 无效，你也可以手动输入 cookie。
在上述 [全部书籍](https://www.amazon.cn/hz/mycd/myx#/home/content/booksAll/dateDsc/) 列表页面，按 `F12` 或右键点击——检查，进入网络面板 (Network)，在 Name 栏找到任意一个 `ajax` 请求，右键复制 Request Headers 里的 `Cookie` 即可。同时也能在 Payload 里找到 `csrfToken`。

然后，执行

```python
python3 kindle.py --cn --cookie ${cookie}
```

你也可以把 cookie 保存为文本文件，执行 `python3 kindle.py --cookie-file ${cookie_file}` 下载书籍。

### 获取 CSRF Token

若执行过程中提示获取 CSRF token 失败，你可以手动输入 CSRF Token。

`CSRF Token` 可以在页面源码中找到。在 [全部书籍](https://www.amazon.cn/hz/mycd/myx#/home/content/booksAll/dateDsc/) 列表页面右键点击，选择查看网页源码，再利用文本匹配工具 (Ctrl + F) 查找 `csrfToken`，将等号右边引号中的值复制出来，加到命令行参数中。

```python
# CSRF Token
python3 kindle.py --cn ${csrfToken}
# Both cookie and CSRF Token
python3 kindle.py --cn --cookie ${cookie} ${csrfToken}
```

## 自动获取 cookie

如果你的运行环境是本机，项目可以使用 [browser-cookie3](https://github.com/borisbabic/browser_cookie3) 库自动从浏览器中获取 cookie。

### 使用 `amazon.cn`

1. 登陆 amazon.cn
2. 访问 <https://www.amazon.cn/hz/mycd/myx#/home/content/booksAll/dateDsc/>
3. 右键查看源码，搜索 `csrfToken` 复制后面的 value
4. 执行 `python3 kindle.py --cn`
5. 如果下载推送文件 `python3 kindle.py --cn --pdoc`
5. 如果想直接 dedrm 解密 (不保证好用) `python3 kindle.py --cn --pdoc --dedrm`

### how to `amazon.com`

1. login amazon.com
2. visit <https://www.amazon.com/hz/mycd/myx#/home/content/booksAll/dateDsc/>
3. right click this page source then find `csrfToken` value copy
4. run: `python3 kindle.py`
5. if is doc file `python3 kindle.py --pdoc`

### how to `amazon.de`

1. login amazon.de
2. visit <https://www.amazon.de/hz/mycd/myx#/home/content/booksAll/dateDsc/>
3. right click this page source then find `csrfToken` value copy
4. run: `python3 kindle.py --de`
5. if is doc file `python3 kindle.py --de --pdoc`

### `amazon.jp` を使用する

1. amazon.co.jp にログインする。
2. ホームページ <https://www.amazon.jp/hz/mycd/myx#/home/content/booksAll/dateDsc/>）にアクセスする。
3. ソースコード上で右クリックし、`csrfToken`を検索して、それ以降の値をコピーします。
4. `python3 kindle.py --jp` を実行する。
5. プッシュファイルをダウンロードする場合 `python3 kindle.py --jp --pdoc`


## 注意

- cookie 和 csrf token 会过期，重新刷新下 amazon 的页面就行
- 程序会自动在命令执行的目录下创建 `DOWNLOADS` 目录，书会下载在 `DOWNLOADS` 里
- 支持 mobi 类型的文件直接 dedrm `--dedrm` 生成的文件在 `DEDRMS` 里
- 如果你用 [DeDRM_tools](https://github.com/apprenticeharper/DeDRM_tools) 解密 key 存在 key.txt 里
- 或者直接拖进 Calibre 里 please google it.
- 如果过程中失败了可以使用 e.g. `--resume-from ${num}`
- 如果出现名字太长的报错可以增加：`--cut-length 80` 来截断文件名
- 支持推送文件下载 `--pdoc`
- 如果有很多同名 pdoc 或 book 可以使用 `--resolve_duplicate_names` 解决同名冲突
- error log 记录在 .error_books.log 中
- 支持生成最近读完书的 README `--readme` 生成的文件在 `my_kindle_stats.md` 中
- 支持 mobi 类型的文件直接 dedrm `--dedrm` 生成的文件在 `DEDRMS` 里

## Note

- The cookie and csrf token will expire, just refresh the amazon page again.
- The program will automatically create `DOWNLOADS` directory under the command execution directory, the book will be downloaded in `DOWNLOADS` directory.
- If you use [DeDRM_tools](https://github.com/apprenticeharper/DeDRM_tools) to decrypt the key, it will be stored in key.txt
- or just drag it into Calibre. Please google it.
- If the process fails you can use e.g. `--resume-from ${num}`
- If the name is too long, you can add: `-cut-length 80` to truncate the file name
- Support push file download `--pdoc`
- If there are many pdocs or books with the same name, you can use `--resolve_duplicate_names` to resolve conflicts with the same name.
- error log is logged in .error_books.log
- Support for generating READMEs of recently finished books `--readme` generated files are in `my_kindle_stats.md`

![image](https://user-images.githubusercontent.com/15976103/172113475-92862b57-bb39-4cd7-84d5-6bc428172bc4.png)

## 贡献

1. Any issues PR welcome
2. `black kindle.py`

## 感谢

- @[Kindle](https://zh.m.wikipedia.org/zh/Kindle)
- @[DeDRM_tools](https://github.com/apprenticeharper/DeDRM_tools)
- @[frostming](https://github.com/frostming) GUI and a lot of work
- @[bladewang](https://github.com/bladewang) PDOC download

## 赞赏

- 谢谢就够了

## Enjoy
