# Kindle_download_helper
Download all your kindle books script.


<img width="1661" alt="image" src="https://user-images.githubusercontent.com/15976103/172113700-7be0ae1f-1aae-4b50-8377-13047c63411b.png">


# 使用 `amazon CN`

1. 登陆 amazon.cn
2. 访问 https://www.amazon.cn/hz/mycd/myx#/home/content/booksAll/dateDsc/
3. 找到 cookie XHR 或者其他的方式
4. 右键查看源码，搜索 `csrfToken` 复制后面的 value
5. 执行 `python3 kindle.py ${cookie} ${csrfToken} --is-cn`

# how to `amazon.com`
1. login amazon.com
2. visit https://www.amazon.com/hz/mycd/myx#/home/content/booksAll/dateDsc/ 
3. find cookie F12 XHR or other ways
4. right click this page source then find `csrfToken` value copy
5. run: `python3 kindle.py ${cookie} ${csrfToken}`


# 注意
- cookie 和 csrf token 会过期，重新刷新下 amazon 的页面就行 
- 书会下载在 DOWNLOADS 里
- 如果你用 [DeDRM_tools](https://github.com/apprenticeharper/DeDRM_tools) 解密 key 存在 key.txt 里 
- 或者直接拖进 Calibre 里 please google it.
- 如果过程中失败了可以使用 e.g. `--recover-index ${num}`

<img width="1045" alt="image" src="https://user-images.githubusercontent.com/15976103/172113475-92862b57-bb39-4cd7-84d5-6bc428172bc4.png">


# Enjoy
