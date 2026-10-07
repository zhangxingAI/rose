"""Streamlit 外壳：只为拿一条公网 https 链接。

页面是纯前端单页（index.html，粒子版），不依赖 Python。这里只做三件事：
把它整屏嵌进 iframe、把 Streamlit 自己的头/边距/滚动条藏掉、
把 ?play / ?still 透传成页面认识的 hash。

**这个文件刻意不用任何 Streamlit 组件。** 手机首屏慢的大头是 Streamlit
自己的前端包（实测 2.7MB / 63 个请求 / 4G 下约 5.9 秒，而页面本身只有 41KB、
一个请求、0.4 秒）。那 2.7MB 里 index.js 909KB + protobuf.js 738KB 是内核，
去不掉；试过把 st.markdown / st.radio 全撤掉换成从 iframe 内部注入，
实测传输量和时间纹丝不动——那些 chunk 是急加载的。所以这里只是尽量不添乱：
藏 chrome 的 CSS 从 iframe 内部往父页面插（srcdoc 与外层同源，够得着
parent.document），整个脚本只剩一次 components.html 调用。

其它几版（index_mix / index_photo / index_splat）留在仓库里备查，不再上线。

用法：
    ?play=1     跳过「点一下，花开」
    ?still=1    定格不动

部署：推到公开 GitHub 仓库 → share.streamlit.io 绑定本文件。不需要 Secrets。
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

HERE = Path(__file__).parent
PAGE = "index_splat.html"      # 粒子版

CHROME_CSS = """
[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
[data-testid="stSidebarCollapsedControl"],
#MainMenu, footer, .stAppDeployButton { display: none !important; }

html, body, .stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"] { background: #000 !important; overflow: hidden !important; }

.block-container,
[data-testid="stMainBlockContainer"],
[data-testid="stAppViewBlockContainer"] {
  padding: 0 !important; margin: 0 !important; max-width: 100% !important;
}

[data-testid="stVerticalBlock"],
[data-testid="stElementContainer"] { gap: 0 !important; }

/* 100dvh 放后面，手机地址栏收起时才不露黑边 */
iframe {
  position: fixed !important; inset: 0 !important;
  width: 100vw !important; height: 100vh !important; height: 100dvh !important;
  border: 0 !important; z-index: 10 !important;
}
"""

# 这一段在 iframe 里跑，负责两件事：
#   1. 把藏 chrome 的样式插进**父页面**（换 st.markdown 也一样慢，但少一个组件
#      少一分意外，而且不必让 Streamlit 解析一大段 HTML）
#   2. 写 __ROSE_HASH——srcdoc 里读不到外层地址栏的 hash 和 query
BOOT = """<script>
(function () {
  window.__ROSE_HASH = "__FRAG__";
  try {
    var d = parent.document;
    if (!d.getElementById("rose-chrome")) {
      var s = d.createElement("style");
      s.id = "rose-chrome";
      s.textContent = __CSS__;
      d.head.appendChild(s);
    }
  } catch (e) {}
})();
</script>"""


@st.cache_data(show_spinner=False)
def read_page(name: str) -> str:
    return (HERE / name).read_text(encoding="utf-8")


def page_html(name: str, fragment: str) -> str:
    markup = read_page(name)
    # 用替换而不是 .format()：BOOT 里全是 JS 的花括号，format 会把它们当占位符
    boot = BOOT.replace("__FRAG__", fragment).replace("__CSS__", json.dumps(CHROME_CSS))
    return markup.replace("<body>", "<body>\n" + boot, 1)


def main() -> None:
    st.set_page_config(
        page_title="叶老师的玫瑰",
        page_icon="🌹",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    q = st.query_params
    fragment = "#still" if q.get("still") else ("#play" if q.get("play") else "")
    components.html(page_html(PAGE, fragment), height=900, scrolling=False)


if __name__ == "__main__":
    main()
