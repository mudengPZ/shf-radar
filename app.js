/* =====================================================================
   SHF 猎手 · 假面骑士比价（演示版）
   无框架、无构建。数据来自 data.js：真实抓取条目（live=true）与参考样本混合，
   匹配与比价逻辑在前端完成，
   规则与后端 shf-price 的 PriceCompareService 保持一致：
     · 到手价 = 价格 + 运费
     · 最低价只在正版里取，KO 版不参与评选但保留在候选里并标红
     · 该型号没有正版时，才回退到全局最低并给出警告

   导航是两层：
     首屏 = 平成 20 位主骑（每位一张卡，显示该骑士当前最低到手价）
     点进去 = 该主骑的各版本（真骨雕 / 普通 SHF × 形态）
     再点进去 = 单版本的三平台报价
   ===================================================================== */

(function () {
  'use strict';

  const PLATFORM_CN = { TAOBAO: '淘宝', TMALL: '天猫', XIANYU: '闲鱼' };

  const state = {
    keyword: '',
    line: 'ALL',
    platforms: new Set(['TAOBAO', 'TMALL', 'XIANYU']),
    cond: 'ANY',
    matched: [],
    allMatched: [],
    rider: null,        // 当前展开的主骑
    activeKey: null     // 当前展开的版本
  };

  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));

  const esc = s => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

  const money = n => (n == null || isNaN(n)) ? '—'
    : Number(n).toFixed(Number(n) % 1 === 0 ? 0 : 2);

  const total = it => Number(it.price || 0) + Number(it.shipping || 0);

  // 搜索词：完整型号名 + 产品线 + 版本，比只搜骑士名更接近目标商品
  function searchTerm(m, platform) {
    const base = m.name.replace(/^假面骑士\s*/, '').trim();
    const lw = m.line === '真骨雕' ? '真骨雕' : 'SHF';
    const ver = (m.ver || '').trim();
    const tail = ver ? ' ' + ver : '';
    return platform === 'XIANYU'
      ? base + ' ' + lw + tail
      : '万代 ' + lw + ' ' + base + tail;
  }

  // 有真实商品链接就直达，没有才回退到平台精确搜索
  function itemHref(it, m) {
    return it.itemUrl || platformSearchUrl(it.platform, searchTerm(m, it.platform));
  }

  const itemLabel = it => (it.itemUrl ? '商品页 ↗' : '搜同款 ↗');

  /* ---------------- 匹配 ---------------- */
  function modelIndex(m) {
    return [
      m.name, m.series, m.line, m.ver, m.riderCn, m.key,
      ...(m.alias || [])
    ].map(x => String(x == null ? '' : x).toLowerCase());
  }

  function matchModels(kw) {
    const raw = String(kw || '').trim().toLowerCase();
    if (!raw) return [];

    const tokens = raw.split(/\s+/).filter(Boolean);

    // 主策略：每个词都要落在同一个型号上（AND）
    // 单字符只认精确匹配，否则 "w" 会误伤所有含 w 的字段
    const hit = (fields, t) => fields.some(f => f === t || (t.length >= 2 && f.includes(t)));
    const strict = MODELS.filter(m => {
      const idx = modelIndex(m);
      return tokens.every(t => hit(idx, t));
    });
    if (strict.length) return strict;

    // 兜底：整串包含（应对「空我55」「blackrx」这类连写）
    return MODELS.filter(m => modelIndex(m).some(f => f.includes(raw) || raw.includes(f)));
  }

  /* ---------------- 取数 + 比价 ---------------- */
  function collect(model) {
    let list = ITEMS.filter(it => it.modelKey === model.key);
    list = list.filter(it => state.platforms.has(it.platform));
    if (state.cond === 'NEW') list = list.filter(it => it.condition === '全新');
    return list.sort((a, b) => total(a) - total(b));
  }

  function analyse(model) {
    const cands = collect(model);
    const official = cands.filter(it => it.official);
    const koCount = cands.length - official.length;

    const warnings = [];
    let lowest = official[0] || null;

    if (!lowest && cands.length) {
      lowest = cands[0];
      warnings.push('该型号在当前筛选条件下没有正版在售，最低价取自非官方版本，请自行判断真伪。');
    }
    if (koCount > 0) {
      warnings.push('结果里有 ' + koCount + ' 条 KO 版 / 祖国版报价，已单独标出，不参与「正版最低价」评选。');
    }
    if (!cands.length) {
      warnings.push('当前筛选条件下没有可用报价，试着放宽平台或成色。');
    }

    return { model, cands, lowest, warnings, koCount };
  }

  // 受当前筛选影响的型号集合
  function visibleModels() {
    return MODELS.filter(m => state.line === 'ALL' || m.line === state.line);
  }

  function ridersOf(list) {
    const map = new Map();
    list.forEach(m => {
      if (!map.has(m.rider)) {
        map.set(m.rider, { key: m.rider, cn: m.riderCn, year: m.year, series: m.series, models: [] });
      }
      map.get(m.rider).models.push(m);
    });
    return Array.from(map.values()).sort((a, b) => a.year - b.year);
  }

  // 某位主骑在两条产品线里各自的最低正版到手价
  // 不能只给一个「全场最低」—— 真骨雕和普通 SHF 差着两三倍价，
  // 混成一个数字会让人以为 157 能买到真骨雕
  function riderBest(r) {
    const res = {
      '真骨雕': { price: null, model: null },
      'SHF': { price: null, model: null }
    };
    r.models.forEach(m => {
      const a = analyse(m);
      const slot = res[m.line];
      if (a.lowest && slot) {
        const t = total(a.lowest);
        if (slot.price == null || t < slot.price) {
          slot.price = t;
          slot.model = m;
        }
      }
    });
    return res;
  }

  /* ---------------- 渲染小件 ---------------- */
  function lineTag(line) {
    return line === '真骨雕'
      ? '<span class="tag gold">真骨雕制法</span>'
      : '<span class="tag blue">普通 SHF</span>';
  }

  function editionTag(it) {
    return it.official
      ? '<span class="tag green">正版</span>'
      : '<span class="tag red">KO / 祖国版</span>';
  }

  // 数据来源标记：真实抓取 vs 参考样本，两处都要能一眼分辨
  function srcTag(it) {
    return it && it.live
      ? '<span class="tag live">实时在售</span>'
      : '<span class="tag est">参考价</span>';
  }

  // 封面：型号配了 image 就显示实物图，加载失败或未配图回退到文字海报
  // 文字海报只用型号名，不冒充实物照片；small 版只放形态名，避免重复
  function cover(model, small) {
    const nm = small
      ? (model.short || model.name.replace(/^假面骑士\s*/, ''))
      : model.name.replace(/^假面骑士\s*/, '');
    const line = model.line === '真骨雕' ? 'SHINKOCCHOU SEIHOU' : 'S.H.FIGUARTS';
    const inner = small
      ? `<div class="k2">${esc(nm)}</div><div class="k3">${line}</div>`
      : `<div class="k1">KAMEN RIDER</div><div class="k2">${esc(nm)}</div><div class="k3">${line}</div>`;
    if (!model.image) return `<div class="fk">${inner}</div>`;

    return `<div class="fk has-photo">
      <img src="${esc(model.image)}" alt="${esc(model.name)} 实物图" loading="lazy"
           onerror="this.style.display='none';this.parentNode.classList.add('photo-failed')">
      <div class="fk-fallback">${inner}</div>
    </div>`;
  }

  // 单条商品自己的图优先（真实抓取时每条都带自己的商品图），没有才退回型号图
  function itemCover(it, model, small) {
    if (!it || !it.image) return cover(model, small);
    const nm = small
      ? (model.short || model.name.replace(/^假面骑士\s*/, ''))
      : model.name.replace(/^假面骑士\s*/, '');
    const line = model.line === '真骨雕' ? 'SHINKOCCHOU SEIHOU' : 'S.H.FIGUARTS';
    const inner = small
      ? `<div class="k2">${esc(nm)}</div><div class="k3">${line}</div>`
      : `<div class="k1">KAMEN RIDER</div><div class="k2">${esc(nm)}</div><div class="k3">${line}</div>`;
    return `<div class="fk has-photo">
      <img src="${esc(it.image)}" alt="${esc(it.title || model.name)}" loading="lazy"
           onerror="this.style.display='none';this.parentNode.classList.add('photo-failed')">
      <div class="fk-fallback">${inner}</div>
    </div>`;
  }

  /* ---------------- 单型号详情 ---------------- */
  function renderDetail(a) {
    const m = a.model;
    let html = '';

    if (a.lowest) {
      const low = a.lowest;
      const sf = Number(low.shipping || 0);
      const jpyNote = m.officialJpy
        ? `官方定价 ${m.officialJpy.toLocaleString()} 日元 ≈ ¥${Math.round(m.officialJpy * 0.0475)}`
          + (m.priceSrc === 'confirmed' ? '（已核实）' : '（按同期产品线推算）')
        : '';
      html += `
      <div class="result-head">
        <h2>${esc(m.name)}${m.ver ? ' · ' + esc(m.ver) : ''}</h2>
        <span class="cnt">共 ${a.cands.length} 条候选 · 覆盖 ${new Set(a.cands.map(i => i.platform)).size} 个平台</span>
        <div class="rule"></div>
      </div>

      <div class="lowest">
        <div class="thumb">${itemCover(low, m, false)}</div>
        <div class="body">
          <div class="eyebrow">LOWEST · ${esc(PLATFORM_CN[low.platform] || low.platform)}${srcTag(low)}</div>
          <div class="price"><small>¥</small>${money(total(low))}</div>
          <div class="calc">
            到手价 = ${money(low.price)}${sf > 0
              ? ' + ' + money(sf) + ' 运费'
              : (low.shippingNote ? ' · 运费未含' : ' · 包邮')}
            　·　${esc(low.condition)}
          </div>
          <div class="title">${esc(low.title)}</div>
          ${m.productPage ? `<div class="src"><a href="${esc(m.productPage)}" target="_blank" rel="noopener">查看官方商品页 ↗</a><span>该型号的商品介绍页，含官方定价</span></div>` : ''}
          <div class="meta">
            ${lineTag(m.line)}
            ${editionTag(low)}
            <span>${esc(low.shopName)}</span>
            ${low.wantCount ? `<span>${low.wantCount} 人想要</span>` : ''}
            ${low.area ? `<span>${esc(low.area)}</span>` : ''}
          </div>
          <div class="acts">
            <a class="btn accent" href="${itemHref(low, m)}"
               target="_blank" rel="noopener">${low.itemUrl ? '打开商品页 ↗' : '去' + esc(PLATFORM_CN[low.platform]) + '搜同款 ↗'}</a>
            <span class="tip">${jpyNote || esc(m.ver || '')}</span>
          </div>
        </div>
      </div>`;
    }

    if (a.warnings.length) {
      html += `<div class="alert"><span class="ic">!</span><span>${a.warnings.map(esc).join('<br>')}</span></div>`;
    }

    if (a.cands.length) {
      html += `
      <div class="result-head">
        <h2>全部候选</h2>
        <span class="cnt">按到手价升序 · 灰底为 KO 版 / 祖国版</span>
        <div class="rule"></div>
      </div>
      <div class="grid">`;

      a.cands.forEach(it => {
        const isBest = a.lowest && it === a.lowest;
        html += `
        <div class="item ${it.official ? '' : 'dim'} ${isBest ? 'best' : ''}">
          <div class="im">
            ${itemCover(it, m, true).replace('<div class="fk',
              '<div style="' + (it.official ? '' : 'opacity:.75') + '" class="fk')}
            <span class="flag">${editionTag(it)}</span>
          </div>
          <div class="bd">
            <div class="pr"><small>¥</small>${money(total(it))}
              <span class="sf">${Number(it.shipping || 0) > 0
                ? '含' + money(it.shipping) + '运费'
                : (it.shippingNote ? '运费另计' : '包邮')}</span>
            </div>
            <div class="tt">${esc(it.title)}</div>
            <div class="ft">
              <span class="tag blue">${esc(PLATFORM_CN[it.platform])}</span>
              ${srcTag(it)}
              <span>${esc(it.condition)}</span>
              ${it.wantCount ? `<span>${it.wantCount} 想要</span>` : ''}
              <a class="go" href="${itemHref(it, m)}" target="_blank" rel="noopener"
                 title="${it.itemUrl ? '已登记真实商品链接' : '离线样本报价，暂无真实商品页，将按完整型号名精确搜索'}">${itemLabel(it)}</a>
            </div>
          </div>
        </div>`;
      });
      html += '</div>';
    }

    html += `
      <div style="margin-top:22px;font-size:11.5px;color:#9aa0a7;line-height:1.85">
        KO 版不会因为便宜就变成最低价 —— 标红是为了让你看见它为什么便宜，而不是替你藏起来。
        标「实时在售」的是闲鱼真实抓取结果，点「商品页」直达该商品；标「参考价」的是按行情推算的样本，
        没有真实商品 ID，点「搜同款」会按完整型号名打开平台精确搜索，能看到当下的实际挂价。
        闲鱼列表页不含运费字段，这类报价标注「运费另计」，到手价以商品页为准。
      </div>`;

    return html;
  }

  /* ---------------- 主骑卡（首屏） ---------------- */
  function renderRiders(list, title, hint) {
    const riders = ridersOf(list);

    let html = `
      <div class="result-head">
        <h2>${esc(title)}</h2>
        <span class="cnt">${esc(hint)}</span>
        <div class="rule"></div>
      </div>
      <div class="rider-grid">`;

    riders.forEach(r => {
      const best = riderBest(r);
      const gs = r.models.filter(m => m.line === '真骨雕').length;
      const sh = r.models.filter(m => m.line === 'SHF').length;
      const parts = [];
      if (gs) parts.push('真骨雕 ' + gs);
      if (sh) parts.push('SHF ' + sh);

      const lineRow = (label, slot, cls) => {
        if (!slot.price) return '';
        return `<div class="rl ${cls}">
          <span class="rlb">${label}</span>
          <span class="rlp"><small>¥</small>${money(slot.price)}<i class="rlq">起</i></span>
        </div>`;
      };

      const rows = lineRow('真骨雕', best['真骨雕'], 'gold')
                 + lineRow('SHF', best['SHF'], 'blue');

      // 万代确实没给这位出过真骨雕，卡上要说明，否则会被误认为「没收录」
      const noGS = !r.models.some(m => m.line === '真骨雕');

      html += `
      <div class="rcard" data-rider="${esc(r.key)}">
        <div class="rhd">
          <span class="ryr mono">${r.year}</span>
          <span class="rnm">${esc(r.cn)}</span>
          <span class="rgo">→</span>
        </div>
        <div class="rsub">${esc(r.series)}</div>
        <div class="rlines">
          ${rows || '<div class="rl"><span class="rlb">当前筛选下</span><span class="rlp none">无报价</span></div>'}
        </div>
        ${noGS ? '<div class="rnote">万代未推出真骨雕，仅普通 SHF</div>' : ''}
        <div class="rft">
          <span>${parts.join(' · ')}</span>
          <span class="rgo2">看这 ${r.models.length} 个 →</span>
        </div>
      </div>`;
    });

    html += '</div>';
    return html;
  }

  /* ---------------- 某主骑的版本列表 ---------------- */
  function renderRiderPool(r) {
    let html = `
      <div style="margin-top:18px">
        <button class="hot-chip" id="btnBack">← 返回 20 位主骑</button>
      </div>

      <div class="result-head" style="margin-top:20px">
        <h2>${esc(r.cn)} · ${r.models.length} 个版本</h2>
        <span class="cnt">${esc(r.series)} · ${r.year}　点任一版本看三平台报价</span>
        <div class="rule"></div>
      </div>
      <div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(300px,1fr))">`;

    r.models.forEach(m => {
      const a = analyse(m);
      html += `
      <div class="item" data-open="${esc(m.key)}" style="cursor:pointer">
        <div class="im" style="height:96px">${cover(m, true)}</div>
        <div class="bd">
          <div style="display:flex;align-items:center;gap:7px;margin-bottom:7px;flex-wrap:wrap">
            ${lineTag(m.line)}
            ${m.ver ? `<span style="font-size:11px;color:#9aa0a7">${esc(m.ver)}</span>` : ''}
          </div>
          <div style="font-size:14px;font-weight:750;margin-bottom:8px">${esc(m.name.replace(/^假面骑士\s*/, ''))}</div>
          <div class="pr" style="font-size:22px">
            ${a.lowest ? '<small>¥</small>' + money(total(a.lowest)) : '<span style="font-size:13px;color:#9aa0a7">无报价</span>'}
          </div>
          <div class="ft">
            <span>${a.cands.length} 条候选</span>
            ${a.koCount ? `<span>含 ${a.koCount} 条 KO</span>` : ''}
            <span class="go">看详情 →</span>
          </div>
        </div>
      </div>`;
    });

    html += '</div>';

    html += `
      <div class="note" style="margin-top:20px">
        <b>版本怎么看</b>　真骨雕制法（Shinkocchou Seihou）是 S.H.Figuarts 里的高端支线，
        重制比例与关节，定价约为普通线的 1.5–2.5 倍；普通 SHF 是常规线，角色覆盖广、二手更好找。
        同一位骑士的两个版本不要混着比价 —— 先决定买哪条线，再比价。
      </div>`;
    return html;
  }

  /* ---------------- 空态 ---------------- */
  function renderEmpty() {
    const names = ['空我', 'W', 'Faiz', 'Kabuto', '电王', 'OOO', 'Build', 'Zi-O'];
    return `
      <div class="empty">
        <b>没找到「${esc(state.keyword)}」</b>
        当前收录平成 20 位主骑共 ${MODELS.length} 个版本（真骨雕 + 普通 SHF）。<br>
        换个说法试试，或者直接点下面的：
        <div class="sug">
          ${names.map(n => `<button class="hot-chip" data-hot="${esc(n)}">${esc(n)}</button>`).join('')}
        </div>
      </div>`;
  }

  /* ---------------- 主渲染 ---------------- */
  function render() {
    const out = $('#out');

    // 1) 已选中某个版本 —— 直接看详情
    if (state.activeKey) {
      const model = MODELS.find(m => m.key === state.activeKey);
      if (model) {
        const backText = state.rider ? '← 返回 ' + model.riderCn + ' 的版本列表' : '← 返回';
        out.innerHTML = `
          <div style="margin-top:18px">
            <button class="hot-chip" id="btnBack">${backText}</button>
          </div>` + renderDetail(analyse(model));
        $('#btnBack').addEventListener('click', () => {
          state.activeKey = null;
          render();
          window.scrollTo({ top: 240, behavior: 'smooth' });
        });
        return;
      }
      state.activeKey = null;
    }

    // 2) 已选中某位主骑 —— 看他的版本列表
    if (state.rider) {
      const pool = visibleModels().filter(m => m.rider === state.rider);
      if (pool.length) {
        out.innerHTML = renderRiderPool({
          key: state.rider,
          cn: pool[0].riderCn,
          series: pool[0].series,
          year: pool[0].year,
          models: pool
        });
        $('#btnBack').addEventListener('click', () => {
          state.rider = null;
          render();
          window.scrollTo({ top: 240, behavior: 'smooth' });
        });
        bindDynamic();
        return;
      }
      state.rider = null;
    }

    // 3) 没有关键词 —— 首屏铺出 20 位主骑
    if (!state.keyword) {
      const list = visibleModels();
      const n = ridersOf(list).length;
      out.innerHTML = renderRiders(list,
        '平成 ' + n + ' 位主骑 · ' + list.length + ' 个版本',
        '点骑士看他有哪些版本（真骨雕 / 普通 SHF）');
      bindDynamic();
      return;
    }

    // 4) 命中恰好一个版本 —— 直接给比价结果
    if (state.matched.length === 1) {
      state.rider = state.matched[0].rider;
      out.innerHTML = renderDetail(analyse(state.matched[0]));
      return;
    }

    // 5) 命中多个版本，但都属于同一位主骑 —— 直接进他的版本列表
    if (state.matched.length > 1) {
      const set = new Set(state.matched.map(m => m.rider));
      if (set.size === 1) {
        state.rider = state.matched[0].rider;
        out.innerHTML = `
          <div style="margin-top:18px">
            <button class="hot-chip" id="btnBack">← 返回 20 位主骑</button>
          </div>` + renderRiderPool({
            key: state.rider,
            cn: state.matched[0].riderCn,
            series: state.matched[0].series,
            year: state.matched[0].year,
            models: state.matched
          });
        $('#btnBack').addEventListener('click', () => {
          state.rider = null;
          state.keyword = '';
          $('#kw').value = '';
          render();
          window.scrollTo({ top: 240, behavior: 'smooth' });
        });
        bindDynamic();
        return;
      }

      // 跨主骑 —— 按主骑聚合
      out.innerHTML = renderRiders(state.matched,
        '命中 ' + set.size + ' 位主骑 · ' + state.matched.length + ' 个版本',
        '点骑士看具体版本');
      bindDynamic();
      return;
    }

    // 6) 没命中。若是被系列筛选挡掉，说清原因
    if (state.allMatched.length) {
      out.innerHTML = `
        <div class="empty" style="margin-top:26px">
          <b>「${esc(state.keyword)}」不在「${esc(state.line)}」线里</b>
          它命中的是：${state.allMatched.map(m => esc(m.riderCn) + ' ' + esc(m.ver) + '（' + esc(m.line) + '）').join('、')}<br>
          把上面的系列切回「全部」就能看到。
        </div>`;
      return;
    }

    out.innerHTML = renderEmpty();
    bindDynamic();
  }

  function bindDynamic() {
    $$('#out [data-open]').forEach(el => el.addEventListener('click', () => {
      state.activeKey = el.dataset.open;
      render();
      window.scrollTo({ top: 240, behavior: 'smooth' });
    }));
    $$('#out [data-rider]').forEach(el => el.addEventListener('click', () => {
      state.rider = el.dataset.rider;
      render();
      window.scrollTo({ top: 240, behavior: 'smooth' });
    }));
    $$('#out [data-hot]').forEach(el => el.addEventListener('click', () => {
      $('#kw').value = el.dataset.hot;
      doSearch(el.dataset.hot);
    }));
  }

  /* ---------------- 搜索 ---------------- */
  function doSearch(kw) {
    state.keyword = String(kw || '').trim();
    state.activeKey = null;
    state.rider = null;
    recompute();
    render();
    if (state.keyword) {
      const y = $('#out').getBoundingClientRect().top + window.scrollY - 20;
      window.scrollTo({ top: y, behavior: 'smooth' });
    }
  }

  /* ---------------- 绑定 ---------------- */
  function bind() {
    $('#btnSearch').addEventListener('click', () => doSearch($('#kw').value));
    $('#kw').addEventListener('keydown', e => {
      if (e.key === 'Enter') doSearch($('#kw').value);
    });

    $$('.hot-chip[data-hot]').forEach(el => el.addEventListener('click', () => {
      $('#kw').value = el.dataset.hot;
      doSearch(el.dataset.hot);
    }));

    // 系列
    $$('.chip[data-line]').forEach(c => c.addEventListener('click', () => {
      state.line = c.dataset.line;
      $$('.chip[data-line]').forEach(x => x.classList.toggle('on', x === c));
      applyLineFilter();
    }));

    // 平台
    $$('.chip[data-pf]').forEach(c => c.addEventListener('click', () => {
      const pf = c.dataset.pf;
      if (state.platforms.has(pf) && state.platforms.size === 1) return;
      if (state.platforms.has(pf)) { state.platforms.delete(pf); c.classList.remove('on'); }
      else { state.platforms.add(pf); c.classList.add('on'); }
      render();
    }));

    // 成色
    $$('.chip[data-cond]').forEach(c => c.addEventListener('click', () => {
      state.cond = c.dataset.cond;
      $$('.chip[data-cond]').forEach(x => x.classList.toggle('on', x === c));
      render();
    }));
  }

  // 系列筛选同时约束搜索命中结果与候选条目
  function recompute() {
    const all = matchModels(state.keyword);
    state.allMatched = all;
    state.matched = state.line === 'ALL' ? all : all.filter(m => m.line === state.line);
  }

  function applyLineFilter() {
    state.activeKey = null;
    state.rider = null;
    recompute();
    render();
  }

  // 页脚数据口径：有真实抓取数据时改成动态描述，避免页面写着「离线」却显示实时价
  function fillLiveNote() {
    const el = document.getElementById('liveNote');
    const stat = document.getElementById('statQuotes');
    const meta = (typeof LIVE_META !== 'undefined') ? LIVE_META : null;

    if (stat) {
      stat.innerHTML = meta && meta.count
        ? '<b>' + meta.count + '</b>条实时 · <b>' + (ITEMS.length - meta.count) + '</b>条参考'
        : '<b>' + ITEMS.length + '</b>条三平台报价';
    }
    if (!el) return;
    if (meta && meta.count) {
      el.innerHTML =
        '其中 <b>' + meta.models + ' 个型号 / ' + meta.count + ' 条</b>为' +
        (meta.platforms && meta.platforms.length
          ? meta.platforms.map(p => PLATFORM_CN[p] || p).join('、') : '平台') +
        '实时在售（抓取于 ' + esc(meta.fetchedAt) + '，点开即真实商品页），标「实时在售」；' +
        '其余型号暂无整只在售，标「参考价」，为按行情推算的样本。';
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    fillLiveNote();
    bind();
    render();          // 首屏直接铺出 20 位主骑，不用先搜一次才看到东西
  });
})();

/* =====================================================================
   可选账号：注册 / 登录 / 退出（演示用，不阻塞查价）
     · 账号只存当前浏览器 localStorage，不上传、不跨设备同步
     · 口令以 SHA-256(随机盐 + 口令) 摘要保存，不存明文；仍是演示级实现
     · 未登录可完整使用查价；登录后不追加虚构的订阅数据
   ===================================================================== */
(function () {
  'use strict';

  const K_USERS = 'shf_demo_users_v1';
  const K_SESSION = 'shf_demo_session_v1';
  const $ = s => document.querySelector(s);

  function readUsers() {
    try { return JSON.parse(localStorage.getItem(K_USERS) || '{}') || {}; }
    catch (e) { return {}; }
  }
  const writeUsers = u => localStorage.setItem(K_USERS, JSON.stringify(u));
  const session = () => localStorage.getItem(K_SESSION) || '';
  const setSession = n => n
    ? localStorage.setItem(K_SESSION, n)
    : localStorage.removeItem(K_SESSION);

  async function digest(text, salt) {
    const data = new TextEncoder().encode(salt + '|' + text);
    if (window.crypto && window.crypto.subtle) {
      const buf = await window.crypto.subtle.digest('SHA-256', data);
      return Array.from(new Uint8Array(buf))
        .map(b => b.toString(16).padStart(2, '0')).join('');
    }
    // 旧浏览器退化路径：仍不保存明文口令
    let h = 2166136261;
    for (let i = 0; i < data.length; i++) { h ^= data[i]; h = Math.imul(h, 16777619); }
    return 'fnv:' + (h >>> 0).toString(16);
  }
  const newSalt = () => Math.random().toString(36).slice(2) + Date.now().toString(36);

  let tab = 'login';

  function msg(text, ok) {
    ['#acctMsg', '#acctMsg2'].forEach(sel => {
      const e = $(sel);
      if (!e) return;
      e.textContent = text || '';
      e.className = 'acct-msg' + (text ? (ok ? ' ok' : ' bad') : '');
    });
  }

  function syncUI() {
    const who = session();
    const btn = $('#acctBtn');
    btn.textContent = who ? '你好，' + who : '登录 / 注册';
    btn.classList.toggle('signed', !!who);
    $('#acctLogged').hidden = !who;
    $('#acctForm').hidden = !!who;
    $('#acctTabs').hidden = !!who;
    if (who) $('#acctWho').textContent = who;
  }

  function switchTab(t) {
    tab = t;
    document.querySelectorAll('#acctTabs .tab').forEach(b =>
      b.classList.toggle('on', b.dataset.tab === t));
    $('#acctPwd2Row').hidden = t !== 'register';
    $('#acctSubmit').textContent = t === 'register' ? '注册并登录' : '登录';
    $('#acctForm').reset();
    msg('');
  }

  async function submit(e) {
    e.preventDefault();
    const u = ($('#acctUser').value || '').trim();
    const p = $('#acctPwd').value || '';
    if (!/^[\w\u4e00-\u9fa5]{2,20}$/.test(u)) return msg('用户名须为 2–20 位中英文或数字');
    if (p.length < 6) return msg('密码至少 6 位');

    const users = readUsers();
    if (tab === 'register') {
      if (users[u]) return msg('该用户名已注册，请直接登录');
      if (($('#acctPwd2').value || '') !== p) return msg('两次输入的密码不一致');
      const s = newSalt();
      users[u] = { salt: s, hash: await digest(p, s) };
      writeUsers(users);
      setSession(u);
      msg('注册成功，已登录', true);
      syncUI();
      return;
    }
    if (!users[u]) return msg('该用户名未注册，请先切换到「注册」');
    if ((await digest(p, users[u].salt)) !== users[u].hash) return msg('密码不正确');
    setSession(u);
    msg('登录成功', true);
    syncUI();
  }

  document.addEventListener('DOMContentLoaded', () => {
    const modal = $('#acctModal');
    $('#acctBtn').addEventListener('click', () => { modal.hidden = false; syncUI(); msg(''); });
    $('#acctClose').addEventListener('click', () => { modal.hidden = true; });
    modal.addEventListener('click', e => { if (e.target === modal) modal.hidden = true; });
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') modal.hidden = true;
    });
    $('#acctTabs').addEventListener('click', e => {
      const b = e.target.closest('.tab');
      if (b) switchTab(b.dataset.tab);
    });
    $('#acctForm').addEventListener('submit', submit);
    $('#acctLogout').addEventListener('click', () => {
      setSession(''); syncUI(); msg('已退出登录', true);
    });
    switchTab('login');
    syncUI();
  });
})();
