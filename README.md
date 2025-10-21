# DeepSock - DeepSeek 多币种期货交易机器人

一个基于 DeepSeek API 分析市场并使用 Binance Future API 执行交易的 Python 自动交易机器人。

## 功能

*   **多币种支持**: 可同时监控和交易多个合约。
*   **AI 分析**: 利用 DeepSeek 生成交易信号、止损止盈和信心度。
*   **实时持仓**: 准确获取并显示 API 返回的实时持仓信息。
*   **格式化输出**: 持仓信息以易读格式展示。
*   **灵活配置**: 通过 `.env` 文件配置币种、数量、杠杆等参数。

## 依赖

*   `python 3.x`
*   `openai`, `ccxt`, `pandas`, `schedule`, `json5`, `python-dotenv`

## 使用

1.  安装依赖: `pip install -r requirements.txt` 
2.  配置 `.env` 文件 (参考 `.env.example` 格式)。
3.  运行: `python deepsock.py` 

**警告: 期货交易风险高，请谨慎使用。**
