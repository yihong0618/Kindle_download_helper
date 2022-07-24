# Kindle_download_helper

Download all your kindle books script.

<img width="1661" alt="image" src="https://user-images.githubusercontent.com/15976103/172113700-7be0ae1f-1aae-4b50-8377-13047c63411b.png">

Use `--readme` command to generate readme file to memory your kindle journey.

<img width="1120" alt="image" src="https://user-images.githubusercontent.com/15976103/174820597-5aca1065-8d39-4853-b89d-1b6fce658a98.png">


## 下载二进制文件

到 [Release](https://github.com/yihong0618/Kindle_download_helper/releases) 页面查看最新版本，获取对应系统的二进制文件下载解压即可。

若打开二进制遇到问题，请参考[这个 issue](https://github.com/yihong0618/Kindle_download_helper/issues/25)

## 无法下载问题

触发了亚马逊风控见 [issue](https://github.com/yihong0618/Kindle_download_helper/issues/69)

## Cli 

1. python3
2. requirements

```
pip3 install -r requirements.txt
```

<details>
<summary> Mac 新手指南</summary>

Added by [chongiscool](https://github.com/chongiscool)

基于我的环境和编程背景，我想补充下，没有 Python 经验的程序员，如何使用该开源库。

```txt
环境：macOS Catalina 10.15.7
我的编程背景：Android 开发者，使用 Java 和 Kotlin。「 Python3 学过基础语法，**没用 Python3 写过项目** 」
Kindle：我有一台 paperwhite 2
```

针对 README.md 的教程，自己如何在 [ **命令行** ] 的环境下，来下载电子书？
- 第一步：clone 仓库到下载目录(`~/Downloads`) ；再安装依赖 `cd ~/Downloads/Kindle_download_helper ; pip3 install -r requirements.txt --user`
- 第二步：打开 国内（amazon.cn）[电子书所有内容](http://amazon.cn/)（需要登录自己账户）的页面，按 F12
	- 获取 cookie ：Network -> Fetch/XHR -> Refresh(Cmd + R) -> 点击任意一个 ajax -> Headers -> Request Headers -> Cookie -> 右键复制它 -> 在 Kindle_download_helper 目录中，新建 cookie_file.txt 来保存 cookie 。
	- 获取 CSRF token : Headers 右边 -> Payload -> csrfToken -> 右键复制它。
- 第三步：下载书籍 `python3 kindle.py --cn --cookie-file ./cookie_file.txt your_csrf_Token`

可能的疑问：
1. 为什么安装依赖要加`--user`，可能是权限的问题，于是我按照命令行输出的提示，添加的，就安装依赖成功了；
2. 你应该始终，在 Kindle_download_helper 目录下，执行命令(`python3 kindle.py ***`)。
3. cookie 保存在 Kindle_download_helper/cookie_file.txt 中，方便命令行输入 和 cookie的更新，但**如果你要 PR，务必删除 ./cookie_file.txt，以免泄露个人账户信息**。

----------------------------- 分割线 ----------------------------- 

受[#41](https://github.com/yihong0618/Kindle_download_helper/issues/41))自动化的启发，如果你有 Shell 脚本的知识，也可以自行写个如下**半自动化**参考脚本；但前提，依然是你得准备好 cookie 和  csrf_token 。

```bash
#!/bin/bash

cd ~/Downloads 
git clone https://github.com/yihong0618/Kindle_download_helper.git
cd ~/Downloads/Kindle_download_helper 
pip3 install -r requirements.txt --user
# save cookie in ./cookie_file.txt
python3 kindle.py --cn --cookie-file ./cookie_file.txt your_csrf_Token
```

</details>

## 推荐手动输入 cookie

### 手动输入 cookie

若默认情况下提示 cookie 无效，你也可以手动输入 cookie 。方法是在上述全部书籍列表页面，按 <kbd>F12</kbd> 或右键点击——检查，进入网络面板(Network)，找到任意一个 `ajax` 请求，复制请求头里的 Cookie 即可。同时也能在 Payload 里找到 csrfToken。

然后，执行 `python3 kindle.py --cookie ${cookie}`。

你也可以把 cookie 保存为文本文件，执行 `python3 kindle.py --cookie-file ${cookie_file}` 下载书籍。

### 手动输入 CSRF Token

或执行过程中提示获取 CSRF token 失败，你可以手动输入 CSRF Token。CSRF Token 可以在页面源码中找到。方法是在浏览器书籍列表页面右键点击，选择查看网页源码，再利用文本匹配工具 (Ctrl + F) 查找 `csrfToken`，将等号右边引号中的值复制出来，加到命令行参数中：

```
# CSRF Token
python3 kindle.py ${csrfToken}
# Both cookie and CSRF Token
python3 kindle.py --cookie ${cookie} ${csrfToken}
```

## 自动获取 cookie

如果你的运行环境是本机，项目可以使用 [browser-cookie3](https://github.com/borisbabic/browser_cookie3) 库自动从浏览器中获取 cookie。

### 使用 `amazon.cn`

1. 登陆 amazon.cn
2. 访问 https://www.amazon.cn/hz/mycd/myx#/home/content/booksAll/dateDsc/
3. 右键查看源码，搜索 `csrfToken` 复制后面的 value
4. 执行 `python3 kindle.py --cn`
5. 如果下载推送文件 `python3 kindle.py --cn --pdoc`

### how to `amazon.com`

1. login amazon.com
2. visit https://www.amazon.com/hz/mycd/myx#/home/content/booksAll/dateDsc/
3. right click this page source then find `csrfToken` value copy
4. run: `python3 kindle.py`
5. if is doc file `python3 kindle.py --pdoc`

### how to `amazon.de` 

1. login amazon.com
2. visit https://www.amazon.de/hz/mycd/myx#/home/content/booksAll/dateDsc/
3. right click this page source then find `csrfToken` value copy
4. run: `python3 kindle.py --de`
5. if is doc file `python3 kindle.py --de --pdoc`

### `amazon.jp` を使用する

1. amazon.co.jp にログインする。
2. ホームページ https://www.amazon.jp/hz/mycd/myx#/home/content/booksAll/dateDsc/）にアクセスする。
3. ソースコード上で右クリックし、`csrfToken`を検索して、それ以降の値をコピーします。
4. `python3 kindle.py --jp` を実行する。
5. プッシュファイルをダウンロードする場合 `python3 kindle.py --jp --pdoc`


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
