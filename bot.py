import os, re, json, html
from datetime import datetime, timedelta, timezone
import requests

CHANNELS = [
    ("bbcrussian", "BBC", "#bb1919"),
    ("meduzalive", "Медуза", "#2f7bd9"),
    ("astrapress", "ASTRA", "#e0861a"),
]
TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
MAX_NEWS = 10
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня",
          "июля", "августа", "сентября", "октября", "ноября", "декабря"]
MSK = timezone(timedelta(hours=3))
SKIP = ("http", "Подробнее", "Открыть", "Фото", "Видео",
        "Защитить себя", "Please open", "VIEW IN")


def strip_junk(s):
    return re.sub(r"[\U00010000-\U0010ffff\u2600-\u27bf\ufe0f\u200d]", "", s).strip()


def is_junk(l):
    return (not l or l.startswith(SKIP) or "Сайт без VPN" in l
            or re.fullmatch(r"[—–\-_=*\s]+", l) is not None)


def short(s, n):
    if len(s) <= n:
        return s
    cut = s[:n]
    k = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return cut[:k + 1] if k > n * 0.4 else cut.rsplit(" ", 1)[0] + "…"


def parse_posts(text, ch):
    _, label, color = ch
    posts = []
    for part in text.split("tgme_widget_message_wrap")[1:]:
        m_id = re.search(r'data-post="([^"]+)"', part)
        m_tx = re.search(r'js-message_text[^>]*>(.*?)</div>', part, re.S)
        m_tm = re.search(r'<time[^>]*datetime="([^"]+)"', part)
        if not (m_id and m_tx and m_tm):
            continue
        t = re.sub(r"<br\s*/?>", "\n", m_tx.group(1))
        t = html.unescape(re.sub(r"<[^>]+>", "", t))
        lines = []
        for x in t.split("\n"):
            l = strip_junk(x)
            if not is_junk(l):
                lines.append(l)
        if not lines:
            continue
        title = re.sub(r"^[^\w«\"“(]+", "", lines[0])
        if len(title) < 10:
            continue
        posts.append({
            "title": title,
            "summary": short(" ".join(lines[1:]), 300),
            "url": "https://t.me/" + m_id.group(1),
            "time": datetime.fromisoformat(m_tm.group(1)),
            "src": label,
            "color": color,
        })
    return posts


def get_channel_posts(ch, day_start):
    found = {}
    url = f"https://t.me/s/{ch[0]}"
    last_before = None
    for _ in range(8):
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        r.raise_for_status()
        page = parse_posts(r.text, ch)
        for p in page:
            found[p["url"]] = p
        if page and min(p["time"] for p in page) < day_start:
            break
        nums = [int(x) for x in re.findall(r"\?before=(\d+)", r.text)]
        if not nums:
            break
        nxt = min(nums)
        if last_before is not None and nxt >= last_before:
            break
        last_before = nxt
        url = f"https://t.me/s/{ch[0]}?before={nxt}"
    return [p for p in found.values() if p["time"] >= day_start]


def get_day_posts():
    day_start = datetime.now(MSK).replace(hour=0, minute=0, second=0, microsecond=0)
    allp, errors = [], 0
    for ch in CHANNELS:
        try:
            allp += get_channel_posts(ch, day_start)
        except Exception as e:
            errors += 1
            print("Канал не прочитался:", ch[0], type(e).__name__)
    if errors == len(CHANNELS):
        raise SystemExit(1)
    return sorted(allp, key=lambda p: p["time"], reverse=True)


CSS = """
:root{--bg:#f4efe1;--ink:#1e1e1e;--gray:#5f5f5f;--line:#cfc8b2;--card:#faf6ea}
@media (prefers-color-scheme:dark){:root{--bg:#15171c;--ink:#ece8da;--gray:#a9a597;--line:#33363e;--card:#1d2027}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:Georgia,"DejaVu Serif",serif;padding:14px 14px 40px;max-width:760px;margin:0 auto}
header{text-align:center;border-top:4px double var(--ink);border-bottom:2px solid var(--ink);padding:12px 0 10px;margin-bottom:16px}
h1{margin:0;font-size:30px;letter-spacing:1px}
.sub{color:var(--gray);font-size:14px;margin-top:6px;font-family:Arial,sans-serif}
.item{display:block;text-decoration:none;color:inherit;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 12px 12px 14px;margin-bottom:10px}
.meta{font-family:Arial,sans-serif;font-weight:bold;font-size:13px;color:var(--gray);margin-bottom:5px}
h2{margin:0 0 6px;font-size:19px;line-height:1.25}
p{margin:0;color:var(--gray);font-size:15px;line-height:1.4}
.empty{text-align:center;color:var(--gray);padding:40px 0}
"""


def make_page(posts):
    now = datetime.now(MSK)
    items = []
    for p in posts:
        t = p["time"].astimezone(MSK).strftime("%H:%M")
        summ = f"<p>{html.escape(p['summary'])}</p>" if p["summary"] else ""
        items.append(
            f'<a class="item" style="border-left:5px solid {p["color"]}" '
            f'href="{html.escape(p["url"])}">'
            f'<div class="meta">{t} · {html.escape(p["src"])}</div>'
            f'<h2>{html.escape(p["title"])}</h2>{summ}</a>'
        )
    body = "\n".join(items) if items else '<div class="empty">Пока новостей за сегодня нет</div>'
    date = f"{now.day} {MONTHS[now.month - 1]} {now.year}"
    names = " · ".join(c[1] for c in CHANNELS)
    return (
        '<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Новостная газета</title><style>' + CSS + '</style></head><body>'
        '<header><h1>НОВОСТНАЯ ГАЗЕТА</h1>'
        f'<div class="sub">{date} · {names} · новостей: {len(posts)}</div>'
        '</header>' + body + '</body></html>'
    )


def make_widget_json(posts):
    data = {}
    for i in range(1, 7):
        if i <= len(posts):
            p = posts[i - 1]
            data[f"time{i}"] = p["time"].astimezone(MSK).strftime("%H:%M")
            data[f"src{i}"] = p["src"]
            data[f"title{i}"] = short(p["title"], 110)
            data[f"url{i}"] = p["url"]
        else:
            data[f"time{i}"] = data[f"src{i}"] = data[f"title{i}"] = data[f"url{i}"] = ""
    data["count"] = str(len(posts))
    return json.dumps(data, ensure_ascii=False, indent=1)


def make_text(news):
    now = datetime.now(MSK)
    out = f"📰 <b>Новости</b> · {now.strftime('%H:%M')}\n"
    for n in news:
        t = n["time"].astimezone(MSK).strftime("%H:%M")
        block = (f"\n<b>{t} · {html.escape(n['src'])}</b>\n"
                 f'<a href="{html.escape(n["url"])}">{html.escape(n["title"])}</a>\n')
        if n["summary"]:
            block += html.escape(short(n["summary"], 110)) + "\n"
        if len(out) + len(block) > 3800:
            break
        out += block
    return out


def main():
    posts = get_day_posts()
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(make_page(posts))
    with open("news.json", "w", encoding="utf-8") as f:
        f.write(make_widget_json(posts))
    print("Новостей за сегодня:", len(posts))

    if os.environ.get("SEND") != "true":
        return
    now = datetime.now(timezone.utc)
    fresh = [p for p in posts if now - p["time"] < timedelta(hours=4, minutes=30)]
    news = fresh[:MAX_NEWS]
    if not news:
        print("Новых новостей для бота нет")
        return
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": make_text(news), "parse_mode": "HTML",
              "disable_web_page_preview": "true"},
        timeout=60,
    )
    print("Телеграм ответил:", r.status_code)
    if not r.ok:
        raise SystemExit(1)


main()
