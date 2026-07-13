# 量化动量选股系统

手机小程序风格的 A 股动量选股报告系统，每日收盘自动扫描 10 只股票 + 10 只 ETF，生成精致手机版报告。

## 核心功能

- **五维动量打分**：价格动量(30)+成交量(20)+趋势结构(25)+相对强度(15)+风险控制(10)
- **手机小程序 UI**：Tab 切换股票/ETF/推文，圆环得分、迷你走势图、五维进度条
- **自动部署**：配合 GitHub Pages 生成公开链接，客户手机直接打开
- **双版本输出**：手机版 + WPS 兼容版（表格布局）

## 快速使用

```bash
# 安装依赖
pip install requests

# 生成报告
python ai_stock_picker.py

# 启动本地服务（手机同局域网查看）
python ai_stock_picker.py --serve
```

报告输出到 `reports/` 目录：
- `动量选股_20260713.html` — 手机小程序版
- `动量选股_20260713_WPS.html` — WPS/Word 兼容版
- `推文_20260713.txt` — 推文摘要
- `index.html` — 报告首页（列出所有历史报告）

## 部署到 GitHub Pages

1. **在 GitHub 上建仓库**：打开 https://github.com/new
   - 仓库名：`momentum-stock-picker`
   - 设为 **Public**
   - 不要勾选任何初始化选项

2. **上传文件**：
   ```bash
   # 在 WSL 中执行
   cd /mnt/c/Users/86157/Desktop/动量选股小程序
   git init
   git add .
   git commit -m "首次提交"
   git branch -M main
   git remote add origin https://github.com/Yin56898956/momentum-stock-picker.git
   git push -u origin main
   ```

3. **开启 Pages**：
   - 打开仓库 → Settings → Pages
   - Source 选 **Deploy from a branch**
   - Branch 选 `main`，目录选 `/ (root)`
   - 点 **Save**
   - 等待 1-2 分钟，访问 `https://yin56898956.github.io/momentum-stock-picker/`

## 每日自动更新

配合 GitHub Actions（可选），每天收盘后自动运行并更新报告到 Pages。

## 技术栈

- Python 3.8+，无外部依赖（仅需 requests）
- 数据源：腾讯自选股（免费，无需 API Key）
- 五维动量打分模型：价格动量 + 成交量 + 趋势结构 + 相对强度 + 风险控制
