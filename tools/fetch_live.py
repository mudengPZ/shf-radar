# -*- coding: utf-8 -*-
"""
SHF 猎手 · 真实在售数据抓取器
==========================================================================
两种用途：
  1. 本机人工登录一次，导出登录态文件 state.json
  2. CI（GitHub Actions）每天定时用 state.json 抓取，生成 data.js 并发布

用法：
  python tools/fetch_live.py --login                     扫码登录，导出 tools/state.json
  python tools/fetch_live.py --probe "铠武 阵羽柠檬"      抓一个词看效果
  python tools/fetch_live.py --all --limit 20             全量（可限型号数）
  python tools/fetch_live.py --all --headless             无头模式（CI 用）

口径：
  · 只保留「整只」商品；补件 / 拆卖 / 食玩 / 装动 / 空盒 / 定金 一律剔除。
  · 版本名必须出现在标题里，避免把同骑士的其它形态算成这只。
  · 标题含 国产 / 祖国 / KO / 仿 的标为非正版，保留但标红、不参与最低价。
  · 闲鱼列表不含运费字段，运费记 0 并标 shippingNote，页面写「运费另计」。
  · 抓不到就是 0 条，不编造。
==========================================================================
"""
import argparse
import base64
import json
import re
import sys
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path

from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(__file__).resolve().parent.parent
PROFILE = BASE / "tools" / "chrome-profile"     # 仅 --login 时用，不提交
STATE = BASE / "tools" / "state.json"           # 登录态，不提交
PIC_DIR = BASE / "models" / "live"
OUT = BASE / "live_prices.json"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

DROP = [
    "补件", "拆卖", "拆出", "散货", "配件", "零件", "散件", "单出", "拆车",
    "食玩", "装动", "掌动", "扭蛋", "景品", "软胶", "拼装", "模型套件",
    "空盒", "运输盒", "包装盒", "说明书", "吸塑", "封套", "彩盒",
    "定金", "预售", "代购", "代拍", "求购", "回收", "接单",
    "支架", "地台", "武器包", "特效件", "手型", "替换脸",
]
FAKE = ["国产", "祖国", "ko版", "仿版", "盗版", "高仿", "厂货", "第三批"]


def launch(p, headless):
    return p.chromium.launch(
        headless=headless,
        args=["--disable-blink-features=AutomationControlled"],
    )


def new_ctx(browser, state=None):
    kw = {
        "viewport": {"width": 1400, "height": 950},
        "user_agent": UA,
        "locale": "zh-CN",
    }
    if state and Path(state).exists():
        kw["storage_state"] = str(state)
    return browser.new_context(**kw)


def logged_in_xianyu(pg):
    try:
        t = pg.inner_text("body")
    except Exception:
        return False
    head = t[:300]
    return "登录" not in head and "扫码" not in head


def load_models():
    txt = (BASE / "data.js").read_text(encoding="utf-8")
    m = re.search(r"const MODELS = (\[[\s\S]*?\]);\n", txt)
    if not m:
        raise SystemExit("data.js 里找不到 MODELS")
    return json.loads(m.group(1))


def search_keyword(model):
    """闲鱼按综合排序，词太短会被同骑士的其它形态稀释，所以带上形态名更聚焦。
    例：铠武 阵羽 真骨雕 / 空我 全能 真骨雕 / 龙骑 真骨雕"""
    line = model.get("line") or ""
    rider = model["name"].replace("假面骑士", "").strip().split(" ")[0]
    short = (model.get("short") or "").strip()
    if not re.search(r"[\u4e00-\u9fff]", rider):
        cn = next((a for a in (model.get("alias") or [])
                   if re.search(r"[\u4e00-\u9fff]", a)), None)
        if cn:
            rider = cn
    tail = " 真骨雕" if line == "真骨雕" else " shf"
    if short and short != rider and len(short) >= 2:
        return "%s %s%s" % (rider, short, tail)
    return rider + tail


def parse_price(v):
    if isinstance(v, (int, float)):
        return int(round(float(v)))
    if isinstance(v, str):
        s = re.sub(r"[^\d.]", "", v)
        return int(round(float(s))) if s else None
    if isinstance(v, list):
        s = re.sub(r"[^\d.]", "", "".join(
            x.get("text", "") for x in v if isinstance(x, dict)))
        return int(round(float(s))) if s else None
    if isinstance(v, dict):
        for k in ("value", "text", "price", "soldPrice"):
            if k in v:
                return parse_price(v[k])
    return None


def parse_xianyu(payload_texts):
    rows = []
    for txt in payload_texts:
        try:
            root = json.loads(txt)
        except Exception:
            continue
        rl = (root.get("data") or {}).get("resultList") or []
        for r in rl:
            try:
                c = r["data"]["item"]["main"]["exContent"]
            except Exception:
                continue
            dp = c.get("detailParams") or {}
            iid = str(c.get("itemId") or dp.get("itemId") or "")
            title = (c.get("title") or dp.get("title") or "").strip()
            price = parse_price(dp.get("soldPrice")) or parse_price(c.get("price"))
            if not iid or not title or not price:
                continue
            rows.append({
                "itemId": iid,
                "title": title,
                "price": price,
                "area": c.get("area") or "",
                "seller": c.get("userNickName") or dp.get("userNick") or "",
                "pic": c.get("picUrl") or "",
                "url": "https://www.goofish.com/item?id=" + iid,
            })
    seen, uniq = set(), []
    for r in rows:
        if r["itemId"] in seen:
            continue
        seen.add(r["itemId"])
        uniq.append(r)
    return uniq


def is_target(row, model):
    t = row["title"]
    low = t.lower()
    if any(w in t for w in DROP):
        return False
    floor = 180 if model.get("line") == "真骨雕" else 120
    if row["price"] < floor:
        return False
    short = (model.get("short") or "").replace(" ", "")
    core = model["name"].replace("假面骑士", "").replace(" ", "")
    tnorm = t.replace(" ", "")
    if not ((short and short in tnorm) or (core and core in tnorm)):
        return False
    if model.get("line") == "真骨雕":
        # 真骨雕型号必须明确写出来，否则会把旧版 SHF 同名装甲算进来
        if not ("真骨雕" in t or "真骨彫" in t or "shinkocchou" in low):
            return False
    else:
        if "shf" not in low and "figuarts" not in low:
            return False
    return True


def download_pic(ctx, url, dst):
    """商品图存本地，避免平台 CDN 的防盗链与失效。"""
    if not url or dst.exists():
        return dst.exists()
    try:
        r = ctx.request.get(url, headers={"Referer": "https://www.goofish.com/"},
                            timeout=20000)
        if not r.ok:
            return False
        from PIL import Image
        im = Image.open(BytesIO(r.body())).convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[3])
        bg.thumbnail((640, 640), Image.LANCZOS)
        dst.parent.mkdir(parents=True, exist_ok=True)
        bg.save(dst, "JPEG", quality=84, optimize=True)
        return True
    except Exception:
        return False


def to_item(row, model, fetched_at, img_rel=None):
    t = row["title"]
    low = t.lower()
    official = not any(w in low or w in t for w in FAKE)
    if "全新" in t or "未拆" in t or "未开封" in t or "misb" in low:
        cond = "全新"
    elif "仅开封" in t or "仅拆" in t:
        cond = "仅开封"
    else:
        cond = "二手"
    it = {
        "modelKey": model["key"],
        "platform": "XIANYU",
        "title": t[:110],
        "price": row["price"],
        "shipping": 0,
        "condition": cond,
        "official": official,
        "shopName": row["seller"] or "闲鱼卖家",
        "wantCount": 0,
        "itemUrl": row["url"],
        "area": row["area"],
        "shippingNote": "闲鱼列表不含运费，以商品页为准",
        "fetchedAt": fetched_at,
    }
    if img_rel:
        it["image"] = img_rel
    return it


def grab(ctx, keyword, wait_ms=2600, scrolls=3):
    pg = ctx.new_page()
    captured = []

    def on_resp(resp):
        try:
            ct = (resp.headers.get("content-type") or "").lower()
            if "json" not in ct:
                return
            t = resp.text()
            if len(t) > 200 and "resultList" in t:
                captured.append(t)
        except Exception:
            pass

    pg.on("response", on_resp)
    try:
        pg.goto("https://www.goofish.com/search?q=" + keyword,
                wait_until="domcontentloaded", timeout=45000)
        pg.wait_for_timeout(wait_ms)
        for _ in range(scrolls):
            pg.mouse.wheel(0, 2400)
            pg.wait_for_timeout(1100)
        pg.wait_for_timeout(500)
    finally:
        pg.remove_listener("response", on_resp)
        pg.close()
    return captured


def export_state(ctx):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    ctx.storage_state(path=str(STATE))
    raw = STATE.read_bytes()
    b64 = base64.b64encode(raw).decode()
    (BASE / "tools" / "state.b64").write_text(b64, encoding="utf-8")
    print("登录态已写入", STATE, "| 长度", len(raw), "字节")
    print("Base64 版本 tools/state.b64（%d 字符），用于放进 GitHub Secrets" % len(b64))


def do_login(p):
    PROFILE.mkdir(parents=True, exist_ok=True)
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE), headless=False,
        viewport={"width": 1400, "height": 950}, user_agent=UA,
        args=["--disable-blink-features=AutomationControlled"])
    pg = ctx.new_page()
    pg.goto("https://www.goofish.com/", wait_until="domcontentloaded", timeout=40000)
    print("\n浏览器已打开，请扫码登录闲鱼。脚本自动检测，登录后自动关闭。\n")
    deadline = time.time() + 300
    while time.time() < deadline:
        if logged_in_xianyu(pg):
            print("检测到已登录")
            export_state(ctx)
            time.sleep(1)
            ctx.close()
            return True
        time.sleep(3)
    print("5 分钟内未检测到登录")
    ctx.close()
    return False


def do_probe(p, keyword, headless=False):
    b = launch(p, headless)
    ctx = new_ctx(b, STATE)
    caps = grab(ctx, keyword, wait_ms=3200, scrolls=2)
    rows = parse_xianyu(caps)
    pg = ctx.new_page()
    pg.goto("https://www.goofish.com/", wait_until="domcontentloaded", timeout=30000)
    print("登录状态：", "已登录" if logged_in_xianyu(pg) else "未登录")
    print("解析商品：", len(rows), "条")
    for r in rows[:12]:
        print("  ¥%-6s %s | %s" % (r["price"], r["area"], r["title"][:40]))
    b.close()


def do_all(p, keys=None, limit=None, headless=False, gap=2.5, wait_ms=2600):
    models = load_models()
    if keys:
        models = [m for m in models if m["key"] in keys]
    if limit:
        models = models[:limit]
    print("待抓型号：", len(models))

    b = launch(p, headless)
    ctx = new_ctx(b, STATE)
    fetched_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    items, stats = [], []
    for i, m in enumerate(models, 1):
        kw = search_keyword(m)
        try:
            caps = grab(ctx, kw, wait_ms=wait_ms)
            rows = parse_xianyu(caps)
            hit_rows = [r for r in rows if is_target(r, m)]
            for r in hit_rows:
                dst = PIC_DIR / (r["itemId"] + ".jpg")
                ok = download_pic(ctx, r["pic"], dst)
                rel = ("models/live/%s.jpg" % r["itemId"]) if ok else None
                items.append(to_item(r, m, fetched_at, rel))
        except Exception as e:
            print("  [%d/%d] %s 失败：%s" % (i, len(models), m["key"], str(e)[:50]))
            stats.append((m["key"], 0, 0))
            continue
        stats.append((m["key"], len(rows), len(hit_rows)))
        print("  [%2d/%d] %-20s 解析 %3d → 保留 %2d"
              % (i, len(models), m["key"], len(rows), len(hit_rows)))
        time.sleep(gap)

    b.close()

    if not items:
        print("\n本次 0 条（多半是登录态失效或触发风控），保留上一版 live_prices.json 不覆盖")
        return

    OUT.write_text(json.dumps({
        "fetchedAt": fetched_at,
        "source": "XIANYU",
        "keywordMode": "per-model",
        "items": items,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    ok = sum(1 for _, _, h in stats if h)
    print("\n完成：%d 个型号里 %d 个抓到真实在售，共 %d 条，图片 %d 张"
          % (len(models), ok, len(items), sum(1 for x in items if x.get("image"))))
    print("写入", OUT.name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--login", action="store_true")
    ap.add_argument("--probe")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--keys", nargs="*")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--wait", type=int, default=2600)
    ap.add_argument("--gap", type=float, default=2.5)
    a = ap.parse_args()

    with sync_playwright() as p:
        if a.login:
            do_login(p)
        elif a.probe:
            do_probe(p, a.probe, a.headless)
        elif a.all or a.keys:
            do_all(p, a.keys, a.limit, a.headless, a.gap, a.wait)
        else:
            print("请指定 --login / --probe 关键词 / --all / --keys")


if __name__ == "__main__":
    main()
