# DeepSock - DeepSeek 多币种期货合约交易机器人

一个利用 DeepSeek (或其他 OpenAI 兼容 API) 分析市场并自动执行交易的 Python 加密货币期货机器人。

## 功能亮点

*   **AI 驱动决策**: 核心交易逻辑由强大的 LLM 驱动，生成精准的交易信号、止损止盈位和信心度评估。
*   **实时行情分析**: AI 实时分析 K 线、技术指标和市场深度，捕捉瞬息万变的市场机会。
*   **实时新闻整合**(AI增强版): **AI 增强功能**。集成 BlockBeats 等权威 RSS 新闻源，将最新市场动态实时注入 AI 分析流程，实现更前瞻的决策。(通过 `ENABLE_NEWS` 环境变量开关)
*   **动态仓位管理**(AI增强版): **AI 增强功能**。AI 不仅决定买卖方向，还能根据市场分析和账户风险状况，智能计算并建议每次交易的最优仓位大小。(依赖 `ENABLE_NEWS` 提供的新闻进行更全面分析)
*   **多币种支持**: 可同时监控和交易多个加密货币合约 (如 BTC/USDT, ETH/USDT 等)。
*   **实时持仓**: 准确获取并显示交易所实时持仓信息。
*   **灵活配置**: 通过简单的 `.env` 文件即可配置所有参数，包括交易对、杠杆、模型选择、AI 增强功能开关等。

## 依赖

*   `Docker` (推荐) 或 `Python 3.8+`
*   相关 Python 包见 `requirements.txt`

## 快速开始

### 1. 准备工作

*   **克隆项目**:
    ```bash
    git clone https://github.com/OiCkilL/deepsock.git
    cd deepsock
    ```
*   **配置 `.env` 文件**:
    *   复制 `.env.example` 为 `.env`: `cp .env.example .env`
    *   **重要**: 编辑 `.env` 文件，填入您的交易所和 `LLM` (如 DeepSeek) API 密钥及其他必要参数。

### 2.A. 使用 Docker (推荐)

*   **构建镜像**:
    ```bash
    docker build -t deepsock .
    ```
*   **运行**:
    *   确保 `.env` 文件已配置好。
    *   运行容器:
        ```bash
        docker run --env-file .env deepsock
        ```
*   **查看日志**:
    *   如果您在后台运行容器（使用 `-d` 标志），或者想查看正在运行的容器的日志，可以使用 `docker logs` 命令。
    *   **获取容器 ID 或名称**: 运行 `docker ps` 查看当前运行的容器列表。
    *   **查看日志**:
        ```bash
        docker logs <CONTAINER_ID_OR_NAME>
        ```
    *   **实时跟踪日志**: 添加 `-f` 标志可以像 `tail -f` 一样实时查看日志输出。
        ```bash
        docker logs -f <CONTAINER_ID_OR_NAME>
        ```

### 2.B. 使用 Docker Compose

*   **构建并启动**:
    *   确保 `.env` 文件已配置好。
    *   构建镜像并启动容器:
        ```bash
        docker compose up --build
        ```
*   **后台运行**: 添加 `-d` 参数，例如 `docker compose up -d --build`。
*   **查看日志**:
    *   **查看所有服务日志**:
        ```bash
        docker-compose logs
        ```
    *   **实时跟踪所有服务日志**:
        ```bash
        docker-compose logs -f
        ```
    *   **查看特定服务日志** (服务名默认为 `deepsock`，定义在 `compose.yml` 中):
        
        ```bash
        docker compose logs deepsock
        ```
    *   **实时跟踪特定服务日志**:
        
        ```bash
        docker compose logs -f deepsock
        ```
*   **停止**: 在项目目录下运行 `docker-compose down`。

### 2.C. 本地运行 (不使用 Docker)

*   **安装依赖**:
    ```bash
    pip install -r requirements.txt
    ```
*   **配置 `.env` 文件**。
*   **运行**:
    ```bash
    python deepsock.py
    ```

## 配置说明 (`.env` 文件)

请参考 `.env.example` 文件了解所有可配置的选项。关键配置包括：

*   `BINANCE_API_KEY`, `BINANCE_SECRET`: 您的 Binance API 凭据。
*   `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL_NAME`: 您的 LLM (如 DeepSeek) API 凭据和模型设置。
*   `TRADE_SYMBOLS`, `TRADE_LEVERAGES`: 逗号分隔的交易对和对应杠杆。
*   `ENABLE_NEWS`: **AI 增强功能开关**。设置为 `True` 以启用新闻模块和基于新闻的动态仓位分析，`False` 则禁用此 AI 增强功能。
*   `RSS_FEED_URLS`, `RSS_CHECK_INTERVAL_MINUTES`: 新闻源 URL 和检查间隔（如果 `ENABLE_NEWS=True`）。
*   `TEST_MODE`: 设置为 `True` 进入模拟模式（仅打印信号，不下单）。

## 警告

**⚠️ 警告: 加密货币交易风险极高，可能导致巨额亏损。本项目代码仅供学习和研究使用。任何基于此代码进行的实盘交易，您需自行承担全部责任。投资有风险，入市须谨慎。**
