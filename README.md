# Kindle_download_helper

## 1. 先看看最终效果吧


使用命令行，下载完成的样子(Download all your kindle books script)。

<img width="1661" alt="image" src="https://user-images.githubusercontent.com/15976103/172113700-7be0ae1f-1aae-4b50-8377-13047c63411b.png">

使用 `--readme` 命令，生成你的 Kindle 阅读之旅（Use `--readme` command to generate readme file to memory your kindle journey）。

<img width="1120" alt="image" src="https://user-images.githubusercontent.com/15976103/174820597-5aca1065-8d39-4853-b89d-1b6fce658a98.png">

---

## 2. 下载

> 大致思路：你通过下面2种方法之一，搭配 cookie 和 CSRF Token，就能下载 Kindle电子书了。有了 cookie 和 CSRF Token 就能访问并下载你的电子书，第3点将介绍如何获取它们。

- 方法一：通过，下载二进制文件（即，应用程序），来下载电子书
- 方法二，通过，命令行（CLI），来下载电子书
  - macOS 指南：写给【 没有 Python 经验的程序员 】

### 2.1 方法一：下载二进制文件

到 [Release](https://github.com/yihong0618/Kindle_download_helper/releases) 页面查看最新版本，获取对应系统的二进制文件下载解压即可。

若打开二进制遇到问题，请参考[这个 issue](https://github.com/yihong0618/Kindle_download_helper/issues/25)



### 2.2 方法二：命令行（CLI） 

> 说明：你要熟悉基本的命令行操作，本地电脑有 Python3 环境，才能运行该项目；但如果你是 `macOS Catalina 10.15.7`，下面 2.2.1 有份专属指南给你。

1. 克隆项目到本地 `git clone https://github.com/yihong0618/Kindle_download_helper.git` 
2. 安装项目所需依赖(requirements)

```bash
# requirements.txt 在 Kindle_download_helper 目录中
cd your_path/Kindle_download_helper
# 安装依赖
pip3 install -r requirements.txt 
```
- 注意：macOS 下，运行 `pip3 install -r requirements.txt` 遇到权限问题而安装啊失败，比如提示以下权限问题；如果你对 Python3 有经验或希望安装在系统，那可以；如果你不了解 或 不熟悉 Python3，则可以考虑`--user` 选项，试试这个`pip3 install -r requirements.txt --user`重新安装依赖。
```
ERROR: Could not install packages due to an EnvironmentError: [Errno 13] Permission denied: '/Library/Python/3.8'
Consider using the `--user` option or check the permissions.
```

---

#### **2.2.1 macOS 指南：写给【 没有 Python 经验的程序员 】**

> 如果你满足下面三点，可参考 [issue #76](https://github.com/yihong0618/Kindle_download_helper/issues/76) 的参考指南/教程，完成电子书下载！

1. 环境：macOS Catalina 10.15.7
2. 编程背景：是个程序员，「 Python3 学过基础语法，没用 Python3 写过项目 」
3. Kindle：我有一台 paperwhite 2 【 我看 issues 有提过，你没 Kindle 设备，会遇到一些问题，因此才提这点。 】

---

## 3. 获取 cookie 和 CSRF Token

### 3.1 获取 cookie 和 CSRF Token

> 若默认情况下提示 cookie 无效，推荐手动输入 cookie 。

方法：打开国内亚马逊[全部书籍列表内容](https://www.amazon.cn/hz/mycd/myx#/home/content/booksAll/dateDsc/)（需要登录自己账户）的页面，按 <kbd>F12</kbd> 或 右键点击 —— 检查
- **获取 cookie** ：Network -> Fetch/XHR -> Refresh(Cmd + R) -> 点击任意一个 `ajax` -> Headers -> Request Headers -> Cookie -> 右键复制它 -> 存放一边 或 在Kindle_download_helper 目录中，新建 cookie_file.txt 来保存 cookie 。
- **获取 CSRF Token** ：Network -> Fetch/XHR -> Refresh(Cmd + R) -> 点击任意一个 `ajax` -> Headers 右边 -> Payload -> csrfToken -> 复制它，存放一边，后续使用。


### 3.2 自动获取 cookie

> 说明：高级用法，如果你不懂，请忽略！

如果你的运行环境是本机，项目可以使用 [browser-cookie3](https://github.com/borisbabic/browser_cookie3) 库自动从浏览器中获取 cookie。

---

## 4. 开始下载电子书吧

> 说明：让我们先定个性，第2点就是下载电子书的程序。第3点获取的cookie和CSRF Token就是亚马逊电子书的账号密码，有了它们，才能通过程序访问并下载你账户中的电子书。

- 你在第2.1 走了，下载二进制的应用程序，那带上第3点获取的 cookie和CSRF Token，去下载吧。
- 你在第2.2 走了，克隆该项目到本地，参见下面具体命令执行方式；


执行命令，开始下载国内亚马逊电子书
```bash
# 【 注意 ：确保在 Kindle_download_helper 目录，
# 因为 kindle.py 脚本在 Kindle_download_helper 目录下  】
cd you_path/Kindle_download_helper

# 查看命令参数含义，比如：看看 --cn 的含义
python3 kindle.py -h

# 直接使用 cookie 来下载电子书
python3 kindle.py --cn --cookie ${cookie} # --cn 下载国内亚马逊电子书

# 或者，cookie 保存在 Kindle_download_helper/cookie_file.txt 文件中
python3 kindle.py --cn --cookie-file ./cookie_file
```
- **注意**：如果，上面执行过程中提示获取 CSRF token 失败，你可以手动输入 CSRF Token。按下面的方式，手动添加，即可重新开始下载国内亚马逊电子书。

```bash
#  cookie 和 CSRF Token 都直接放命令行参数
python3 kindle.py --cn --cookie ${cookie} ${csrfToken}

# 或者，cookie 保存在 Kindle_download_helper/cookie_file.txt 文件中
python3 kindle.py --cn --cookie-file ./cookie_file ${csrfToken}

# 如果下载推送文件，使用 --pdoc 参数
python3 kindle.py --cn --pdoc --cookie-file ./cookie_file ${csrfToken}
```

### 小结一下

我们下载国内电子书的流程：
1. 第2点有了下载电子书的程序；
2. 第3点有了国内亚马逊书籍列表的cookie 和 CSRF Token；
3. 第4点，使用第2和第3点，直接下载国内亚马逊的电子书；

那，如果要下载 亚马逊（amazon.com）、亚马逊德国（amazon.de）、亚马逊日本（amazon.co.jp）账户的电子书呢？
> 打开对应国家的亚马逊站点的书籍列表，登录自己账户，通过第3点获取对应的 cookie 和 CSRF Token，再通过第4点注意切换国家缩写（如：中国 cn，日本 jp）下载即可；

以命令行方式，下载亚马逊（美国），德国，日本 为例
```bash
# 假设：你以获得了对应的cookie 和 CSRF Token

# 没有 --cn，缺省 就是亚马逊（美国）
python3 kindle.py --cookie-file ./cookie_file ${csrfToken}
# 添加 --de，亚马逊 德国
python3 kindle.py --de --cookie-file ./cookie_file ${csrfToken}
# 添加 --jp，亚马逊 日本
python3 kindle.py --cn --cookie-file ./cookie_file ${csrfToken}
```

### 目前支持的亚马逊站点如下

#### 使用 `amazon.cn`

1. 访问 [所有书籍列表](https://www.amazon.cn/hz/mycd/myx#/home/content/booksAll/dateDsc/)(可能需要登录)
2. 右键查看源码，搜索 `csrfToken` 复制后面的 value
3. 执行 `python3 kindle.py --cn`
4. 如果下载推送文件 `python3 kindle.py --cn --pdoc`

#### how to `amazon.com`

1. [visit digital content](https://www.amazon.com/hz/mycd/myx#/home/content/booksAll/dateDsc/)(may need login)
2. right click this page source then find `csrfToken` value copy
3. run: `python3 kindle.py`
4. if is doc file `python3 kindle.py --pdoc`

#### how to `amazon.de` 

1. [visit digital content](https://www.amazon.de/hz/mycd/myx#/home/content/booksAll/dateDsc/)(may need login)
2. right click this page source then find `csrfToken` value copy
3. run: `python3 kindle.py --de`
4. if is doc file `python3 kindle.py --de --pdoc`

#### `amazon.jp` を使用する

1. [訪問デジタルコンテンツ](https://www.amazon.jp/hz/mycd/myx#/home/content/booksAll/dateDsc/)(ログインが必要な場合があります)
2. ソースコード上で右クリックし、`csrfToken`を検索して、それ以降の値をコピーします。
3. `python3 kindle.py --jp` を実行する。
4. プッシュファイルをダウンロードする場合 `python3 kindle.py --jp --pdoc`

---

## 无法下载电子书的问题

触发了亚马逊风控见 [issue #69](https://github.com/yihong0618/Kindle_download_helper/issues/69)


## 注意

- cookie 和 csrf token 会过期，重新刷新下 amazon 的页面就行
- 程序会自动在命令执行的目录下创建 `DOWNLOADS` 目录，书会下载在 `DOWNLOADS` 里
- 如果你用 [DeDRM_tools](https://github.com/apprenticeharper/DeDRM_tools) 解密 key 存在 key.txt 里
- 或者直接拖进 Calibre 里 please google it.
- 如果过程中失败了可以使用 e.g. `--resume-from ${num}`
- 如果出现名字太长的报错可以增加: `--cut-length 80` 来截断文件名
- 支持推送文件下载 `--pdoc`
- 如果有很多同名 pdoc 或 book 可以使用 `--resolve_duplicate_names` 解决同名冲突
- error log 记录在 .error_books.log 中
- 支持生成最近读完书的 README `--readme` 生成的文件在 `my_kindle_stats.md` 中

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


<img width="1045" alt="image" src="https://user-images.githubusercontent.com/15976103/172113475-92862b57-bb39-4cd7-84d5-6bc428172bc4.png">


## 贡献

1. Any issues PR welcome
2. `black kindle.py`

## 感谢

- @[Kindle](https://zh.m.wikipedia.org/zh/Kindle)
- @[frostming](https://github.com/frostming) GUI and a lot of work
- @[bladewang](https://github.com/bladewang) PDOC download

## 赞赏

- 谢谢就够了

## Enjoy
