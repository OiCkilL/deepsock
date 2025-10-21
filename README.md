# DeepSock - DeepSeek 多币种合约交易机器人

一个基于 DeepSeek API 分析市场并使用 Binance Future API 执行交易的 Python 自动交易机器人。

## 版本

*   **`deepsock.py`**: 标准版，基于 K 线、技术指标和持仓信息进行 AI 分析。
*   **`deepsock_ai.py`**: 增强版，在标准版基础上整合了 BlockBeats 实时新闻，为 AI 决策提供更多市场信息。

## 功能

*   **多币种支持**: 可同时监控和交易多个合约。
*   **AI 分析**: 利用 DeepSeek 生成交易信号、止损止盈和信心度。
*   **实时持仓**: 准确获取并显示 API 返回的实时持仓信息。
*   **格式化输出**: 持仓信息以易读格式展示。
*   **灵活配置**: 通过 `.env` 文件配置币种、数量、杠杆等参数。

## 依赖

*   `python 3.x`
*   `openai`, `ccxt`, `pandas`, `schedule`, `json5`, `feedparser`, `python-dotenv`

## 使用

1.  安装依赖: `pip install -r requirements.txt` 
2.  配置 `.env` 文件 (参考 `.env.example` 格式)。
3.  运行:
    *   标准版: `python deepsock.py`
    *   新闻增强版: `python deepsock_ai.py`

**⚠️ 警告: 加密货币交易风险高，请低倍率谨慎使用。**
