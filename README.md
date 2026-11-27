# SHF 猎手 · 假面骑士比价

万代 S.H.Figuarts 假面骑士（平成 20 主骑 · 真骨雕 / 普通 SHF）比价工具。
每天自动抓一次闲鱼真实在售，更新最低价与商品图，页面打开即查，不需要注册。

独立网址：`https://<你的用户名>.github.io/<仓库名>/`

| 项 | 数量 |
|---|---|
| 主骑 | 20 位（空我 → Zi-O，2000–2019） |
| 型号 / 版本 | 73 个（真骨雕 42 + 普通 SHF 31） |
| 官方定价 | 37 款公开页面核实 / 36 款推算 |
| 型号主图 | 9 款（来源见 `models/sources.csv`） |

剑、Fourze、Drive、Ghost、Ex-Aid、Build、Zi-O 这 7 位万代至今没出过真骨雕，
页面上只记普通 SHF，不虚构。

---

## 一、发布到 GitHub Pages（首次，约 5 分钟）

### 1. 建仓库

在 GitHub 新建一个 **Public** 仓库，名字随意，例如 `shf-radar`。
**不要**勾选自动生成 README，保持空仓库。

### 2. 推代码

在本目录执行（把地址换成你自己的）：

```bash
git remote add origin https://github.com/<你的用户名>/shf-radar.git
git branch -M main
git push -u origin main
```

第一次 push 会要求登录。密码位置填 **Personal Access Token**（GitHub 已不支持账号密码）：
头像 → Settings → Developer settings → Personal access tokens → Tokens (classic) →
Generate new token → 勾选 `repo` 和 `workflow` → 复制生成的串。

### 3. 打开 Pages

仓库 → Settings → Pages → **Build and deployment** → Source 选 **GitHub Actions**。
不做这一步，推了也不会出网页。

### 4. 配闲鱼登录态（关键）

没有登录态，抓取只能拿到空列表，页面就只剩参考价。

```bash
python tools/fetch_live.py --login
```

浏览器会打开闲鱼，扫码登录。脚本检测到登录后自动导出两个文件：

- `tools/state.json` — 登录态原始文件（**不要提交**，已在 `.gitignore`）
- `tools/state.b64` — 同内容的 Base64，用来贴进 GitHub

然后到仓库 → Settings → Secrets and variables → Actions → **New repository secret**：

- Name：`XIANYU_STATE`
- Secret：把 `tools/state.b64` 的**全部内容**粘进去（一长串，不要换行）

### 5. 跑一次

仓库 → Actions → 左侧「每日行情刷新与发布」→ 右侧 **Run workflow**。

跑完看日志；成功后 `https://<用户名>.github.io/<仓库名>/` 就是你的独立网址。

---

## 二、每天自动刷新

`.github/workflows/daily.yml` 每天北京时间 **06:10** 自动执行：

1. 还原登录态
2. 抓取 73 个型号的真实在售（含商品图）
3. 重新生成 `data.js`
4. 提交数据变更
5. 发布到 Pages

手动刷新：Actions → Run workflow。

**登录态失效怎么办**：闲鱼 Cookie 一般能撑几天到几周。失效的表现是抓取返回 0 条，
日志出现「本次 0 条…保留上一版」，页面不会变空，只是价格停在最后一次成功的时间。
重跑一遍第 4 步换掉 `XIANYU_STATE` 即可。

---

## 三、数据口径

| 类型 | 来源 | 页面标记 |
|---|---|---|
| 实时在售 | 闲鱼搜索结果，每天抓取 | 「实时在售」，点开即真实商品页 |
| 参考价 | 官方定价折人民币 × 行情系数推算 | 「参考价」，走平台精确搜索 |
| 官方定价 | 万代官网 / Hpoi 商品页核实（37 款） | 「已核实 / 推算」 |

- 到手价 = 商品价 + 运费。闲鱼列表不含运费字段，这类报价标「运费另计」，以商品页为准。
- KO 版 / 祖国版保留在候选里并标红，但**不参与**最低价评选。
- 抓不到就是 0 条，不编造。

---

## 四、本地预览与开发

```bash
python -m http.server 8199
# 打开 http://127.0.0.1:8199
```

只改型号库时，重跑 `python gen_data.py` 即可，不必抓取。

```bash
python tools/fetch_live.py --probe "铠武 阵羽柠檬"   # 抓一个词看效果
python tools/fetch_live.py --keys gaim-jinba         # 只抓指定型号
python tools/fetch_live.py --all --limit 10          # 限量抓取
```

---

## 五、目录

```
index.html / app.js / styles.css   页面
data.js                            数据（gen_data.py 生成，勿手改）
gen_data.py                        型号库与数据生成
live_prices.json                   抓取结果
models/                            型号主图（9 款，来源见 sources.csv）
models/live/                       抓取到的商品图
tools/fetch_live.py                抓取器
.github/workflows/daily.yml        每日自动刷新
```
