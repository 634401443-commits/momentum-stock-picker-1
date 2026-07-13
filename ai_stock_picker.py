#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
量化动量选股系统 v4.0
- 全新金融仪表盘 UI 设计
- tkinter 进度窗口 (解决 console=False 无反馈问题)
- 桌面端响应式布局 + 雷达图 + 迷你 K 线
- 中国 A 股配色惯例 (红涨绿跌)
腾讯自选股数据源
"""
import os, sys, time, math, webbrowser, threading, json
from datetime import datetime, timedelta

# ═══ 自选池 ═════════════════════════════════════════
STOCKS = [
    ("600519", "贵州茅台"), ("000858", "五粮液"),
    ("300750", "宁德时代"), ("601318", "中国平安"),
    ("000333", "美的集团"), ("002594", "比亚迪"),
    ("300059", "东方财富"), ("600900", "长江电力"),
    ("688981", "中芯国际"), ("000001", "平安银行"),
]

ETFS = [
    ("510050", "上证50ETF"), ("510300", "沪深300ETF"),
    ("510500", "中证500ETF"), ("588000", "科创50ETF"),
    ("159915", "创业板ETF"), ("159949", "创业板50ETF"),
    ("512880", "证券ETF"), ("512660", "军工ETF"),
    ("159865", "养殖ETF"), ("513100", "纳指ETF"),
]

if getattr(sys, 'frozen', False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))
def _get_ip():
    """获取本机局域网IP"""
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

OUTPUT_DIR = os.path.join(_BASE_DIR, "reports")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ═══ 数据获取 ═════════════════════════════════════════

def fetch_kline(code, days=200):
    import requests as req
    prefix = "sh" if code[0] in "56" else "sz"
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={prefix}{code},day,,,{days},qfq"
    try:
        r = req.get(url, timeout=10, headers={"User-Agent":"Mozilla/5.0"})
        if r.status_code == 200:
            d = r.json().get("data",{}).get(f"{prefix}{code}",{})
            kl = d.get("qfqday") or d.get("day",[])
            if kl and len(kl)>5:
                return parse_kline(kl)
    except: pass
    return None

def parse_kline(kl):
    r = {"dates":[],"opens":[],"highs":[],"lows":[],"closes":[],"volumes":[]}
    for line in kl:
        r["dates"].append(line[0])
        r["opens"].append(float(line[1]))
        r["closes"].append(float(line[2]))
        r["highs"].append(float(line[3]))
        r["lows"].append(float(line[4]))
        r["volumes"].append(float(line[5]))
    return r

# ═══ 指标 ════════════════════════════════════════════

def sma(arr,n):
    r=[]; [r.append(None if i<n-1 else sum(arr[i-n+1:i+1])/n) for i in range(len(arr))]; return r
def ema(arr,n):
    k=2/(n+1); r=[]; [r.append(arr[i] if i==0 else arr[i]*k+r[-1]*(1-k)) for i in range(len(arr))]; return r
def rsi(c,n=14):
    if len(c)<n+1: return [50]*len(c)
    g,lv=[],[]
    for i in range(1,len(c)): d=c[i]-c[i-1]; g.append(max(d,0)); lv.append(max(-d,0))
    r=[50]*n; ag,al=sum(g[:n])/n,sum(lv[:n])/n
    for i in range(n,len(g)): ag=(ag*(n-1)+g[i])/n; al=(al*(n-1)+lv[i])/n; r.append(100-100/(1+ag/al if al>0 else 999))
    return r
def macd(c):
    e12,e26=ema(c,12),ema(c,26); dif=[e12[i]-e26[i] for i in range(len(c))]
    dea=ema(dif,9); bar=[2*(dif[i]-dea[i]) for i in range(len(c))]; return dif,dea,bar

# ═══ 动量打分 ═══════════════════════════════════════

def calc_score(kline):
    c=h=l=v=[]; c=kline["closes"]; h=kline["highs"]; l=kline["lows"]; v=kline["volumes"]; n=len(c)
    if n<50: return None
    price=c[-1]; chg=(c[-1]-c[-2])/c[-2]*100

    # 1.价格动量30分
    pm=0; r15=(c[-1]-c[-16])/c[-16]*100 if n>=16 else 0
    r45=(c[-1]-c[-46])/c[-46]*100 if n>=46 else 0
    r150=(c[-1]-c[-151])/c[-151]*100 if n>=151 else r45
    pm+=10 if r15>5 else 7 if r15>2 else 4 if r15>0 else 2 if r15>-3 else 0
    pm+=10 if r45>15 else 7 if r45>8 else 4 if r45>0 else 2 if r45>-8 else 0
    pm+=10 if r150>25 else 7 if r150>10 else 4 if r150>0 else 2 if r150>-15 else 0

    # 2.成交量20分
    vol=0; vma5=sum(v[-5:])/5; vma20=sum(v[-20:])/20 if n>=20 else vma5; vr=vma5/vma20 if vma20>0 else 1
    vol+=10 if vr>1.5 else 7 if vr>1.2 else 5 if vr>0.8 else 3 if vr>0.5 else 1
    uv,dv,uc,dc=0,0,0,0
    for i in range(-10,0):
        if c[i]>c[i-1]: uv+=v[i]; uc+=1
        else: dv+=v[i]; dc+=1
    auv=uv/uc if uc>0 else 0; adv=dv/dc if dc>0 else 1
    vol+=10 if auv>adv*1.2 else 6 if auv>adv else 3

    # 3.趋势结构25分
    tr=0; m5=sma(c,5); m10=sma(c,10); m20=sma(c,20); m60=sma(c,60)
    m5v=m5[-1]or 0; m10v=m10[-1]or 0; m20v=m20[-1]or 0; m60v=m60[-1]or 0
    if m5v>m10v>m20v>m60v: tr+=10
    elif m5v>m10v>m20v: tr+=7
    elif m5v>m10v: tr+=4
    tr+=5 if price>m20v and price>m60v else 3 if price>m20v else 2 if price>m60v else 0
    dif,dea,bar=macd(c)
    if dif[-1]>dea[-1] and bar[-1]>0: tr+=10 if len(bar)>=2 and bar[-1]>bar[-2] else 7
    elif dif[-1]>dea[-1]: tr+=5
    elif bar[-1]>0: tr+=3
    ms="多头排列" if m5v>m10v>m20v else "空头排列" if m5v<m10v<m20v else "均线粘合"

    # 4.相对强度15分
    rs=0; r20=(c[-1]-c[-21])/c[-21]*100 if n>=21 else r15
    rs+=8 if r20>0 and r15>0 else 5 if r20>0 else 3 if r20>-5 else 1
    rsi_v=rsi(c)[-1]
    rs+=7 if 40<=rsi_v<=60 else 5 if 30<=rsi_v<=70 else 3 if rsi_v>70 else 1

    # 5.风险控制10分
    risk=0; peak=max(c[-20:]) if n>=20 else c[-1]; dd=(peak-c[-1])/peak*100
    risk+=5 if dd<5 else 4 if dd<10 else 2 if dd<15 else 1 if dd<20 else 0

    total=pm+vol+tr+rs+risk
    if total>=80 and r15>0: signal="强烈买入"
    elif total>=70: signal="买入"
    elif total>=60: signal="持有"
    elif total>=50: signal="观望"
    elif total>=30: signal="注意风险"
    else: signal="回避"

    support=round(min(c[-5:]) if n>=5 else c[-1],2)
    pressure=round(max(c[-5:]) if n>=5 else c[-1],2)

    # 提取最近30日收盘价用于迷你走势图
    spark_closes = c[-30:] if n>=30 else c[:]

    return {
        "total":total,"price":price,"change":chg,"signal":signal,
        "support":support,"pressure":pressure,
        "r15":round(r15,1),"r45":round(r45,1),
        "ma_status":ms,"vol_ratio":round(vr,2),
        "rsi":round(rsi_v,1),"dd":round(dd,1),
        "detail":(pm,vol,tr,rs,risk),
        "spark":spark_closes,
    }

# ═══ 生成推文 ═════════════════════════════════════════

def gen_tweet(stock_res, etf_res, label):
    lines=[f"量化动量选股 {label} 收盘扫描"]
    lines.append(f"股票{len(stock_res)}只 + ETF{len(etf_res)}只\n")

    top_s=stock_res[:3]
    lines.append("【股票 Top 3】")
    for i,r in enumerate(top_s,1):
        lines.append(f" {i}. {r['name']}({r['code']}) {r['total']}分 {r['signal']}  现价{r['price']:.2f}")

    if etf_res:
        top_e=etf_res[:3]
        lines.append("\n【ETF Top 3】")
        for i,r in enumerate(top_e,1):
            lines.append(f" {i}. {r['name']}({r['code']}) {r['total']}分 {r['signal']}  现价{r['price']:.2f}")

    buy=[r for r in stock_res if "买入" in r["signal"]]
    sell=[r for r in stock_res if "回避" in r["signal"] or "注意风险" in r["signal"]]
    if buy: lines.append(f"\n买入信号 {len(buy)}只")
    if sell: lines.append(f"风险预警 {len(sell)}只")

    avg_s=sum(r["total"] for r in stock_res)/len(stock_res) if stock_res else 0
    avg_e=sum(r["total"] for r in etf_res)/len(etf_res) if etf_res else 0
    avg_all=(avg_s+avg_e)/2
    if avg_all>=65: lines.append("\n市场偏强 可适当加仓")
    elif avg_all>=50: lines.append("\n市场中性 精选个股为主")
    else: lines.append("\n市场偏弱 控制仓位注意风险")

    lines.append("\n量化模型仅供参考 不构成投资建议")
    return "\n".join(lines)

# ═══ SVG 工具函数 ═════════════════════════════════════

def gen_sparkline(closes, width=120, height=36):
    """生成迷你走势图 SVG"""
    if not closes or len(closes) < 2:
        return ""
    mn, mx = min(closes), max(closes)
    rng = mx - mn if mx > mn else 1
    n = len(closes)
    pts = []
    for i, val in enumerate(closes):
        x = (i / (n - 1)) * width
        y = height - ((val - mn) / rng) * height
        pts.append(f"{x:.1f},{y:.1f}")
    poly_str = " ".join(pts)
    # 判断涨跌: 中国惯例 红涨绿跌
    is_up = closes[-1] >= closes[0]
    color = "#e53935" if is_up else "#00c853"
    fill_color = "#e5393533" if is_up else "#00c85333"
    # 填充区域路径
    area_str = f"0,{height} " + poly_str + f" {width},{height}"
    return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" style="display:block">
  <polygon points="{area_str}" fill="{fill_color}"/>
  <polyline points="{poly_str}" fill="none" stroke="{color}" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>
  <circle cx="{width:.1f}" cy="{height - ((closes[-1]-mn)/rng)*height:.1f}" r="2.5" fill="{color}"/>
</svg>"""

def gen_radar(detail, size=100):
    """生成五维雷达图 SVG"""
    labels = ["价格", "量能", "趋势", "强度", "风险"]
    max_vals = [30, 20, 25, 15, 10]
    vals = list(detail)
    cx, cy = size/2, size/2
    r = size/2 - 16
    n = 5
    angles = [-90 + i * 360/n for i in range(n)]

    # 背景多边形 (3层)
    bg_polys = ""
    for layer in [0.33, 0.66, 1.0]:
        pts = []
        for a in angles:
            rad = math.radians(a)
            x = cx + r * layer * math.cos(rad)
            y = cy + r * layer * math.sin(rad)
            pts.append(f"{x:.1f},{y:.1f}")
        bg_polys += f'<polygon points="{" ".join(pts)}" fill="none" stroke="#2a3548" stroke-width="0.5"/>'

    # 轴线
    axis_lines = ""
    for a in angles:
        rad = math.radians(a)
        x = cx + r * math.cos(rad)
        y = cy + r * math.sin(rad)
        axis_lines += f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{x:.1f}" y2="{y:.1f}" stroke="#2a3548" stroke-width="0.5"/>'

    # 数据多边形
    data_pts = []
    for i, (a, v, mv) in enumerate(zip(angles, vals, max_vals)):
        rad = math.radians(a)
        ratio = v / mv if mv > 0 else 0
        x = cx + r * ratio * math.cos(rad)
        y = cy + r * ratio * math.sin(rad)
        data_pts.append(f"{x:.1f},{y:.1f}")
    data_poly = " ".join(data_pts)

    # 标签
    label_strs = ""
    for i, (a, lb) in enumerate(zip(angles, labels)):
        rad = math.radians(a)
        lx = cx + (r + 8) * math.cos(rad)
        ly = cy + (r + 8) * math.sin(rad)
        label_strs += f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" dominant-baseline="middle" fill="#6b7689" font-size="8">{lb}</text>'

    return f"""<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" style="display:block">
  {bg_polys}
  {axis_lines}
  <polygon points="{data_poly}" fill="#2962ff33" stroke="#2962ff" stroke-width="1.5"/>
  {"".join(f'<circle cx="{p.split(",")[0]}" cy="{p.split(",")[1]}" r="1.5" fill="#2962ff"/>' for p in data_pts)}
  {label_strs}
</svg>"""

def gen_score_ring(score, size=56):
    """生成得分圆环 SVG"""
    # 中国惯例: 高分(强势)=红色, 低分(弱势)=绿色
    if score >= 70:
        color = "#e53935"
    elif score >= 50:
        color = "#ffb74d"
    else:
        color = "#00c853"
    cx, cy = size/2, size/2
    r = size/2 - 4
    circumference = 2 * math.pi * r
    # 满分100
    ratio = score / 100
    dash = ratio * circumference
    return f"""<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#1e2434" stroke-width="4"/>
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="4"
    stroke-dasharray="{dash:.1f} {circumference:.1f}" stroke-linecap="round"
    transform="rotate(-90 {cx} {cy})"/>
  <text x="{cx}" y="{cy-1}" text-anchor="middle" dominant-baseline="middle" fill="{color}" font-size="18" font-weight="700" font-family="monospace">{score}</text>
</svg>"""

# ═══ HTML 报告 (手机小程序版) ═══════════════════════

def gen_html(stock_res, etf_res, label):
    now_str = datetime.now().strftime("%H:%M:%S")

    def card(r, idx):
        pm,vol,tr,rs,risk = r["detail"]
        t = r["total"]
        s = r["signal"]
        # 中国惯例: 红涨绿跌
        cc = "#e53935" if r["change"] >= 0 else "#00c853"
        cs = "+" if r["change"] >= 0 else ""

        # 信号样式
        if "买入" in s:
            sig_bg = "rgba(229,57,53,0.15)"; sig_color = "#e53935"; sig_border = "rgba(229,57,53,0.4)"
        elif "持有" in s or "观望" in s:
            sig_bg = "rgba(255,183,77,0.15)"; sig_color = "#ffb74d"; sig_border = "rgba(255,183,77,0.4)"
        else:
            sig_bg = "rgba(0,200,83,0.15)"; sig_color = "#00c853"; sig_border = "rgba(0,200,83,0.4)"

        # 各维度进度条
        dims = [
            ("价格动量", pm, 30, "#5c6bc0"),
            ("成交量",   vol, 20, "#26a69a"),
            ("趋势结构", tr,  25, "#e53935"),
            ("相对强度", rs,  15, "#ab47bc"),
            ("风险控制", risk,10, "#ff7043"),
        ]
        bars = "".join(
            f'<div class="dim-bar">'
            f'<span class="dim-label">{lb}</span>'
            f'<div class="dim-track">'
            f'<div class="dim-fill" style="width:{v/mv*100:.0f}%;background:{cl}"></div>'
            f'</div>'
            f'<span class="dim-val">{v}/{mv}</span>'
            f'</div>'
            for lb, v, mv, cl in dims
        )

        # 迷你走势图
        spark_svg = gen_sparkline(r.get("spark", []), 130, 38)

        # 雷达图
        radar_svg = gen_radar(r["detail"], 88)

        # 得分圆环
        ring_svg = gen_score_ring(t, 52)

        # 涨跌幅样式
        r15_color = "#e53935" if r["r15"] > 0 else "#00c853"
        r45_color = "#e53935" if r["r45"] > 0 else "#00c853"

        return f"""
<div class="stock-card" style="animation-delay:{idx*0.06}s">
  <div class="card-left">
    {ring_svg}
  </div>
  <div class="card-main">
    <div class="card-header">
      <div class="stock-info">
        <span class="stock-code">{r['code']}</span>
        <span class="stock-name">{r['name']}</span>
      </div>
      <span class="signal-badge" style="background:{sig_bg};color:{sig_color};border-color:{sig_border}">{s}</span>
    </div>
    <div class="price-row">
      <span class="price-main">{r['price']:.2f}</span>
      <span class="price-change" style="color:{cc}">{cs}{r['change']:.2f}%</span>
      <span class="tag-chip">{r['ma_status']}</span>
      <span class="tag-chip">量比 {r['vol_ratio']}</span>
      <span class="tag-chip">RSI {r['rsi']}</span>
    </div>
    <div class="card-body">
      <div class="bars-section">{bars}</div>
      <div class="chart-section">
        <div class="radar-wrap">{radar_svg}</div>
        <div class="spark-wrap">{spark_svg}</div>
      </div>
    </div>
    <div class="key-metrics">
      <div class="metric"><span class="metric-label">15日</span><span class="metric-value" style="color:{r15_color}">{r['r15']:+.1f}%</span></div>
      <div class="metric"><span class="metric-label">45日</span><span class="metric-value" style="color:{r45_color}">{r['r45']:+.1f}%</span></div>
      <div class="metric"><span class="metric-label">支撑</span><span class="metric-value">{r['support']}</span></div>
      <div class="metric"><span class="metric-label">压力</span><span class="metric-value">{r['pressure']}</span></div>
      <div class="metric"><span class="metric-label">回撤</span><span class="metric-value" style="color:{'#00c853' if r['dd']>10 else '#ffb74d' if r['dd']>5 else '#e53935'}">-{r['dd']:.1f}%</span></div>
    </div>
  </div>
</div>"""

    stock_cards = "".join(card(r, i) for i, r in enumerate(stock_res))
    etf_cards = "".join(card(r, i) for i, r in enumerate(etf_res))

    # 统计
    b_s=sum(1 for r in stock_res if "买入" in r["signal"])
    h_s=sum(1 for r in stock_res if "持有" in r["signal"] or "观望" in r["signal"])
    s_s=sum(1 for r in stock_res if "回避" in r["signal"] or "注意风险" in r["signal"])
    b_e=sum(1 for r in etf_res if "买入" in r["signal"])
    h_e=sum(1 for r in etf_res if "持有" in r["signal"] or "观望" in r["signal"])
    s_e=sum(1 for r in etf_res if "回避" in r["signal"] or "注意风险" in r["signal"])

    avg_s = sum(r["total"] for r in stock_res)/len(stock_res) if stock_res else 0
    avg_e = sum(r["total"] for r in etf_res)/len(etf_res) if etf_res else 0
    avg_all = (avg_s + avg_e) / 2 if (stock_res or etf_res) else 0

    # 市场温度计
    if avg_all >= 65:
        market_text = "市场偏强"; market_color = "#e53935"; market_desc = "可适当加仓"
    elif avg_all >= 50:
        market_text = "市场中性"; market_color = "#ffb74d"; market_desc = "精选个股为主"
    else:
        market_text = "市场偏弱"; market_color = "#00c853"; market_desc = "控制仓位注意风险"

    # Top 1 股票
    top1 = stock_res[0] if stock_res else None
    top1_html = ""
    if top1:
        top1_html = f"""
<div class="top-pick">
  <div class="top-pick-badge">TOP 1</div>
  <div class="top-pick-info">
    <span class="top-pick-name">{top1['name']}</span>
    <span class="top-pick-code">{top1['code']}</span>
  </div>
  <div class="top-pick-score" style="color:{'#e53935' if top1['total']>=70 else '#ffb74d'}">{top1['total']}</div>
  <div class="top-pick-signal">{top1['signal']}</div>
  <div class="top-pick-price">{top1['price']:.2f}</div>
</div>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>量化动量选股系统 {label}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
:root {{
  --bg: #0a0e17;
  --bg-card: #131722;
  --bg-card-hover: #182033;
  --border: #1e2434;
  --border-hover: #2a3548;
  --text: #dee5f0;
  --text-2: #8b95a8;
  --text-3: #4a5568;
  --accent: #2962ff;
  --red: #e53935;
  --green: #00c853;
  --amber: #ffb74d;
  --radius: 14px;
}}
body {{
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, 'PingFang SC', 'Microsoft YaHei', 'Segoe UI', sans-serif;
  font-size: 14px;
  line-height: 1.5;
  min-height: 100vh;
}}
.container {{ max-width: 1280px; margin: 0 auto; padding: 20px; }}

/* ===== Header ===== */
.header {{
  background: linear-gradient(135deg, #131722 0%, #0d1521 100%);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 28px 32px;
  margin-bottom: 20px;
  position: relative;
  overflow: hidden;
}}
.header::before {{
  content: '';
  position: absolute;
  top: -50%; right: -10%;
  width: 400px; height: 400px;
  background: radial-gradient(circle, rgba(41,98,255,0.08) 0%, transparent 70%);
  pointer-events: none;
}}
.header-top {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
  position: relative;
}}
.header-title {{
  display: flex; align-items: center; gap: 14px;
}}
.header-logo {{
  width: 44px; height: 44px;
  background: linear-gradient(135deg, #2962ff, #6200ea);
  border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  font-size: 22px; font-weight: 800; color: #fff;
}}
.header h1 {{
  font-size: 24px; font-weight: 700; color: var(--text);
}}
.header .subtitle {{
  color: var(--text-2); font-size: 13px; margin-top: 2px;
}}
.header-meta {{
  display: flex; gap: 12px; align-items: center; flex-wrap: wrap;
}}
.meta-chip {{
  background: rgba(41,98,255,0.1);
  color: var(--accent);
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  border: 1px solid rgba(41,98,255,0.2);
}}
.meta-time {{ color: var(--text-2); font-size: 12px; }}

/* ===== Dashboard ===== */
.dashboard {{
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 1fr;
  gap: 14px;
  margin-bottom: 20px;
}}
.dash-card {{
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 18px 20px;
  transition: border-color 0.2s;
}}
.dash-card:hover {{ border-color: var(--border-hover); }}
.dash-card .dash-label {{
  font-size: 11px; color: var(--text-2); text-transform: uppercase;
  letter-spacing: 1px; margin-bottom: 8px;
}}
.dash-card .dash-value {{
  font-size: 28px; font-weight: 700; font-family: 'SF Mono', 'Consolas', monospace;
}}
.dash-card .dash-sub {{ font-size: 12px; color: var(--text-2); margin-top: 4px; }}

/* 市场温度计 */
.temp-bar {{
  height: 6px; border-radius: 3px;
  background: linear-gradient(90deg, var(--green) 0%, var(--amber) 50%, var(--red) 100%);
  margin-top: 10px;
  position: relative;
}}
.temp-pointer {{
  position: absolute;
  top: -3px;
  width: 4px; height: 12px;
  background: #fff;
  border-radius: 2px;
  box-shadow: 0 0 6px rgba(255,255,255,0.5);
  transition: left 0.6s ease;
}}

/* ===== Top Pick ===== */
.top-pick {{
  display: flex; align-items: center; gap: 14px;
  background: linear-gradient(135deg, rgba(229,57,53,0.08), rgba(229,57,53,0.02));
  border: 1px solid rgba(229,57,53,0.2);
  border-radius: var(--radius);
  padding: 16px 20px;
  margin-bottom: 20px;
}}
.top-pick-badge {{
  background: linear-gradient(135deg, #e53935, #ff6f00);
  color: #fff;
  padding: 4px 12px;
  border-radius: 8px;
  font-size: 12px; font-weight: 700;
  letter-spacing: 1px;
}}
.top-pick-info {{ display: flex; flex-direction: column; }}
.top-pick-name {{ font-size: 18px; font-weight: 700; }}
.top-pick-code {{ font-size: 12px; color: var(--text-2); font-family: monospace; }}
.top-pick-score {{
  font-size: 32px; font-weight: 800; font-family: monospace;
  margin-left: auto;
}}
.top-pick-signal {{
  background: rgba(229,57,53,0.15); color: var(--red);
  padding: 4px 12px; border-radius: 8px;
  font-size: 13px; font-weight: 600;
}}
.top-pick-price {{ font-size: 16px; color: var(--text-2); font-family: monospace; }}

/* ===== Section ===== */
.section {{
  margin-bottom: 24px;
}}
.section-header {{
  display: flex; align-items: center; gap: 10px;
  margin-bottom: 14px;
}}
.section-header h2 {{
  font-size: 18px; font-weight: 700;
}}
.section-line {{
  flex: 1; height: 1px;
  background: linear-gradient(90deg, var(--border), transparent);
}}
.section-stats {{
  display: flex; gap: 8px;
}}
.section-stat {{
  display: flex; align-items: center; gap: 4px;
  padding: 4px 10px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
}}
.section-stat.buy {{ background: rgba(229,57,53,0.1); color: var(--red); }}
.section-stat.hold {{ background: rgba(255,183,77,0.1); color: var(--amber); }}
.section-stat.sell {{ background: rgba(0,200,83,0.1); color: var(--green); }}

/* ===== Stock Cards Grid ===== */
.cards-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(560px, 1fr));
  gap: 14px;
}}
.stock-card {{
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 18px;
  display: flex;
  gap: 16px;
  transition: all 0.25s;
  opacity: 0;
  animation: cardIn 0.5s ease forwards;
}}
.stock-card:hover {{
  border-color: var(--border-hover);
  background: var(--bg-card-hover);
  transform: translateY(-1px);
  box-shadow: 0 4px 20px rgba(0,0,0,0.3);
}}
@keyframes cardIn {{
  from {{ opacity: 0; transform: translateY(12px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}

.card-left {{
  flex-shrink: 0;
  display: flex; align-items: flex-start;
  padding-top: 2px;
}}
.card-main {{
  flex: 1; min-width: 0;
}}
.card-header {{
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 8px;
}}
.stock-info {{ display: flex; align-items: center; gap: 8px; }}
.stock-code {{
  color: var(--text-2); font-size: 12px;
  font-family: 'SF Mono', 'Consolas', monospace;
  background: rgba(255,255,255,0.05);
  padding: 2px 6px; border-radius: 4px;
}}
.stock-name {{
  font-size: 16px; font-weight: 700; color: var(--text);
}}
.signal-badge {{
  font-size: 12px; padding: 4px 12px;
  border-radius: 8px; font-weight: 600;
  border: 1px solid;
  white-space: nowrap;
}}
.price-row {{
  display: flex; align-items: center; gap: 10px;
  margin-bottom: 14px; flex-wrap: wrap;
}}
.price-main {{
  font-size: 24px; font-weight: 700;
  font-family: 'SF Mono', 'Consolas', monospace;
  color: var(--text);
}}
.price-change {{
  font-size: 15px; font-weight: 700;
  font-family: 'SF Mono', 'Consolas', monospace;
}}
.tag-chip {{
  font-size: 11px; padding: 3px 8px;
  border-radius: 6px;
  background: rgba(255,255,255,0.04);
  color: var(--text-2);
  border: 1px solid rgba(255,255,255,0.06);
}}

.card-body {{
  display: flex; gap: 16px;
  margin-bottom: 12px;
}}
.bars-section {{
  flex: 1; min-width: 0;
}}
.dim-bar {{
  display: flex; align-items: center; gap: 8px;
  margin: 3px 0;
}}
.dim-label {{
  width: 56px; flex-shrink: 0;
  font-size: 11px; color: var(--text-2);
}}
.dim-track {{
  flex: 1; height: 8px;
  background: rgba(255,255,255,0.04);
  border-radius: 4px; overflow: hidden;
}}
.dim-fill {{
  height: 100%; border-radius: 4px;
  transition: width 0.6s ease;
  min-width: 2px;
}}
.dim-val {{
  width: 42px; flex-shrink: 0;
  font-size: 11px; color: var(--text-2);
  text-align: right;
  font-family: 'SF Mono', 'Consolas', monospace;
}}

.chart-section {{
  display: flex; flex-direction: column;
  align-items: center; gap: 4px;
  flex-shrink: 0;
}}
.radar-wrap {{ }}
.spark-wrap {{ }}

.key-metrics {{
  display: flex; gap: 6px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
}}
.metric {{
  flex: 1; text-align: center;
  padding: 4px 0;
}}
.metric-label {{
  display: block; font-size: 10px;
  color: var(--text-2); margin-bottom: 2px;
}}
.metric-value {{
  font-size: 13px; font-weight: 700;
  font-family: 'SF Mono', 'Consolas', monospace;
  color: var(--text);
}}

/* ===== Tweet Box ===== */
.tweet-box {{
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  margin-top: 20px;
}}
.tweet-title {{
  font-size: 14px; font-weight: 700;
  color: var(--accent);
  margin-bottom: 10px;
  display: flex; align-items: center; gap: 6px;
}}
.tweet-content {{
  font-size: 13px; line-height: 1.8;
  color: var(--text-2);
  white-space: pre-wrap;
  font-family: 'SF Mono', 'Consolas', monospace;
}}
.copy-btn {{
  margin-left: auto;
  background: rgba(41,98,255,0.1);
  color: var(--accent);
  border: 1px solid rgba(41,98,255,0.2);
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}}
.copy-btn:hover {{
  background: rgba(41,98,255,0.2);
}}

/* ===== Footer ===== */
.footer {{
  text-align: center;
  padding: 24px 20px;
  color: var(--text-3);
  font-size: 12px;
  border-top: 1px solid var(--border);
  margin-top: 24px;
}}

/* ===== Responsive ===== */
@media (max-width: 1200px) {{
  .dashboard {{ grid-template-columns: 1fr 1fr; }}
}}
@media (max-width: 640px) {{
  .container {{ padding: 12px; }}
  .cards-grid {{ grid-template-columns: 1fr; }}
  .stock-card {{ flex-direction: column; }}
  .card-left {{ display: none; }}
  .card-body {{ flex-direction: column; }}
  .dashboard {{ grid-template-columns: 1fr; }}
  .header h1 {{ font-size: 20px; }}
  .header {{ padding: 20px; }}
}}
</style>
</head>
<body>
<div class="container">

<!-- Header -->
<div class="header">
  <div class="header-top">
    <div class="header-title">
      <div class="header-logo">Q</div>
      <div>
        <h1>量化动量选股系统</h1>
        <div class="subtitle">五维动量打分模型 | 股票{len(stock_res)}只 + ETF{len(etf_res)}只</div>
      </div>
    </div>
    <div class="header-meta">
      <span class="meta-chip">{label}</span>
      <span class="meta-time">扫描时间 {now_str}</span>
    </div>
  </div>
</div>

<!-- Dashboard -->
<div class="dashboard">
  <div class="dash-card">
    <div class="dash-label">市场温度</div>
    <div class="dash-value" style="color:{market_color}">{market_text}</div>
    <div class="dash-sub">{market_desc} | 均分 {avg_all:.1f}</div>
    <div class="temp-bar">
      <div class="temp-pointer" style="left:{max(2, min(98, avg_all)):.0f}%"></div>
    </div>
  </div>
  <div class="dash-card">
    <div class="dash-label">买入信号</div>
    <div class="dash-value" style="color:var(--red)">{b_s + b_e}</div>
    <div class="dash-sub">股票 {b_s} | ETF {b_e}</div>
  </div>
  <div class="dash-card">
    <div class="dash-label">持有/观望</div>
    <div class="dash-value" style="color:var(--amber)">{h_s + h_e}</div>
    <div class="dash-sub">股票 {h_s} | ETF {h_e}</div>
  </div>
  <div class="dash-card">
    <div class="dash-label">注意/回避</div>
    <div class="dash-value" style="color:var(--green)">{s_s + s_e}</div>
    <div class="dash-sub">股票 {s_s} | ETF {s_e}</div>
  </div>
</div>

<!-- Top Pick -->
{top1_html}

<!-- Stocks Section -->
<div class="section">
  <div class="section-header">
    <h2>股票</h2>
    <div class="section-line"></div>
    <div class="section-stats">
      <span class="section-stat buy">买入 {b_s}</span>
      <span class="section-stat hold">持有 {h_s}</span>
      <span class="section-stat sell">回避 {s_s}</span>
    </div>
  </div>
  <div class="cards-grid">
    {stock_cards}
  </div>
</div>

<!-- ETF Section -->
<div class="section">
  <div class="section-header">
    <h2>ETF</h2>
    <div class="section-line"></div>
    <div class="section-stats">
      <span class="section-stat buy">买入 {b_e}</span>
      <span class="section-stat hold">持有 {h_e}</span>
      <span class="section-stat sell">回避 {s_e}</span>
    </div>
  </div>
  <div class="cards-grid">
    {etf_cards}
  </div>
</div>

<!-- Tweet Box -->
<div class="tweet-box">
  <div class="tweet-title">
    <span>推文摘要</span>
    <button class="copy-btn" onclick="copyTweet()">复制</button>
  </div>
  <div class="tweet-content" id="tweet-content">{gen_tweet(stock_res, etf_res, label)}</div>
</div>

<!-- Footer -->
<div class="footer">
  量化模型仅供参考 不构成投资建议<br>
  CTAAgents 动量选股体系 v4.0 | 数据源: 腾讯自选股 | {datetime.now().strftime("%Y-%m-%d %H:%M")}
</div>

</div>

<script>
function copyTweet() {{
  const text = document.getElementById('tweet-content').textContent;
  navigator.clipboard.writeText(text).then(() => {{
    const btn = document.querySelector('.copy-btn');
    const orig = btn.textContent;
    btn.textContent = '已复制';
    btn.style.background = 'rgba(0,200,83,0.15)';
    btn.style.color = '#00c853';
    setTimeout(() => {{
      btn.textContent = orig;
      btn.style.background = '';
      btn.style.color = '';
    }}, 2000);
  }});
}}

// 进度条动画
document.querySelectorAll('.dim-fill').forEach(el => {{
  const w = el.style.width;
  el.style.width = '0';
  setTimeout(() => {{ el.style.width = w; }}, 100);
}});
</script>
</body>
</html>"""
    return html

# ═══ 首页导航生成 ════════════════════════════════════

def gen_index_page(reports_dir):
    """生成网页版首页 - 报告列表导航"""
    import glob, json
    files = sorted(glob.glob(os.path.join(reports_dir, "动量选股_*.html")), reverse=True)
    # 排除 WPS 版
    files = [f for f in files if "_WPS" not in f]
    items = ""
    for fpath in files:
        base = os.path.basename(fpath)
        date_str = base.replace("动量选股_", "").replace(".html", "")
        date_display = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
        # 读取对应的推文作为预览
        tweet_path = os.path.join(reports_dir, f"推文_{date_str}.txt")
        preview = ""
        if os.path.exists(tweet_path):
            with open(tweet_path, "r", encoding="utf-8") as f:
                preview = f.read()[:150]
        items += f"""
<div class="report-item" onclick="window.location.href='{base}'">
    <div class="date">{date_display} 收盘报告</div>
    <div class="preview">{preview}</div>
</div>"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>量化动量选股系统</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box;font-family:-apple-system,'PingFang SC','Microsoft YaHei','Helvetica Neue',sans-serif}}
body{{background:#0a0e17;color:#dee5f0;padding:20px;max-width:640px;margin:0 auto;font-size:15px}}
.header{{text-align:center;padding:32px 20px;background:linear-gradient(135deg,#131722,#0d1521);border:1px solid #1e2434;border-radius:18px;margin-bottom:20px}}
.header h1{{color:#2962ff;font-size:24px;font-weight:700}}
.header p{{color:#8b95a8;font-size:13px;margin-top:4px}}
.report-item{{background:#131722;border:1px solid #1e2434;border-radius:14px;padding:16px;margin-bottom:10px;cursor:pointer;transition:all .2s}}
.report-item:hover{{border-color:#2962ff;background:#182033}}
.report-item .date{{color:#2962ff;font-size:14px;font-weight:600;margin-bottom:6px}}
.report-item .preview{{color:#8b95a8;font-size:13px;line-height:1.5;white-space:pre-wrap;overflow:hidden;max-height:3em}}
.help{{text-align:center;padding:30px;color:#4a5568;font-size:12px}}
</style>
</head>
<body>
<div class="header">
    <h1>量化动量选股系统</h1>
    <p>五维动量打分 | CTAAgents 体系 | 每日收盘扫描</p>
</div>
{items if items else '<div class="help">暂无报告，请先运行程序生成</div>'}
<div class="help">{'共 ' + str(len(files)) + ' 份报告' if items else ''}</div>
</body>
</html>"""

# ═══ WPS 兼容版 HTML (表格布局+内联样式) ════════════════

def gen_html_wps(stock_res, etf_res, label):
    """生成 WPS/Word 兼容的 HTML，使用表格布局和内联样式"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 统计
    b_s = sum(1 for r in stock_res if "买入" in r["signal"])
    h_s = sum(1 for r in stock_res if "持有" in r["signal"] or "观望" in r["signal"])
    s_s = sum(1 for r in stock_res if "回避" in r["signal"] or "注意风险" in r["signal"])
    b_e = sum(1 for r in etf_res if "买入" in r["signal"])
    h_e = sum(1 for r in etf_res if "持有" in r["signal"] or "观望" in r["signal"])
    s_e = sum(1 for r in etf_res if "回避" in r["signal"] or "注意风险" in r["signal"])

    avg_s = sum(r["total"] for r in stock_res) / len(stock_res) if stock_res else 0
    avg_e = sum(r["total"] for r in etf_res) / len(etf_res) if etf_res else 0
    avg_all = (avg_s + avg_e) / 2 if (stock_res or etf_res) else 0

    if avg_all >= 65:
        mkt_text, mkt_color, mkt_desc = "市场偏强", "#cc0000", "可适当加仓"
    elif avg_all >= 50:
        mkt_text, mkt_color, mkt_desc = "市场中性", "#cc8800", "精选个股为主"
    else:
        mkt_text, mkt_color, mkt_desc = "市场偏弱", "#008800", "控制仓位注意风险"

    DIM_NAMES = ["价格动量", "成交量", "趋势结构", "相对强度", "风险控制"]
    DIM_MAX = [30, 20, 25, 15, 10]

    def score_bg(total):
        if total >= 70: return "#ffe0e0"
        if total >= 50: return "#fff8e0"
        return "#e0f5e0"

    def score_fg(total):
        if total >= 70: return "#cc0000"
        if total >= 50: return "#cc8800"
        return "#008800"

    def signal_style(signal):
        if "买入" in signal: return "background:#cc0000;color:#ffffff;font-weight:bold;padding:3px 8px;font-size:12px;"
        if "持有" in signal or "观望" in signal: return "background:#cc8800;color:#ffffff;font-weight:bold;padding:3px 8px;font-size:12px;"
        return "background:#008800;color:#ffffff;font-weight:bold;padding:3px 8px;font-size:12px;"

    def change_color(val):
        return "#cc0000" if val > 0 else "#008800" if val < 0 else "#333333"

    def make_table(items, start_rank=1):
        rows = ""
        for i, r in enumerate(items):
            rank = start_rank + i
            s_bg = score_bg(r["total"])
            s_fg = score_fg(r["total"])
            chg = r.get("change", 0)
            chg_c = change_color(chg)
            r15_c = change_color(r["r15"])
            r45_c = change_color(r["r45"])
            dd_c = "#cc0000" if r["dd"] > 10 else "#cc8800" if r["dd"] > 5 else "#008800"

            # 维度得分小表格
            dim_cells = ""
            for j, (dn, dm, dv) in enumerate(zip(DIM_NAMES, DIM_MAX, r["detail"])):
                pct = dv / dm * 100
                if pct >= 80: dc_bg = "#cc0000"; dc_fg = "#ffffff"
                elif pct >= 50: dc_bg = "#cc8800"; dc_fg = "#ffffff"
                else: dc_bg = "#dddddd"; dc_fg = "#666666"
                dim_cells += f'<td style="background:{dc_bg};color:{dc_fg};text-align:center;font-size:11px;padding:2px 4px;white-space:nowrap;">{dn}<br>{dv}/{dm}</td>'

            rows += f"""<tr>
<td style="text-align:center;font-weight:bold;padding:4px;border:1px solid #ddd;">{rank}</td>
<td style="text-align:center;padding:4px;border:1px solid #ddd;font-family:Consolas,monospace;font-size:12px;">{r['code']}</td>
<td style="padding:4px;border:1px solid #ddd;font-weight:bold;font-size:13px;">{r['name']}</td>
<td style="text-align:center;padding:4px;border:1px solid #ddd;background:{s_bg};color:{s_fg};font-size:18px;font-weight:bold;font-family:Consolas,monospace;">{r['total']}</td>
<td style="text-align:center;padding:4px;border:1px solid #ddd;"><span style="{signal_style(r['signal'])}">{r['signal']}</span></td>
<td style="text-align:right;padding:4px;border:1px solid #ddd;font-family:Consolas,monospace;font-size:13px;font-weight:bold;">{r['price']:.2f}</td>
<td style="text-align:right;padding:4px;border:1px solid #ddd;color:{chg_c};font-family:Consolas,monospace;font-size:12px;font-weight:bold;">{chg:+.2f}%</td>
<td style="text-align:right;padding:4px;border:1px solid #ddd;color:{r15_c};font-family:Consolas,monospace;font-size:12px;">{r['r15']:+.1f}%</td>
<td style="text-align:right;padding:4px;border:1px solid #ddd;color:{r45_c};font-family:Consolas,monospace;font-size:12px;">{r['r45']:+.1f}%</td>
<td style="text-align:center;padding:4px;border:1px solid #ddd;font-size:12px;">{r['ma_status']}</td>
<td style="text-align:center;padding:4px;border:1px solid #ddd;font-family:Consolas,monospace;font-size:12px;">{r['vol_ratio']:.2f}</td>
<td style="text-align:center;padding:4px;border:1px solid #ddd;font-family:Consolas,monospace;font-size:12px;">{r['rsi']:.1f}</td>
<td style="text-align:right;padding:4px;border:1px solid #ddd;color:{dd_c};font-family:Consolas,monospace;font-size:12px;">-{r['dd']:.1f}%</td>
<td style="text-align:right;padding:4px;border:1px solid #ddd;font-family:Consolas,monospace;font-size:11px;color:#666;">{r['support']:.2f}</td>
<td style="text-align:right;padding:4px;border:1px solid #ddd;font-family:Consolas,monospace;font-size:11px;color:#666;">{r['pressure']:.2f}</td>
</tr>
<tr>
<td colspan="5" style="padding:2px 8px;border:1px solid #ddd;background:#f8f8f8;font-size:11px;color:#666;">五维得分明细</td>
{dim_cells}
<td colspan="5" style="padding:2px 8px;border:1px solid #ddd;background:#f8f8f8;font-size:11px;color:#666;">&nbsp;</td>
</tr>"""
        return rows

    # 表头
    th_style = 'style="background:#1a237e;color:#ffffff;padding:6px 4px;border:1px solid #1a237e;font-size:12px;font-weight:bold;text-align:center;white-space:nowrap;"'
    ths = ""
    for h in ["#", "代码", "名称", "总分", "信号", "现价", "涨跌", "15日", "45日", "均线", "量比", "RSI", "回撤", "支撑", "压力"]:
        align = "left" if h == "名称" else "right" if h in ("现价", "涨跌", "15日", "45日", "回撤", "支撑", "压力") else "center"
        ths += f'<th {th_style[:-1]} text-align:{align};">{h}</th>'

    stock_table = make_table(stock_res) if stock_res else '<tr><td colspan="15" style="padding:20px;text-align:center;color:#999;border:1px solid #ddd;">暂无数据</td></tr>'
    etf_table = make_table(etf_res) if etf_res else '<tr><td colspan="15" style="padding:20px;text-align:center;color:#999;border:1px solid #ddd;">暂无数据</td></tr>'

    # 推文
    tweet_text = gen_tweet(stock_res, etf_res, label)
    # 转义 HTML
    tweet_escaped = tweet_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>\n")

    # Top1
    top1 = stock_res[0] if stock_res else None
    top1_html = ""
    if top1:
        t1_c = score_fg(top1["total"])
        top1_html = f"""<table style="width:100%;border-collapse:collapse;margin-bottom:12px;">
<tr>
<td style="background:#cc0000;color:#ffffff;font-weight:bold;padding:6px 12px;font-size:13px;width:60px;text-align:center;">TOP 1</td>
<td style="background:#f5f5f5;padding:6px 12px;border:1px solid #ddd;font-weight:bold;font-size:14px;">{top1['name']} <span style="color:#888;font-size:12px;font-family:Consolas,monospace;">{top1['code']}</span></td>
<td style="background:#f5f5f5;padding:6px 12px;border:1px solid #ddd;text-align:center;width:80px;"><span style="color:{t1_c};font-size:24px;font-weight:bold;font-family:Consolas,monospace;">{top1['total']}</span></td>
<td style="background:#f5f5f5;padding:6px 12px;border:1px solid #ddd;text-align:center;width:80px;"><span style="{signal_style(top1['signal'])}">{top1['signal']}</span></td>
<td style="background:#f5f5f5;padding:6px 12px;border:1px solid #ddd;text-align:right;width:100px;font-family:Consolas,monospace;font-size:14px;font-weight:bold;">{top1['price']:.2f}</td>
</tr>
</table>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>量化动量选股系统 {label}</title>
</head>
<body style="background:#ffffff;color:#333333;font-family:'Microsoft YaHei','SimSun',Arial,sans-serif;font-size:13px;margin:0;padding:20px;">

<table style="width:100%;border-collapse:collapse;margin-bottom:16px;">
<tr>
<td style="background:#1a237e;color:#ffffff;padding:16px 24px;font-size:20px;font-weight:bold;">量化动量选股系统</td>
<td style="background:#1a237e;color:#ffffff;padding:16px 24px;text-align:right;font-size:13px;">{label}<br>扫描时间 {now_str}</td>
</tr>
<tr>
<td colspan="2" style="background:#e8eaf6;padding:8px 24px;font-size:12px;color:#555;">五维动量打分模型 | 股票 {len(stock_res)} 只 + ETF {len(etf_res)} 只</td>
</tr>
</table>

<table style="width:100%;border-collapse:collapse;margin-bottom:16px;">
<tr>
<td style="width:25%;background:#f5f5f5;border:1px solid #ddd;padding:10px 14px;text-align:center;">
<div style="font-size:11px;color:#888;margin-bottom:4px;">市场温度</div>
<div style="font-size:18px;font-weight:bold;color:{mkt_color};">{mkt_text}</div>
<div style="font-size:11px;color:#888;margin-top:2px;">{mkt_desc} | 均分 {avg_all:.1f}</div>
</td>
<td style="width:25%;background:#f5f5f5;border:1px solid #ddd;padding:10px 14px;text-align:center;">
<div style="font-size:11px;color:#888;margin-bottom:4px;">买入信号</div>
<div style="font-size:18px;font-weight:bold;color:#cc0000;">{b_s + b_e}</div>
<div style="font-size:11px;color:#888;margin-top:2px;">股票 {b_s} | ETF {b_e}</div>
</td>
<td style="width:25%;background:#f5f5f5;border:1px solid #ddd;padding:10px 14px;text-align:center;">
<div style="font-size:11px;color:#888;margin-bottom:4px;">持有/观望</div>
<div style="font-size:18px;font-weight:bold;color:#cc8800;">{h_s + h_e}</div>
<div style="font-size:11px;color:#888;margin-top:2px;">股票 {h_s} | ETF {h_e}</div>
</td>
<td style="width:25%;background:#f5f5f5;border:1px solid #ddd;padding:10px 14px;text-align:center;">
<div style="font-size:11px;color:#888;margin-bottom:4px;">注意/回避</div>
<div style="font-size:18px;font-weight:bold;color:#008800;">{s_s + s_e}</div>
<div style="font-size:11px;color:#888;margin-top:2px;">股票 {s_s} | ETF {s_e}</div>
</td>
</tr>
</table>

{top1_html}

<table style="width:100%;border-collapse:collapse;margin-bottom:6px;">
<tr><td style="font-size:15px;font-weight:bold;color:#1a237e;padding:4px 0;border-bottom:2px solid #1a237e;">股票明细</td></tr>
</table>
<table style="width:100%;border-collapse:collapse;margin-bottom:16px;">
<tr>{ths}</tr>
{stock_table}
</table>

<table style="width:100%;border-collapse:collapse;margin-bottom:6px;">
<tr><td style="font-size:15px;font-weight:bold;color:#1a237e;padding:4px 0;border-bottom:2px solid #1a237e;">ETF 明细</td></tr>
</table>
<table style="width:100%;border-collapse:collapse;margin-bottom:16px;">
<tr>{ths}</tr>
{etf_table}
</table>

<table style="width:100%;border-collapse:collapse;margin-bottom:16px;">
<tr><td style="background:#1a237e;color:#ffffff;padding:8px 14px;font-size:14px;font-weight:bold;">推文摘要</td></tr>
<tr><td style="border:1px solid #ddd;padding:12px 14px;font-size:12px;line-height:1.8;font-family:Consolas,monospace;white-space:normal;">{tweet_escaped}</td></tr>
</table>

<table style="width:100%;border-collapse:collapse;">
<tr><td style="text-align:center;padding:16px;color:#999;font-size:11px;border-top:1px solid #eee;">
量化模型仅供参考 不构成投资建议<br>
CTAAgents 动量选股体系 v4.0 | 数据源: 腾讯自选股 | {now_str}
</td></tr>
</table>

</body>
</html>"""
    return html

# ═══ tkinter 进度窗口 ═════════════════════════════════

class ProgressWindow:
    """控制台隐藏时显示进度窗口"""
    def __init__(self):
        self.root = None
        self.progress = None
        self.status_label = None
        self.detail_label = None
        self._closed = False

    def start(self):
        try:
            import tkinter as tk
            from tkinter import ttk
        except ImportError:
            return
        self.root = tk.Tk()
        self.root.title("量化动量选股系统 v4.0")
        self.root.geometry("440x280")
        self.root.resizable(False, False)
        self.root.configure(bg="#0a0e17")

        # 居中
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"+{x}+{y}")

        # 标题
        title_frame = tk.Frame(self.root, bg="#0a0e17")
        title_frame.pack(pady=(24, 4))
        tk.Label(title_frame, text="量化动量选股系统", font=("Microsoft YaHei", 16, "bold"),
                 bg="#0a0e17", fg="#dee5f0").pack()
        tk.Label(title_frame, text="五维动量打分模型 v4.0", font=("Microsoft YaHei", 10),
                 bg="#0a0e17", fg="#8b95a8").pack()

        # 进度条
        bar_frame = tk.Frame(self.root, bg="#0a0e17")
        bar_frame.pack(pady=(20, 8), padx=40, fill="x")
        self.progress = ttk.Progressbar(bar_frame, length=340, mode="determinate",
                                        maximum=100, value=0)
        self.progress.pack(fill="x")

        # 状态
        self.status_label = tk.Label(self.root, text="正在初始化...", font=("Microsoft YaHei", 11),
                                     bg="#0a0e17", fg="#2962ff")
        self.status_label.pack(pady=(4, 2))

        self.detail_label = tk.Label(self.root, text="", font=("Microsoft YaHei", 9),
                                     bg="#0a0e17", fg="#8b95a8")
        self.detail_label.pack()

        # 配置 ttk 样式
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TProgressbar",
                        troughcolor="#1e2434",
                        background="#2962ff",
                        darkcolor="#2962ff",
                        lightcolor="#5c8aff",
                        bordercolor="#1e2434",
                        thickness=12)

        self.root.protocol("WM_DELETE_WINDOW", lambda: None)
        self.root.update()

    def update(self, value, status, detail=""):
        if self._closed or not self.root:
            return
        self.progress["value"] = value
        self.status_label.config(text=status)
        self.detail_label.config(text=detail)
        self.root.update()

    def close(self):
        if self._closed or not self.root:
            return
        self._closed = True
        try:
            self.root.destroy()
        except:
            pass

# ═══ 主流程 ═════════════════════════════════════════

def main():
    today = datetime.now()
    wd = today.weekday()
    if wd >= 5:
        today_label = (today - timedelta(days=wd-4)).strftime("%Y-%m-%d") + " (最近交易日)"
    else:
        today_label = today.strftime("%Y-%m-%d")

    # 启动进度窗口
    pw = ProgressWindow()
    pw.start()

    all_items = [("stock", c, n) for c, n in STOCKS] + [("etf", c, n) for c, n in ETFS]
    total = len(all_items)

    sres = []
    eres = []

    for idx, (cat, code, name) in enumerate(all_items):
        progress = (idx / total) * 100
        pw.update(progress, f"正在获取数据 [{idx+1}/{total}]", f"{code} {name}")

        kl = fetch_kline(code)
        if kl:
            s = calc_score(kl)
            if s:
                r = {**{"code":code, "name":name}, **s}
                if cat == "stock":
                    sres.append(r)
                else:
                    eres.append(r)
        time.sleep(0.2)

    pw.update(95, "正在生成报告...", "")

    sres.sort(key=lambda x: x["total"], reverse=True)
    eres.sort(key=lambda x: x["total"], reverse=True)

    if not sres and not eres:
        pw.update(100, "无有效数据", "请检查网络连接")
        time.sleep(3)
        pw.close()
        return

    # 生成 HTML (浏览器版)
    html = gen_html(sres, eres, today_label)
    rname = f"动量选股_{today_label[:10].replace('-','')}.html"
    rpath = os.path.join(OUTPUT_DIR, rname)
    with open(rpath, "w", encoding="utf-8") as f:
        f.write(html)
    
    # 生成首页导航 (网页版用)
    index_html = gen_index_page(OUTPUT_DIR)
    index_path = os.path.join(OUTPUT_DIR, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_html)

    # 生成 JSON 列表 (网页版用)
    import json as _json
    _list = [{"name": rname, "date": today_label[:10],
              "stocks": len(sres), "etfs": len(eres),
              "preview": f"Top1:{sres[0]['name']} {sres[0]['total']}分 {sres[0]['signal']}" if sres else ""}]
    _list_path = os.path.join(OUTPUT_DIR, "list.json")
    with open(_list_path, "w", encoding="utf-8") as f:
        _json.dump(_list, f, ensure_ascii=False, indent=2)

    # 生成 HTML (WPS兼容版)
    html_wps = gen_html_wps(sres, eres, today_label)
    rname_wps = f"动量选股_{today_label[:10].replace('-','')}_WPS.html"
    rpath_wps = os.path.join(OUTPUT_DIR, rname_wps)
    with open(rpath_wps, "w", encoding="utf-8") as f:
        f.write(html_wps)

    # 生成推文
    tweet = gen_tweet(sres, eres, today_label)
    tname = f"推文_{today_label[:10].replace('-','')}.txt"
    tpath = os.path.join(OUTPUT_DIR, tname)
    with open(tpath, "w", encoding="utf-8") as f:
        f.write(tweet)

    pw.update(100, "报告已生成", f"股票{len(sres)}只 + ETF{len(eres)}只")

    # 打开浏览器
    try:
        webbrowser.open(f"file://{os.path.abspath(rpath)}")
    except:
        pass

    time.sleep(2)
    pw.close()

if __name__ == "__main__":
    # 网页服务模式: python ai_stock_picker.py --serve
    if len(sys.argv) > 1 and sys.argv[1] == "--serve":
        try:
            from http.server import HTTPServer, SimpleHTTPRequestHandler
            import socketserver
            port = 8899
            os.chdir(OUTPUT_DIR)
            handler = SimpleHTTPRequestHandler
            httpd = socketserver.TCPServer(("0.0.0.0", port), handler)
            print(f"\n  === 量化动量选股 网页服务 ===")
            print(f"  本机访问: http://localhost:{port}")
            print(f"  手机访问: http://{_get_ip()}:{port}")
            print(f"  按 Ctrl+C 停止服务\n")
            print(f"  提示：先运行一次生成报告，再启动服务查看")
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  服务已停止")
        except Exception as e:
            print(f"\n  启动服务失败: {e}")
            print(f"  请先运行 python ai_stock_picker.py 生成报告")
        sys.exit(0)
    
    # 正常模式：跑数据生成报告
    try:
        main()
    except Exception as e:
        import traceback
        err_log = os.path.join(_BASE_DIR, "选股错误日志.txt")
        with open(err_log, "w", encoding="utf-8") as f:
            f.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"错误: {e}\n\n")
            traceback.print_exc(file=f)
        try:
            import tkinter.messagebox as mb
            mb.showerror("量化动量选股 - 错误", f"程序出错: {e}\n\n详见: {err_log}")
        except:
            pass
