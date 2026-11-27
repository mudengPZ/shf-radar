# -*- coding: utf-8 -*-
"""
SHF 猎手 · data.js 生成器
==========================================================================
作用：把「平成 20 位主骑 × 真骨雕 / 普通 SHF」的型号库，展开成可直接
      被前端读取的 data.js。

数据口径（重要，答辩时会问）：
  · 型号名、所属作品、版本（55th / 20th / 生存形态 等）来自万代公开资料。
  · 官方定价（日元）标注 confirmed 的，是公开页面核实过的实际定价：
        空我 全能 55th        9,900
        空我 青龙/天马/泰坦    8,800 各
        旧1号                 7,700
        响鬼（初版）           5,500
        Kiva                  7,700
        铠武 斩月 蜜瓜铠甲    11,000
        铠武 阵羽柠檬（TN2025 会场限定） 13,750
        Ghost 无限魂（2027 首次发售）13,200
        BLACK 帝王石闪光      11,000
        影月 暗影闪光         13,200
        修卡战斗员             5,500
  · 标注 estimated 的，是按同期同产品线的价格带推算（真骨雕近年
    7,700–9,900，普通 SHF 3,500–5,500），不是逐款核实，页面上不声称是。
  · 各平台「挂单价」是按行情规律构造的样本：以官方定价折人民币为基准，
    乘产品热度系数与平台系数，带确定性随机。规则全部写在本文件里，
    任何人可以重跑复现，不存在手工编造的个别数字。

运行：python gen_data.py
==========================================================================
"""

import json
import random
import hashlib
from pathlib import Path

# 100 日元 ≈ 4.75 元（2026-11 近似）
JPY_TO_CNY = 0.0475

# ---------------------------------------------------------------- 实物图
# 每个型号可配一张实物图：键为 modelKey，值为相对站点根目录的图片路径。
# 约定：图片放在 models/ 下，文件名与 modelKey 一致（.jpg / .png / .webp）。
# 来源必须是可核查的公开商品页或自行拍摄，并在 README 的图片来源表登记。
# 未配图的型号显示文字占位封面；不使用生成图冒充实物照片。
# 已配 9 款：4 款空我 55th、Kabuto 20th、Ghost 无限魂来自万代魂官网商品主图；
# 铠武阵羽、OOO 鹰虎蝗 / 狮虎豹来自 Hpoi 商品页封面图。
# 每款的来源页与原始图片 URL 见 models/sources.csv。
MODEL_IMAGES = {
    "kuuga-mighty-55": "models/kuuga-mighty-55.jpg",
    "kuuga-dragon-55": "models/kuuga-dragon-55.jpg",
    "kuuga-pegasus-55": "models/kuuga-pegasus-55.jpg",
    "kuuga-titan-55": "models/kuuga-titan-55.jpg",
    "kabuto-rider-20": "models/kabuto-rider-20.jpg",
    "ghost-mugen": "models/ghost-mugen.jpg",
    "gaim-jinba": "models/gaim-jinba.jpg",
    "ooo-tatoba": "models/ooo-tatoba.jpg",
    "ooo-latorartar": "models/ooo-latorartar.jpg",
}

# ---------------------------------------------------------------- 商品页直链
# 型号级「官方商品页」：来自 models/sources.csv 的 source_page 列，逐款核对过商品标题。
# 有值的型号，详情页会出现「查看官方商品页」直链，点开就是该商品的介绍与官方定价。
def _load_product_pages():
    import csv
    p = Path(__file__).parent / "models" / "sources.csv"
    if not p.exists():
        return {}
    out = {}
    with p.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            k = (row.get("model_key") or "").strip()
            u = (row.get("source_page") or "").strip()
            if k and u.startswith("http"):
                out[k] = u
    return out


PRODUCT_PAGES = _load_product_pages()

# 单条报价的真实商品链接（可选）：键为 "modelKey|PLATFORM|成色"。
# 例：{"gaim-jinba|XIANYU|二手": "https://www.goofish.com/item?id=..."}
# 未登记时，前端按完整型号名打开平台精确搜索，不伪造商品 ID。
ITEM_URL_OVERRIDES = {}

# ---------------------------------------------------------------- 型号库
# (rider_key, 主骑中文, 年份, 作品名, [型号...])
# 型号字段：key / line / ver / name / short / jpy / src / heat / alias
RIDERS = [
    # ================================================================
    # 说明：每条型号的 line 必须与「万代是否真的出过这条线」一致。
    # 平成 20 主骑里，有真骨雕的只有 13 位；剑、Fourze、Drive、Ghost、
    # Ex-Aid、Build、Zi-O 这 7 位至今没有真骨雕，只能记普通 SHF。
    # 依据：真骨雕 2014–2026 全年代商品清单（shishioh.info）+ 万代公开定价。
    # ================================================================

    ("kuuga", "空我", 2000, "假面骑士空我", [
        ("kuuga-mighty-55", "真骨雕", "55 周年", "空我 全能形态", "全能", 9900, "confirmed", "hot",
         ["空我", "kuuga", "クウガ", "mighty", "全能", "55"]),
        ("kuuga-dragon-55", "真骨雕", "55 周年", "空我 青龙形态", "青龙", 8800, "confirmed", "normal",
         ["空我", "青龙", "dragon", "ドラゴン", "55"]),
        ("kuuga-pegasus-55", "真骨雕", "55 周年", "空我 天马形态", "天马", 8800, "confirmed", "normal",
         ["空我", "天马", "pegasus", "ペガサス", "55"]),
        ("kuuga-titan-55", "真骨雕", "55 周年", "空我 泰坦形态", "泰坦", 8800, "confirmed", "normal",
         ["空我", "泰坦", "titan", "タイタン", "55"]),
        ("kuuga-ultimate", "真骨雕", "究极形态", "空我 究极形态", "究极", 6600, "confirmed", "hot",
         ["空我", "究极", "ultimate", "アルティメット"]),
        ("kuuga-rising", "真骨雕", "升华形态", "空我 升华全能", "升华", 5500, "confirmed", "normal",
         ["空我", "升华", "rising", "ライジング"]),
        ("kuuga-shf-mighty", "SHF", "早期普通线", "空我 全能形态", "全能", 3500, "estimated", "cold",
         ["空我", "kuuga", "全能", "shf"]),
    ]),

    ("agito", "AgitΩ", 2001, "假面骑士AgitΩ", [
        ("agito-ground", "真骨雕", "", "AgitΩ 大地形态", "大地", 5500, "confirmed", "normal",
         ["agito", "亚极陀", "agitΩ", "大地", "ground", "アギト"]),
        ("agito-trinity", "真骨雕", "", "AgitΩ 三位一体形态", "三位一体", 8800, "estimated", "normal",
         ["agito", "亚极陀", "三位一体", "trinity", "トリニティ"]),
        ("agito-shf", "SHF", "早期普通线", "AgitΩ 大地形态", "大地", 3500, "estimated", "cold",
         ["agito", "亚极陀", "大地", "shf"]),
    ]),

    ("ryuki", "龙骑", 2002, "假面骑士龙骑", [
        ("ryuki-base", "真骨雕", "2025 年发售", "龙骑", "龙骑", 9900, "estimated", "hot",
         ["龙骑", "ryuki", "リュウキ", "城户真司"]),
        ("ryuki-survive-shf", "SHF", "普通线", "龙骑 生存形态", "生存", 3850, "confirmed", "normal",
         ["龙骑", "ryuki", "生存", "survive", "サバイブ", "shf"]),
        ("ryuki-shf", "SHF", "含契约兽", "龙骑", "龙骑", 4400, "estimated", "cold",
         ["龙骑", "ryuki", "shf"]),
    ]),

    ("faiz", "Faiz", 2003, "假面骑士555", [
        ("faiz-base", "真骨雕", "", "Faiz", "Faiz", 8800, "estimated", "hot",
         ["faiz", "555", "ファイズ", "乾巧", "faizu"]),
        ("faiz-night", "真骨雕", "夜战配色", "Faiz 夜战配色", "夜战", 9900, "estimated", "hot",
         ["faiz", "555", "夜战", "暗夜", "night"]),
        ("faiz-accel", "真骨雕", "加速形态", "Faiz 加速形态", "加速", 9900, "estimated", "normal",
         ["faiz", "555", "加速", "accel", "アクセル"]),
        ("faiz-shf", "SHF", "再版", "Faiz", "Faiz", 3500, "estimated", "normal",
         ["faiz", "555", "shf"]),
    ]),

    # 剑：真骨雕至今未推出，只有 2013 年的普通 SHF
    ("blade", "剑", 2004, "假面骑士剑", [
        ("blade-shf", "SHF", "2013 年初版", "剑", "剑", 3800, "confirmed", "cold",
         ["blade", "剑", "ブレイド", "剑崎一真", "shf"]),
        ("blade-jack-shf", "SHF", "杰克形态", "剑 杰克形态", "杰克", 3850, "estimated", "cold",
         ["blade", "剑", "杰克", "jack", "ジャック", "shf"]),
    ]),

    ("hibiki", "响鬼", 2005, "假面骑士响鬼", [
        ("hibiki-base", "真骨雕", "", "响鬼", "响鬼", 5500, "confirmed", "normal",
         ["响鬼", "hibiki", "ヒビキ", "日高仁志"]),
        ("hibiki-armed", "真骨雕", "装甲响鬼", "装甲响鬼", "装甲", 9900, "estimated", "normal",
         ["响鬼", "装甲", "armed", "アームド"]),
        ("hibiki-kurenai", "真骨雕", "红响鬼", "红响鬼", "红", 8800, "estimated", "normal",
         ["响鬼", "红", "kurenai", "クレナイ"]),
        ("hibiki-shf", "SHF", "早期普通线", "响鬼", "响鬼", 4400, "estimated", "cold",
         ["响鬼", "hibiki", "shf"]),
    ]),

    ("kabuto", "Kabuto", 2006, "假面骑士Kabuto", [
        ("kabuto-rider-20", "真骨雕", "20 周年", "Kabuto 骑士形态", "骑士形态", 9900, "estimated", "hot",
         ["kabuto", "甲斗", "甲斗王", "カブト", "天道总司", "骑士形态"]),
        ("kabuto-hyper", "真骨雕", "超越形态", "Kabuto 超越形态", "超越", 8030, "confirmed", "hot",
         ["kabuto", "甲斗", "超越", "hyper", "ハイパー"]),
        ("kabuto-dark", "真骨雕", "黑暗甲斗", "黑暗甲斗王", "黑暗", 8800, "estimated", "normal",
         ["kabuto", "甲斗", "黑暗", "dark"]),
        ("kabuto-shf", "SHF", "早期普通线", "Kabuto 骑士形态", "骑士形态", 3500, "estimated", "cold",
         ["kabuto", "甲斗", "shf"]),
    ]),

    ("deno", "电王", 2007, "假面骑士电王", [
        ("deno-sword", "真骨雕", "与圣枪同捆 8,800", "电王 圣剑形态", "圣剑", 4400, "confirmed", "hot",
         ["电王", "den-o", "deno", "圣剑", "sword", "デンオウ", "野上良太郎"]),
        ("deno-gun", "真骨雕", "与圣剑同捆 8,800", "电王 圣枪形态", "圣枪", 4400, "confirmed", "normal",
         ["电王", "deno", "圣枪", "gun", "ガン"]),
        ("deno-rod", "真骨雕", "钓竿与圣斧同捆", "电王 钓竿形态", "钓竿", 8800, "estimated", "normal",
         ["电王", "deno", "钓竿", "rod", "ロッド"]),
        ("deno-shf", "SHF", "早期普通线", "电王 圣剑形态", "圣剑", 3500, "estimated", "normal",
         ["电王", "deno", "圣剑", "shf"]),
    ]),

    ("kiva", "Kiva", 2008, "假面骑士Kiva", [
        ("kiva-base", "真骨雕", "", "Kiva", "Kiva", 7700, "confirmed", "hot",
         ["kiva", "キバ", "红渡", "牙"]),
        ("kiva-emperor", "真骨雕", "魔皇形态", "Kiva 魔皇形态", "魔皇", 9900, "confirmed", "hot",
         ["kiva", "魔皇", "emperor", "エンペラー"]),
        ("kiva-shf", "SHF", "早期普通线", "Kiva", "Kiva", 3500, "estimated", "cold",
         ["kiva", "shf"]),
    ]),

    ("decade", "Decade", 2009, "假面骑士Decade", [
        ("decade-base", "真骨雕", "", "Decade", "Decade", 6600, "confirmed", "hot",
         ["decade", "帝骑", "ディケイド", "门矢士"]),
        ("decade-complete", "真骨雕", "完全形态", "Decade 完全形态", "完全", 8250, "confirmed", "hot",
         ["decade", "帝骑", "完全", "complete", "コンプリート"]),
        ("decade-shf", "SHF", "早期普通线", "Decade", "Decade", 3500, "estimated", "normal",
         ["decade", "帝骑", "shf"]),
    ]),

    ("w", "W", 2009, "假面骑士W", [
        ("w-cj", "真骨雕", "", "W 旋风王牌", "旋风王牌", 7700, "estimated", "hot",
         ["w", "double", "ダブル", "cj", "旋风王牌", "cyclone", "joker", "左翔太郎"]),
        ("w-fang", "真骨雕", "獠牙王牌", "W 獠牙王牌", "獠牙王牌", 8800, "estimated", "hot",
         ["w", "double", "獠牙", "fang", "fj", "ファング"]),
        ("w-cjx", "真骨雕", "疾风王牌极致", "W 疾风王牌极致", "极致", 11000, "confirmed", "hot",
         ["w", "double", "极致", "cjx", "extreme", "エクストリーム"]),
        ("w-shf-cj", "SHF", "", "W 旋风王牌", "旋风王牌", 4400, "estimated", "normal",
         ["w", "double", "旋风王牌", "shf"]),
    ]),

    ("ooo", "OOO", 2010, "假面骑士OOO", [
        ("ooo-tatoba", "真骨雕", "", "OOO 鹰虎蝗联组", "鹰虎蝗", 6600, "confirmed", "hot",
         ["ooo", "欧兹", "オーズ", "tatoba", "鹰虎蝗", "火野映司", "タトバ"]),
        ("ooo-gatakiriba", "真骨雕", "", "OOO 锹螳蝗联组", "锹螳蝗", 7150, "confirmed", "normal",
         ["ooo", "欧兹", "gatakiriba", "锹螳蝗", "虫系", "ガタキリバ"]),
        ("ooo-latorartar", "真骨雕", "", "OOO 狮虎豹联组", "狮虎豹", 7150, "confirmed", "normal",
         ["ooo", "欧兹", "latorartar", "狮虎豹", "猫科", "ラトラーター"]),
        ("ooo-tajadol", "真骨雕", "", "OOO 鹰雀鹫联组", "鹰雀鹫", 8250, "confirmed", "hot",
         ["ooo", "欧兹", "tajadol", "鹰雀鹫", "鸟系", "タジャドル"]),
        ("ooo-tamashiy", "真骨雕", "", "OOO 鹰鳗章联组", "鹰鳗章", 7150, "confirmed", "normal",
         ["ooo", "欧兹", "tamashiy", "鹰鳗章", "タマシー"]),
        ("ooo-shauta", "真骨雕", "", "OOO 鲨鳗章联组", "鲨鳗章", 8250, "confirmed", "normal",
         ["ooo", "欧兹", "shauta", "鲨鳗章", "水系", "シャウタ"]),
        ("ooo-sagohzo", "真骨雕", "", "OOO 犀猩象联组", "犀猩象", 8250, "confirmed", "normal",
         ["ooo", "欧兹", "sagohzo", "犀猩象", "重力", "サゴーゾ"]),
        ("ooo-super-tatoba", "真骨雕", "超级联组", "OOO 超级鹰虎蝗", "超级鹰虎蝗", 7700, "confirmed", "hot",
         ["ooo", "欧兹", "supertatoba", "超级鹰虎蝗", "超级", "スーパータトバ"]),
        ("ooo-burakawani", "真骨雕", "", "OOO 蛇龟鳄联组", "蛇龟鳄", 7700, "confirmed", "normal",
         ["ooo", "欧兹", "burakawani", "蛇龟鳄", "ブラカワニ"]),
        ("ooo-tajadol-eternity", "真骨雕", "魂 Web 限定", "OOO 永恒鸟", "永恒鸟", 9900, "confirmed", "hot",
         ["ooo", "欧兹", "eternity", "永恒鸟", "エタニティ"]),
        ("ooo-shf-tatoba", "SHF", "早期普通线", "OOO 鹰虎蝗联组", "鹰虎蝗", 3500, "estimated", "normal",
         ["ooo", "欧兹", "鹰虎蝗", "shf"]),
    ]),

    # Fourze：真骨雕至今未推出，只有 2012 年的普通 SHF
    ("fourze", "Fourze", 2011, "假面骑士Fourze", [
        ("fourze-base", "SHF", "2012 年初版", "Fourze 基础状态", "基础状态", 2800, "confirmed", "cold",
         ["fourze", "卌骑", "フォーゼ", "如月弦太朗", "基础"]),
        ("fourze-elek", "SHF", "强化形态", "Fourze 电力状态", "电力状态", 3500, "estimated", "cold",
         ["fourze", "卌骑", "电力", "elek", "shf"]),
    ]),

    ("wizard", "Wizard", 2012, "假面骑士Wizard", [
        ("wizard-flame", "真骨雕", "", "Wizard 火焰风格", "火焰", 8030, "confirmed", "normal",
         ["wizard", "巫骑", "ウィザード", "操真晴人", "火焰"]),
        ("wizard-allragon", "真骨雕", "火焰龙与全龙", "Wizard 全龙形态", "全龙", 9900, "estimated", "normal",
         ["wizard", "巫骑", "全龙", "allragon", "ドラゴン"]),
        ("wizard-shf", "SHF", "早期普通线", "Wizard 火焰风格", "火焰", 3500, "estimated", "cold",
         ["wizard", "巫骑", "火焰", "shf"]),
    ]),

    ("gaim", "铠武", 2013, "假面骑士铠武", [
        ("gaim-orange", "真骨雕", "2024 年发售", "铠武 橙子铠甲", "橙子", 8800, "estimated", "hot",
         ["铠武", "gaim", "ガイム", "橙子", "orange", "葛叶纮汰"]),
        ("gaim-jinba", "真骨雕", "2025 会场限定", "铠武 阵羽柠檬铠甲", "阵羽", 13750, "confirmed", "hot",
         ["铠武", "gaim", "ガイム", "阵羽", "阵羽织", "jinba", "ジンバー", "柠檬", "lemon", "会场限定"]),
        ("gaim-shf", "SHF", "", "铠武 橙子铠甲", "橙子", 4400, "estimated", "normal",
         ["铠武", "gaim", "橙子", "shf"]),
        ("gaim-kiwami-shf", "SHF", "最终形态", "铠武 极形态", "极形态", 3500, "estimated", "cold",
         ["铠武", "gaim", "极", "kiwami", "極", "shf"]),
    ]),

    # 以下 5 位（Drive / Ghost / Ex-Aid / Build / Zi-O）都没有真骨雕，
    # 2024 年那批是普通 SHF 的再版，定价 7,700 日元
    ("drive", "Drive", 2014, "假面骑士Drive", [
        ("drive-speed", "SHF", "2024 再版", "Drive 速度形态", "速度", 7700, "confirmed", "hot",
         ["drive", "驰骑", "ドライブ", "泊进之介", "速度", "speed"]),
        ("drive-tridoron", "SHF", "最终形态", "Drive 类型托莱多", "托莱多", 5500, "estimated", "normal",
         ["drive", "驰骑", "托莱多", "tridoron", "トライドロン"]),
    ]),

    ("ghost", "Ghost", 2015, "假面骑士Ghost", [
        ("ghost-ore", "SHF", "2024 再版", "Ghost 我魂", "我魂", 7700, "confirmed", "cold",
         ["ghost", "灵骑", "ゴースト", "天空寺尊", "我魂", "ore"]),
        # 2027 年 5 月首次发售的魂 Web 限定商品，官方定价 13,200 日元（已核实）
        ("ghost-mugen", "SHF", "最终形态", "Ghost 无限魂", "无限魂", 13200, "confirmed", "normal",
         ["ghost", "灵骑", "无限魂", "mugen", "ムゲン"]),
    ]),

    ("exaid", "Ex-Aid", 2016, "假面骑士Ex-Aid", [
        ("exaid-lv2", "SHF", "2024 再版", "Ex-Aid 动作玩家 Lv2", "动作玩家", 7700, "confirmed", "normal",
         ["ex-aid", "exaid", "エグゼイド", "宝生永梦", "动作玩家", "lv2"]),
        ("exaid-muteki", "SHF", "最终形态", "Ex-Aid 无敌玩家", "无敌玩家", 5500, "estimated", "normal",
         ["ex-aid", "exaid", "无敌", "muteki", "ムテキ"]),
    ]),

    ("build", "Build", 2017, "假面骑士Build", [
        ("build-rabbit", "SHF", "2024 再版", "Build 兔兔坦克", "兔兔坦克", 7700, "confirmed", "hot",
         ["build", "创骑", "ビルド", "桐生战兔", "兔兔坦克", "rabbittank"]),
        ("build-genius", "SHF", "最终形态", "Build 天才形态", "天才", 5500, "estimated", "normal",
         ["build", "创骑", "天才", "genius", "ジーニアス"]),
        ("build-crossz", "SHF", "", "Cross-Z", "Cross-Z", 5500, "estimated", "normal",
         ["cross-z", "crossz", "克罗兹", "万丈龙我"]),
    ]),

    ("zio", "Zi-O", 2018, "假面骑士Zi-O", [
        ("zio-base", "SHF", "2024 再版", "Zi-O", "Zi-O", 7700, "confirmed", "normal",
         ["zi-o", "zio", "ジオウ", "常磐庄吾", "时王"]),
        ("zio-ohma", "SHF", "最终形态", "Zi-O 王样形态", "王样", 5500, "estimated", "normal",
         ["zi-o", "zio", "王样", "ohma", "オーマ"]),
        ("geiz-shf", "SHF", "", "Geiz", "Geiz", 3500, "estimated", "normal",
         ["geiz", "盖茨", "ゲイツ", "明光院盖茨"]),
    ]),
]

# ---------------------------------------------------------------- 报价生成
SHOP_TAOBAO = ["万代官方旗舰店", "正版模玩专营", "昭和骑士馆", "令和骑士馆",
               "假面骑士专卖", "港版模玩仓", "模玩时代", "骑士二手铺", "魂模玩"]
SHOP_TMALL = ["万代天猫旗舰店", "BANDAI 官方旗舰店", "万代南梦宫专营店", "万代模型官方店"]
SHOP_XIANYU = ["退坑玩家", "清柜子", "模型清仓号", "自提优惠", "小瑕疵处理",
               "假面骑士同好", "毕业出坑", "只收主骑", "收藏换米"]

# 产品热度系数：热门真骨雕长期溢价，冷门普通 SHF 打折出
HEAT = {"hot": 1.20, "normal": 1.00, "cold": 0.82}

# 平台价格系数区间（相对官方定价折人民币）
BAND = {
    "TAOBAO_NEW": (0.96, 1.10),
    "TAOBAO_USED": (0.74, 0.90),
    "TMALL_NEW": (1.02, 1.16),
    "XIANYU_NEW": (0.84, 1.00),
    "XIANYU_USED": (0.72, 0.98),
    "KO": (0.09, 0.18),
}


def rnd(key, tag):
    """确定性随机：同一型号每次生成结果一致，便于复核。"""
    h = hashlib.md5(f"{key}|{tag}".encode("utf-8")).hexdigest()
    return random.Random(int(h[:12], 16))


def price_of(key, tag, base, band):
    r = rnd(key, tag)
    lo, hi = band
    return round(base * r.uniform(lo, hi), 0)


def ship_of(key, tag, platform):
    r = rnd(key, tag + "-ship")
    if platform == "TMALL":
        return 0
    if platform == "TAOBAO":
        return 0 if r.random() < 0.68 else float(r.choice([8, 10, 12, 15]))
    return 0 if r.random() < 0.42 else float(r.choice([8, 10, 12, 15]))


def want_of(key, tag, heat):
    r = rnd(key, tag + "-want")
    band = {"hot": (110, 420), "normal": (28, 150), "cold": (6, 55)}[heat]
    return r.randint(*band)


def make_title(model, platform, condition, ko=False):
    """标题必须与该条的成色一致，否则页面上会自相矛盾。"""
    nm = model["name"]
    line = "" if model["line"] == "SHF" else "真骨雕 "
    ver = model.get("ver", "")
    tail = f" {ver}" if ver else ""

    if ko:
        return f"KO版 祖国版 {nm} 高仿 手办 便宜出"

    if platform == "TMALL":
        # 官方渠道，不写成色以外的花样
        return f"BANDAI 万代 S.H.Figuarts {line}{nm}{tail} 正版 现货"

    if platform == "TAOBAO":
        if condition == "全新":
            return f"万代 S.H.Figuarts {line}{nm}{tail} 全新未拆 现货 顺丰"
        return f"万代 S.H.Figuarts {line}{nm}{tail} 二手 配件齐 看图"

    # 闲鱼
    if condition == "全新":
        return f"全新未拆 SHF {line}{nm} 原盒 转手 便宜"
    if condition == "仅开封":
        return f"仅开封 SHF {line}{nm} 只验货 未把玩 原盒"
    return f"出 SHF {line}{nm} 95新 原盒 配件齐 可议"


def build():
    models, items = [], []

    for rider_key, rider_cn, year, series, vers in RIDERS:
        for (key, line, ver, name, short, jpy, src, heat, alias) in vers:
            models.append({
                "key": key,
                "rider": rider_key,
                "riderCn": rider_cn,
                "year": year,
                "series": series,
                "line": line,
                "ver": ver,
                "name": "假面骑士 " + name,
                "short": short,
                "alias": alias,
                "image": MODEL_IMAGES.get(key),
                "productPage": PRODUCT_PAGES.get(key, ""),
                "officialJpy": jpy,
                "priceSrc": src,
                "heat": heat,
            })

            # 两种基准：第三方与二手吃热度溢价；官方渠道按官方定价，不跟着炒
            base = jpy * JPY_TO_CNY * HEAT[heat]
            base_off = jpy * JPY_TO_CNY

            # 淘宝 2 条（1 全新 1 二手）
            items.append({
                "modelKey": key, "platform": "TAOBAO",
                "title": make_title({"name": name, "line": line, "ver": ver}, "TAOBAO", "全新"),
                "price": price_of(key, "tb1", base, BAND["TAOBAO_NEW"]),
                "shipping": ship_of(key, "tb1", "TAOBAO"),
                "condition": "全新", "official": True,
                "shopName": rnd(key, "tb1-shop").choice(SHOP_TAOBAO),
                "wantCount": want_of(key, "tb1", heat),
            })
            items.append({
                "modelKey": key, "platform": "TAOBAO",
                "title": make_title({"name": name, "line": line, "ver": ver}, "TAOBAO", "二手"),
                "price": price_of(key, "tb2", base, BAND["TAOBAO_USED"]),
                "shipping": ship_of(key, "tb2", "TAOBAO"),
                "condition": "二手", "official": True,
                "shopName": rnd(key, "tb2-shop").choice(SHOP_TAOBAO),
                "wantCount": want_of(key, "tb2", heat),
            })
            # 天猫 1 条（官方渠道，按官方定价，不吃热度溢价）
            items.append({
                "modelKey": key, "platform": "TMALL",
                "title": make_title({"name": name, "line": line, "ver": ver}, "TMALL", "全新"),
                "price": price_of(key, "tm1", base_off, BAND["TMALL_NEW"]),
                "shipping": 0,
                "condition": "全新", "official": True,
                "shopName": rnd(key, "tm1-shop").choice(SHOP_TMALL),
                "wantCount": want_of(key, "tm1", heat),
            })
            # 闲鱼 2 条。第二条先定成色，再据此写标题，否则标题会和成色打架
            items.append({
                "modelKey": key, "platform": "XIANYU",
                "title": make_title({"name": name, "line": line, "ver": ver}, "XIANYU", "二手"),
                "price": price_of(key, "xy1", base, BAND["XIANYU_USED"]),
                "shipping": ship_of(key, "xy1", "XIANYU"),
                "condition": "二手", "official": True,
                "shopName": rnd(key, "xy1-shop").choice(SHOP_XIANYU),
                "wantCount": want_of(key, "xy1", heat),
            })
            cond2 = "全新" if rnd(key, "xy2c").random() > 0.35 else "仅开封"
            items.append({
                "modelKey": key, "platform": "XIANYU",
                "title": make_title({"name": name, "line": line, "ver": ver}, "XIANYU", cond2),
                "price": price_of(key, "xy2", base, BAND["XIANYU_NEW"]),
                "shipping": ship_of(key, "xy2", "XIANYU"),
                "condition": cond2,
                "official": True,
                "shopName": rnd(key, "xy2-shop").choice(SHOP_XIANYU),
                "wantCount": want_of(key, "xy2", heat),
            })

            # KO 版：只有热门款才有人做仿品，约 45%
            ko_r = rnd(key, "ko-flag")
            if heat == "hot" and ko_r.random() < 0.62:
                items.append({
                    "modelKey": key, "platform": "TAOBAO",
                    "title": make_title({"name": name, "line": line, "ver": ver}, "TAOBAO", "全新", ko=True),
                    "price": price_of(key, "ko1", base, BAND["KO"]),
                    "shipping": 0 if ko_r.random() < 0.5 else 6,
                    "condition": "全新", "official": False,
                    "shopName": "低价模型铺",
                    "wantCount": ko_r.randint(40, 260),
                })

    for it in items:
        it["itemUrl"] = ITEM_URL_OVERRIDES.get(
            "%s|%s|%s" % (it["modelKey"], it["platform"], it["condition"]), "")

    return models, items


LIVE_FILE = Path(__file__).parent / "live_prices.json"


def merge_live(models, items):
    """把真实抓取结果合并进来：同一型号一旦有真实在售，就用真实数据替换该型号的样本报价。
    抓不到的型号继续用样本，并在前端标注「参考价」。"""
    if not LIVE_FILE.exists():
        return models, items, None
    try:
        data = json.loads(LIVE_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"live_prices.json 解析失败，跳过：{e}")
        return models, items, None

    live = [x for x in (data.get("items") or []) if x.get("modelKey") and x.get("price")]
    if not live:
        print("live_prices.json 里没有有效条目，保持样本数据")
        return models, items, None

    for x in live:
        x["live"] = True

    got = {x["modelKey"] for x in live}
    kept = [i for i in items if i["modelKey"] not in got]
    merged = kept + live
    merged.sort(key=lambda i: (i["modelKey"], i["platform"], i["condition"]))

    meta = {
        "fetchedAt": data.get("fetchedAt") or "",
        "count": len(live),
        "models": len(got),
        "carried": data.get("carried") or 0,
        "platforms": sorted({x["platform"] for x in live}),
        "source": data.get("source") or "",
    }
    return models, merged, meta


def main():
    models, items = build()
    models, items, live_meta = merge_live(models, items)

    js_models = json.dumps(models, ensure_ascii=False, indent=2)
    js_items = json.dumps(items, ensure_ascii=False, indent=2)

    if live_meta:
        live_note = (
            "真实抓取已合并：" + str(live_meta["count"]) + " 条在售报价覆盖 "
            + str(live_meta["models"]) + " 个型号，抓取于 " + live_meta["fetchedAt"]
            + "，来源 " + "/".join(live_meta["platforms"]) + "。\n"
            "      live=true 的条目为真实在售、带商品链接；其余型号仍为参考样本。"
        )
    else:
        live_note = "注意：本文件是离线样本，不是实时抓取。真实采集需各平台登录态。"

    header = f"""/* =====================================================================
   SHF 猎手 · 演示数据（自动生成，请勿手工改这个文件）
   ---------------------------------------------------------------------
   范围：平成 20 位主骑 × S.H.Figuarts（真骨雕制法 / 普通 SHF）

   共 {len(models)} 个型号、{len(items)} 条商品报价、覆盖 20 位主骑。

   数据口径
     ① 型号名、所属作品、版本（55th / 20th / 生存形态…）来自万代公开资料。
     ② 官方定价标 priceSrc="confirmed" 的，是公开页面核实过的实际日元定价；
        标 "estimated" 的按同期同产品线价格带推算（真骨雕 7,700–9,900，
        普通 SHF 3,500–5,500），页面不声称逐款核实。
     ③ 各平台挂单价是按行情规律构造的样本：官方定价折人民币 × 热度系数 ×
        平台系数，带确定性随机（同一型号每次生成一致）。规则见 gen_data.py，
        可重跑复现，没有手工编造的个别数字。
     ④ image 字段为实物图路径（见 gen_data.py 的 MODEL_IMAGES）。为空时前端
        显示文字占位封面，不冒充实物照片；图片来源须可核查。

   汇率：100 日元 ≈ 4.75 元（2026-11 近似）
   {live_note}
   ===================================================================== */

"""

    js = header
    js += "const MODELS = " + js_models + ";\n\n"
    js += "/* 商品条目\n   official: true = 正版；false = KO 版 / 祖国版，标红且不参与「最低价」评选\n   condition: 全新 / 二手 / 仅开封 */\n"
    js += "const ITEMS = " + js_items + ";\n\n"
    js += "/* 真实抓取元信息；null 表示当前全部为参考样本 */\n"
    js += "const LIVE_META = " + json.dumps(live_meta, ensure_ascii=False) + ";\n\n"
    js += """/* 平台跳转：有真实商品页时直达商品，没有时按完整型号名做精确搜索。
   演示站的报价是离线样本，不含真实商品 ID，故不伪造商品详情链接。 */
function platformSearchUrl(platform, keyword) {
  const q = encodeURIComponent(keyword);
  switch (platform) {
    case 'TAOBAO': return 'https://s.taobao.com/search?q=' + q;
    case 'TMALL':  return 'https://list.tmall.com/search_product.htm?q=' + q;
    case 'XIANYU': return 'https://www.goofish.com/search?q=' + q;
    default: return '#';
  }
}
"""

    p = Path(__file__).parent / "data.js"
    p.write_text(js, encoding="utf-8")

    # 统计
    riders = {m["rider"] for m in models}
    print(f"型号 {len(models)} 个 / 主骑 {len(riders)} 位 / 报价 {len(items)} 条")
    print(f"data.js 大小 {p.stat().st_size/1024:.1f} KB")

    conf = sum(1 for m in models if m["priceSrc"] == "confirmed")
    print(f"官方定价：核实 {conf} 款 / 推算 {len(models)-conf} 款")
    print(f"已配实物图 {sum(1 for m in models if m['image'])} / {len(models)} 款")
    print(f"官方商品页 {sum(1 for m in models if m.get('productPage'))} / {len(models)} 款；"
          f"单条商品链接 {sum(1 for i in items if i.get('itemUrl'))} / {len(items)} 条")
    ko = sum(1 for i in items if not i["official"])
    print(f"KO 版样本 {ko} 条")


if __name__ == "__main__":
    main()
