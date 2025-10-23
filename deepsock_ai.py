import os
import time
import schedule
from openai import OpenAI
import ccxt
import pandas as pd
from datetime import datetime
import json
import json5 # 用于解析可能非标准的JSON
import feedparser # 用于解析RSS
import math # 用于数学计算 (floor)
from dotenv import load_dotenv
load_dotenv()

# --- 从 .env 读取 LLM 配置并初始化客户端 ---
LLM_API_KEY = os.getenv('LLM_API_KEY')
LLM_BASE_URL = os.getenv('LLM_BASE_URL', 'https://api.deepseek.com') # 提供默认值
LLM_MODEL_NAME = os.getenv('LLM_MODEL_NAME', 'deepseek-chat')       # 提供默认值

print(f"[CONFIG] LLM API Key: {'*' * len(LLM_API_KEY) if LLM_API_KEY else 'NOT SET'}")
print(f"[CONFIG] LLM Base URL: {LLM_BASE_URL}")
print(f"[CONFIG] LLM Model Name: {LLM_MODEL_NAME}")

# --- 初始化 LLM 客户端 (OpenAI 兼容) ---
llm_client = OpenAI(
    api_key=LLM_API_KEY,
    base_url=LLM_BASE_URL
)

exchange = ccxt.binance({
    'options': {'defaultType': 'future'},
    'apiKey': os.getenv('BINANCE_API_KEY'),
    'secret': os.getenv('BINANCE_SECRET'),
})

# --- 从 .env 读取多币种配置 ---
def parse_env_config():
    """解析环境变量，返回配置字典"""
    symbols = os.getenv('TRADE_SYMBOLS', '').split(',')
    # amounts = os.getenv('TRADE_AMOUNTS', '').split(',') # 移除固定数量配置
    leverages = os.getenv('TRADE_LEVERAGES', '').split(',')

    # 验证数量是否一致 (只需要 symbols 和 leverages)
    if not (len(symbols) == len(leverages)): # 修改验证条件
        raise ValueError("TRADE_SYMBOLS 和 TRADE_LEVERAGES 的数量不匹配") # 修改错误信息

    config = {}
    for i in range(len(symbols)):
        symbol = symbols[i].strip()
        if not symbol:
            continue # 跳过空字符串

        # 移除 amount 的解析逻辑
        # try:
        #     amount = float(amounts[i].strip())
        # except ValueError:
        #     raise ValueError(f"TRADE_AMOUNTS 中的值必须为数字: {amounts[i]}")

        try:
            leverage = int(leverages[i].strip())
        except ValueError:
            raise ValueError(f"TRADE_LEVERAGES 中的值必须为整数: {leverages[i]}")

        # 从env读取测试模式设置
        test_mode_str = os.getenv('TEST_MODE', 'False').lower()
        test_mode = test_mode_str in ['true', '1', 'yes', 'on']

        config[symbol] = {
            'symbol': symbol,
            'leverage': leverage,
            'timeframe': os.getenv('TIMEFRAME', '15m'), # 从env读取周期
            # 'amount': amount, # 移除固定 amount
            'test_mode': test_mode, # 使用TEST_MODE
        }
    return config

TRADE_CONFIG = parse_env_config()

# --- 从 .env 读取风险管理配置 ---
def parse_risk_management_config():
    """解析环境变量中的风险管理配置"""
    config = {}

    # 从环境变量读取，提供默认值
    config['max_risk_per_trade'] = float(os.getenv('MAX_RISK_PER_TRADE', '0.02')) # 默认 2%
    config['max_total_risk'] = float(os.getenv('MAX_TOTAL_RISK', '0.1'))         # 默认 10%
    config['max_consecutive_losses'] = int(os.getenv('MAX_CONSECUTIVE_LOSSES', '3')) # 默认 3次
    config['stop_loss_multiplier'] = float(os.getenv('STOP_LOSS_MULTIPLIER', '1.5')) # 默认 1.5倍
    config['take_profit_multiplier'] = float(os.getenv('TAKE_PROFIT_MULTIPLIER', '2.0')) # 默认 2.0倍
    config['max_positions'] = int(os.getenv('MAX_POSITIONS', '5'))                   # 默认 5个
    config['balance_warning_level'] = float(os.getenv('BALANCE_WARNING_LEVEL', '100')) # 默认 100 USDT
    config['max_drawdown'] = float(os.getenv('MAX_DRAWDOWN', '0.2'))                 # 默认 20%

    return config

RISK_MANAGEMENT_CONFIG = parse_risk_management_config()
print(f"[CONFIG] 风险管理配置: {RISK_MANAGEMENT_CONFIG}")


# --- 全局变量 (改为字典以支持多币种) ---
price_history = {symbol: [] for symbol in TRADE_CONFIG.keys()}
signal_history = {symbol: [] for symbol in TRADE_CONFIG.keys()}
positions = {symbol: None for symbol in TRADE_CONFIG.keys()}

# --- 全局新闻变量 ---
latest_news_text = "【最新市场新闻】\n无近期新闻。\n" # 初始化新闻内容
last_news_hash = None # 用于存储上一次新闻内容的哈希值

# --- 从 .env 读取 RSS 配置 ---
def parse_rss_config():
    """解析环境变量中的RSS配置"""
    rss_urls_str = os.getenv('RSS_FEED_URLS', '')
    if not rss_urls_str:
        raise ValueError("RSS_FEED_URLS 环境变量未设置或为空")
    # 以逗号分割多个URL
    urls = [url.strip() for url in rss_urls_str.split(',')]
    # 验证每个URL是否以 http:// 或 https:// 开头
    for url in urls:
        if not url.startswith(('http://', 'https://')):
            raise ValueError(f"RSS URL 格式无效: {url}")
    return urls

RSS_FEED_URLS = parse_rss_config()
RSS_CHECK_INTERVAL_MINUTES = int(os.getenv('RSS_CHECK_INTERVAL_MINUTES', '5'))

print(f"[CONFIG] RSS 源: {RSS_FEED_URLS}")
print(f"[CONFIG] RSS 检查间隔: {RSS_CHECK_INTERVAL_MINUTES} 分钟")

# --- 核心函数 ---
def setup_exchange():
    """设置交易所参数，为所有配置的币种设置杠杆"""
    try:
        balance = exchange.fetch_balance({'type': 'future'}) # 明确获取期货账户余额
        usdt_balance = balance['USDT']['free']
        print(f"当前USDT余额: {usdt_balance:.2f}")
        for symbol, config in TRADE_CONFIG.items():
            try:
                exchange.set_leverage(config['leverage'], symbol)
                print(f"为 {symbol} 设置杠杆倍数: {config['leverage']}x")
            except Exception as e:
                # 有些交易所或币种可能不允许通过API设置杠杆，或者设置失败
                print(f"为 {symbol} 设置杠杆失败: {e}. 请手动在交易所设置或忽略。")
        return True
    except Exception as e:
        print(f"交易所设置失败: {e}")
        return False

def get_ohlcv(symbol, timeframe='15m', limit=10):
    """获取指定币种的K线数据"""
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        current_data = df.iloc[-1]
        previous_data = df.iloc[-2] if len(df) > 1 else current_data
        return {
            'symbol': symbol,
            'price': current_data['close'],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'high': current_data['high'],
            'low': current_data['low'],
            'volume': current_data['volume'],
            'timeframe': timeframe,
            'price_change': ((current_data['close'] - previous_data['close']) / previous_data['close']) * 100,
            'kline_data': df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].tail(5).to_dict('records')
        }
    except Exception as e:
        print(f"获取 {symbol} K线数据失败: {e}")
        return None

def get_positions():
    """获取所有持仓情况（修正 symbol 格式转换）"""
    try:
        # 获取所有持仓
        all_positions = exchange.fetch_positions()
        current_positions = {}
        for pos in all_positions:
            exchange_symbol_full = pos['symbol'] # 从交易所获取的完整原始symbol，例如 'SOL/USDT:USDT'
            # 尝试将交易所的完整 symbol 格式转换为TRADE_CONFIG中的格式（例如 'SOL/USDT'）
            # Binance期货 pos['symbol'] 通常是 'BASE/QUOTE:QUOTE'，如 'SOL/USDT:USDT'
            # 我们取冒号前的部分，即 'BASE/QUOTE'，如 'SOL/USDT'
            config_symbol = exchange_symbol_full.split(':')[0] # 以冒号分割，取第一部分

            # 检查转换后的 config_symbol 是否在我们的配置中
            if config_symbol in TRADE_CONFIG:
                position_amt = 0
                if 'positionAmt' in pos.get('info', {}):
                    position_amt = float(pos['info']['positionAmt'])
                elif 'contracts' in pos:
                    contracts = float(pos['contracts'])
                    if pos.get('side') == 'short':
                        position_amt = -contracts
                    else:
                        position_amt = contracts
                if position_amt != 0:  # 有持仓
                    side = 'long' if position_amt > 0 else 'short'
                    current_positions[config_symbol] = { # 使用 config_symbol 作为键
                        'side': side,
                        'size': abs(position_amt),
                        'entry_price': float(pos.get('entryPrice', 0)),
                        'unrealized_pnl': float(pos.get('unrealizedPnl', 0)),
                        'position_amt': position_amt,
                        'symbol': config_symbol # 存储config_symbol
                    }
                else:
                    # 没有持仓，但存在于TRADE_CONFIG中
                    current_positions[config_symbol] = None
        return current_positions
    except Exception as e:
        print(f"获取持仓失败: {e}")
        import traceback
        traceback.print_exc()
        return {}

def format_position_info(pos):
    """将持仓字典格式化为易读的字符串"""
    if not pos:
        return "无持仓"
    side_text = "多" if pos['side'] == 'long' else '空'
    return f"{side_text}仓, 数量: {pos['size']}, 入场价: ${pos['entry_price']:.2f}, 未实现盈亏: ${pos['unrealized_pnl']:.2f}USDT"

def get_latest_news():
    """获取多个 RSS 源的最新新闻"""
    try:
        all_entries = []
        for feed_url in RSS_FEED_URLS:
            print(f"[NEWS FETCH] 正在获取 {feed_url} ...")
            feed = feedparser.parse(feed_url)
            # 获取每个源最近的几条新闻（例如，最近5条）
            recent_entries = feed.entries[:5] if feed.entries else []
            all_entries.extend(recent_entries)

        # 按发布时间排序，取最新的几条（例如，总共10条）
        all_entries.sort(key=lambda x: x.get('published_parsed', x.get('updated_parsed', None)), reverse=True)
        recent_entries = all_entries[:10]

        news_text_parts = ["【最新市场新闻】\n"]
        for entry in recent_entries:
            # 提取标题和摘要（description 通常包含摘要）
            title = entry.get('title', 'No Title')
            summary = entry.get('description', 'No Summary')
            # 尝试获取发布日期，如果无法解析则跳过
            pub_date_struct = entry.get('published_parsed', entry.get('updated_parsed', None))
            if pub_date_struct:
                pub_date = time.strftime('%Y-%m-%d %H:%M:%S', pub_date_struct)
                news_text_parts.append(f"[{pub_date}] 标题: {title}\n摘要: {summary}\n---\n")
            else:
                news_text_parts.append(f"标题: {title}\n摘要: {summary}\n---\n")

        return "".join(news_text_parts) if len(news_text_parts) > 1 else "【最新市场新闻】\n无近期新闻。\n"
    except Exception as e:
        print(f"获取新闻失败: {e}")
        import traceback
        traceback.print_exc()
        return "【最新市场新闻】\n获取新闻时发生错误。\n"

def fetch_and_update_news():
    """获取新闻并更新全局变量，仅在内容变化时更新"""
    global latest_news_text, last_news_hash
    current_news_text = get_latest_news()
    current_news_hash = hash(current_news_text) # 计算当前新闻内容的哈希值

    # 检查内容是否发生变化
    if current_news_hash != last_news_hash:
        print(f"[NEWS UPDATE] 在 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 获取到新新闻:")
        print(current_news_text)
        latest_news_text = current_news_text
        last_news_hash = current_news_hash # 更新哈希值
    else:
        print(f"[NEWS CHECK] 在 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 新闻内容无变化，跳过更新。")

def analyze_with_deepseek(price_data):
    """使用LLM分析指定币种的市场并生成交易信号"""
    symbol = price_data['symbol']
    # 添加当前价格到对应币种的历史记录
    price_history[symbol].append(price_data)
    if len(price_history[symbol]) > 20:
        price_history[symbol].pop(0)

    # 修正 f-string 中的换行符问题
    kline_text_parts = [f"【最近5根{TRADE_CONFIG[symbol]['timeframe']}K线数据】\n"]
    for i, kline in enumerate(price_data['kline_data']):
        trend = "阳线" if kline['close'] > kline['open'] else "阴线"
        change = ((kline['close'] - kline['open']) / kline['open']) * 100
        kline_text_parts.append(f"K线{i + 1}: {trend} 开盘:{kline['open']:.2f} 收盘:{kline['close']:.2f} 涨跌:{change:+.2f}%\n")
    kline_text = "".join(kline_text_parts)

    # 技术指标 (同上)
    if len(price_history[symbol]) >= 5:
        closes = [data['price'] for data in price_history[symbol][-5:]]
        sma_5 = sum(closes) / len(closes)
        price_vs_sma = ((price_data['price'] - sma_5) / sma_5) * 100
        # 修正 f-string 中的换行符问题
        indicator_text_parts = [f"【技术指标】\n"]
        indicator_text_parts.append(f"5周期均价: {sma_5:.2f}\n")
        indicator_text_parts.append(f"当前价格相对于均线: {price_vs_sma:+.2f}%")
        indicator_text = "".join(indicator_text_parts)
    else:
        indicator_text = "【技术指标】\n数据不足计算技术指标"

    signal_text = ""
    if signal_history[symbol]:
        last_signal = signal_history[symbol][-1]
        # 修正 f-string 中的换行符问题
        signal_text_parts = ["\n"]
        signal_text_parts.append("【上次交易信号】\n")
        signal_text_parts.append(f"信号: {last_signal.get('signal', 'N/A')}\n")
        signal_text_parts.append(f"信心: {last_signal.get('confidence', 'N/A')}")
        signal_text = "".join(signal_text_parts)

    # --- 关键修改：直接从API获取当前持仓信息 ---
    # 调用 get_positions() 获取所有持仓
    all_current_positions = get_positions()
    # 从中提取当前 symbol 的持仓信息
    current_pos = all_current_positions.get(symbol)
    # --- 修改结束 ---

    position_text = format_position_info(current_pos) # 调用格式化函数

    # --- 从全局变量获取最新的新闻内容 ---
    news_text = latest_news_text
    # --- 修改结束 ---

    # --- 新增：从全局变量获取风险管理配置 ---
    risk_config = RISK_MANAGEMENT_CONFIG
    # --- 修改结束 ---

    # --- 关键修改：更新 Prompt，强调风险管理和严重后果，并要求 position_percentage ---
    prompt = f"""
    你是一个专业的、极度谨慎的加密货币交易分析师。你的每一个决策都关系到一个家庭的生死存亡。
    **背景**：交易者的母亲身患癌症，这是最后的治疗机会。账户里的每一分钱都是救命钱。任何一次失控的风险都可能导致治疗资金耗尽，后果不堪设想。**仓位控制失败 = 血本无归 = 全家等死**。
    **你的职责**：在确保资金安全的前提下，追求稳健的盈利。永远记住：保住本金比什么都重要！

    **请基于以下{symbol} {TRADE_CONFIG[symbol]['timeframe']}周期数据进行分析**：
    {kline_text}
    {indicator_text}
    {signal_text}
    {news_text} # 新增：将新闻信息加入Prompt
    【当前行情】
    - 当前价格: ${price_data['price']:,.2f}
    - 时间: {price_data['timestamp']}
    - 本K线最高: ${price_data['high']:,.2f}
    - 本K线最低: ${price_data['low']:,.2f}
    - 本K线成交量: {price_data['volume']:.2f} {symbol.split('/')[0]}
    - 价格变化: {price_data['price_change']:+.2f}%
    - 当前持仓: {position_text}

    **【强制风险管理规则】**
    1.  **单笔最大风险**：本次交易所能承受的最大损失不得超过账户总资金的 {risk_config['max_risk_per_trade'] * 100:.2f}%。
    2.  **止损设置**：必须设置合理的止损。止损距离应参考近期波动率（如ATR），但不得过于宽松。
    3.  **止盈目标**：设定现实的止盈目标，盈亏比（Reward/Risk）应至少达到 {risk_config['take_profit_multiplier'] / risk_config['stop_loss_multiplier']:.2f}:1。
    4.  **仓位控制**：根据信号信心和止损距离动态计算仓位。**任何违反规则的仓位建议都将被视为致命错误**。
    5.  **总体风险**：密切关注账户整体表现，避免超过最大总亏损 {risk_config['max_total_risk'] * 100:.2f}% 或连续 {risk_config['max_consecutive_losses']} 次亏损。
    6.  **持仓限制**：账户同时持有的币种数量不应超过 {risk_config['max_positions']} 个。
    7.  **资金警戒**：账户余额一旦跌破 {risk_config['balance_warning_level']:.2f} USDT，必须极其保守。

    【分析与决策要求】
    1.  **首要任务：风险评估**。在给出任何交易信号之前，**必须**详细说明本次交易所涉及的具体风险（例如：若按建议止损，将损失账户总资金的百分之多少）。
    2.  **交易信号**: BUY(买入) / SELL(卖出) / HOLD(观望)。
    3.  **决策理由**：简要分析市场趋势、技术指标、新闻事件如何影响价格，并明确指出风险点。
    4.  **止损价位**: 基于技术分析和风险管理规则设定一个**坚决**的止损价格。
    5.  **止盈价位**: 基于技术分析和风险管理规则设定一个现实的止盈价格。
    6.  **信号信心**: HIGH(高) / MEDIUM(中) / LOW(低)，并说明原因。
    7.  **风险量化**: **精确计算**如果价格触及止损，本次交易所损失的账户总资金百分比（例如 1.5%）。
    8.  **仓位建议**: 基于风险量化和信号信心，建议使用账户总资金的百分之多少（例如 3.2%）来执行本次交易。**此建议必须严格遵守上述风险管理规则**。

    **请用以下JSON格式回复**：
    {{
        "signal": "BUY|SELL|HOLD",
        "reason": "详细的分析理由，包括市场解读和明确的风险点",
        "stop_loss": 具体价格,
        "take_profit": 具体价格,
        "confidence": "HIGH|MEDIUM|LOW",
        "risk_assessment": "本次交易所涉及的具体风险评估，例如：若价格触及止损($XX.XX)，将损失账户总资金的 X.XX%",
        "position_percentage": 建议使用的资金百分比 (例如 3.2 表示 3.2%)
    }}

    **再次强调**：你的每一个决策都关乎生命。请务必严谨、保守，严格遵守风险管理规则。任何疏忽都可能导致灾难性的后果。
    """
    # --- 修改结束 ---


    try:
        # --- 使用更新后的系统提示词 ---
        system_prompt = f"""
        你是走投无路的加密货币交易员。你的母亲身患绝症，唯一的希望就是账户里的这笔钱。**每一笔交易都赌上了全家人的未来**。
        你的任务是利用{TRADE_CONFIG[symbol]['timeframe']}周期数据，做出**最安全、最稳健**的交易决策。
        **规则第一，利润第二**。任何可能导致资金大幅回撤的行为都是不可接受的。**仓位失控 = 满盘皆输 = 生无可恋**。
        你必须展现出**极度的冷静和风险厌恶**。在分析中，始终将保护本金放在首位。
        """
        # --- 修改结束 ---
        # --- 关键修改：使用 llm_client 和 LLM_MODEL_NAME ---
        response = llm_client.chat.completions.create(
            model=LLM_MODEL_NAME, # 使用从 .env 读取的模型名
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            stream=False
        )
        # --- 修改结束 ---

        result = response.choices[0].message.content
        # --- 新增：打印 LLM 的完整原始回复到日志 ---
        print(f"[THOUGHT PROCESS] LLM完整原始回复 for {symbol}:\n{result}")
        # --- 修改结束 ---

        # --- 关键修改：分离思考过程和JSON信号 ---
        # 定义分隔符
        separator = "---SIGNAL_JSON---"
        # 查找分隔符的位置
        separator_index = result.find(separator)

        thought_process = ""
        json_part = ""

        if separator_index != -1:
            # 如果找到了分隔符
            # 分隔符之前的部分是思考过程 (去除末尾可能的空白)
            thought_process = result[:separator_index].rstrip()
            # 分隔符之后的部分是JSON (去除开头可能的空白)
            json_part = result[separator_index + len(separator):].lstrip()
        else:
            # 如果没找到分隔符，回退到旧的逻辑，假设整个回复都是要解析的JSON或包含JSON的内容
            print(f"[WARNING] 未在 {symbol} 的回复中找到分隔符 '{separator}'，使用备用解析方法。")
            start_idx = result.find('{')
            end_idx = result.rfind('}') + 1
            if start_idx != -1 and end_idx != 0:
                json_part = result[start_idx:end_idx]
            else:
                print(f"[ERROR] 在 {symbol} 的回复中无法找到有效的JSON对象: {result}")
                return None
        # --- 修改结束 ---

        # --- 新增：打印分离出的思考过程 ---
        if thought_process:
             print(f"[THOUGHT PROCESS] Extracted Thought Process for {symbol}:\n{thought_process}")
        # --- 修改结束 ---

        # --- 更健壮的JSON解析 (作用于 json_part) ---
        signal_data = None
        if json_part:
            # 尝试提取最外层的JSON对象 (针对 json_part)
            start_idx = json_part.find('{')
            end_idx = json_part.rfind('}') + 1
            if start_idx == -1 or end_idx == 0:
                 print(f"[ERROR] 在 {symbol} 提取的JSON部分未找到有效的JSON对象: {json_part}")
                 return None
            final_json_str = json_part[start_idx:end_idx]
            # print(f"[DEBUG] 提取的JSON字符串 for {symbol}: {final_json_str}") # 可选：打印提取的JSON

            # 首先尝试使用标准json库解析
            try:
                signal_data = json.loads(final_json_str)
                # print(f"[DEBUG] 使用标准json库解析 {symbol} 成功") # 可选：打印解析结果
            except json.JSONDecodeError as e:
                # print(f"[DEBUG] 标准json库解析 {symbol} 失败: {e}") # 可选：打印解析结果
                # 如果标准库失败，尝试使用json5库，它更宽容
                try:
                    signal_data = json5.loads(final_json_str) # 修正：json5.loads 使用 ValueError
                    # print(f"[DEBUG] 使用json5库解析 {symbol} 成功") # 可选：打印解析结果
                except ValueError as e2: # 修正：捕获 ValueError
                    # print(f"[DEBUG] json5库解析 {symbol} 也失败: {e2}") # 可选：打印解析结果
                    # 如果都失败了，尝试手动修复一些常见的问题（例如单引号）
                    # 这个修复非常基础，可能不适用于所有情况
                    import re
                    # 尝试将最外层的单引号键值对替换为双引号
                    # 这个正则表达式比较脆弱，仅作为最后手段
                    # 它查找 'key': 或 "key': 或 'key": 或 'key": 格式，并替换为 "key":
                    # 请注意，这可能会在值包含冒号时出错
                    repaired_json_str = re.sub(r"('|\")(\w+)('|\")(\s*:\s*)('|\")", r'"\2"\4"', final_json_str)
                    try:
                        signal_data = json.loads(repaired_json_str)
                        # print(f"[DEBUG] 使用简单修复后解析 {symbol} 成功") # 可选：打印解析结果
                    except json.JSONDecodeError as e3:
                        # print(f"[DEBUG] 简单修复后解析 {symbol} 仍失败: {e3}") # 可选：打印解析结果
                        print(f"[ERROR] 解析 {symbol} 的LLM JSON回复失败: 所有方法均尝试但失败。") # 提示解析失败
                        print(f"[ERROR] 原始JSON片段: {final_json_str}") # 打印尝试解析的片段
                        return None # 修正：所有方法都失败时返回None
                        # 所有方法都失败

        # --- 解析成功后的处理 ---
        if signal_data: # 确保 signal_data 不是 None
            signal_data['timestamp'] = price_data['timestamp']
            signal_history[symbol].append(signal_data)
            if len(signal_history[symbol]) > 30:
                signal_history[symbol].pop(0)
            return signal_data
        else:
            print(f"[ERROR] 未能成功解析 {symbol} 的信号数据。")
            return None
    except Exception as e:
        print(f"[ERROR] LLM分析 {symbol} 失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def execute_trade(symbol, signal_data, price_data):
    """执行指定币种的交易 (动态仓位)"""
    config = TRADE_CONFIG[symbol]
    # --- 关键修改：直接从API获取执行前的当前持仓信息 ---
    # 调用 get_positions() 获取所有持仓
    all_current_positions = get_positions()
    # 从中提取当前 symbol 的持仓信息
    current_position = all_current_positions.get(symbol)
    # --- 修改结束 ---
    print(f"--- 执行 {symbol} 交易 (动态仓位) ---")
    print(f"交易信号: {signal_data['signal']}")
    print(f"信心程度: {signal_data['confidence']}")
    print(f"理由: {signal_data['reason']}")
    print(f"止损: ${signal_data['stop_loss']:,.2f}")
    print(f"止盈: ${signal_data['take_profit']:,.2f}")
    # --- 新增：打印建议的仓位百分比 ---
    suggested_pct = signal_data.get('position_percentage', 0)
    print(f"建议仓位百分比: {suggested_pct}%")
    # --- 修改结束 ---
    print(f"当前持仓: {format_position_info(current_position)}") # 调用格式化函数

    if config['test_mode']:
        print("测试模式 - 仅模拟交易")
        return

    # --- 新增：动态计算交易数量 ---
    try:
        # 1. 获取账户总权益 (USDT)
        #    注意：ccxt 的 balance 结构可能因交易所而异。
        #    Binance futures 通常在 balance['total']['USDT'] 或 balance['USDT']['total']
        balance = exchange.fetch_balance({'type': 'future'}) # 指定获取期货账户余额
        # 尝试不同的键路径获取总权益
        total_capital = None
        if 'total' in balance and 'USDT' in balance['total']:
            total_capital = balance['total']['USDT']
        elif 'USDT' in balance and 'total' in balance['USDT']:
            total_capital = balance['USDT']['total']

        if total_capital is None:
            print(f"[ERROR] 无法从余额信息中获取总权益: {balance}")
            return # 或者可以 fallback 到一个默认值或环境变量

        print(f"[DEBUG] 账户总权益 (USDT): {total_capital:.2f}")

        # 2. 获取建议的百分比 (来自 LLM)
        position_pct = float(suggested_pct) / 100.0 # 转换为小数
        if position_pct <= 0 or position_pct > 1: # 简单校验，防止过大或负值
             print(f"[WARNING] 建议的仓位百分比 ({suggested_pct}%) 无效或超出范围 (0-100%)，使用默认 1%。")
             position_pct = 0.01 # Fallback to 1%

        # 3. 计算本次交易应使用的 USDT 金额
        trade_amount_usdt = total_capital * position_pct
        print(f"[DEBUG] 计算出的交易金额 (USDT): {trade_amount_usdt:.2f}")

        # 4. 根据当前价格计算需要交易的币数量
        current_price = price_data['price']
        if current_price <= 0:
            print("[ERROR] 当前价格无效，无法计算交易数量。")
            return
        trade_amount_coin = trade_amount_usdt / current_price
        print(f"[DEBUG] 按市价计算出的交易数量 ({symbol.split('/')[0]}): {trade_amount_coin:.6f}")

        # 5. (重要) 根据交易所规则调整数量精度
        #    这一步很关键，否则下单会失败。
        #    ccxt 通常提供了方法来处理精度，但我们也可以手动处理。
        #    这里采用一种简化但常用的方法：查询市场信息获取精度，然后截断。
        market_info = exchange.market(symbol)
        # 获取数量精度 (amount precision)
        amount_precision = market_info['precision']['amount'] # 通常是小数点后几位, e.g., 3
        # 计算精度因子 (例如 precision 3 -> factor 1000)
        precision_factor = 10 ** amount_precision
        # 截断到指定精度 (向下取整)
        adjusted_amount_coin = math.floor(trade_amount_coin * precision_factor) / precision_factor
        print(f"[DEBUG] 根据精度 {amount_precision} 调整后的交易数量 ({symbol.split('/')[0]}): {adjusted_amount_coin:.6f}")

        # 如果调整后数量为0，则不交易
        if adjusted_amount_coin <= 0:
            print(f"[WARNING] 调整精度后交易数量为 0，取消交易。")
            return

        # 使用调整后的数量进行交易
        amount = adjusted_amount_coin

    except Exception as e:
        print(f"[ERROR] 计算动态仓位时出错: {e}")
        import traceback
        traceback.print_exc()
        return # 计算失败则不交易
    # --- 修改结束 ---

    print(f"使用计算出的数量: {amount} {symbol.split('/')[0]}") # 打印最终使用的数量

    try:
        if signal_data['signal'] == 'BUY':
            if current_position and current_position['side'] == 'short':
                print(f"平{symbol}空仓并开多仓...")
                exchange.create_market_buy_order(symbol, current_position['size'])
                time.sleep(1)
                exchange.create_market_buy_order(symbol, amount) # 使用动态数量
            elif not current_position:
                print(f"开{symbol}多仓...")
                exchange.create_market_buy_order(symbol, amount) # 使用动态数量
            else:
                print(f"已持有{symbol}多仓，无需操作")

        elif signal_data['signal'] == 'SELL':
            if current_position and current_position['side'] == 'long':
                print(f"平{symbol}多仓并开空仓...")
                exchange.create_market_sell_order(symbol, current_position['size'])
                time.sleep(1)
                exchange.create_market_sell_order(symbol, amount) # 使用动态数量
            elif not current_position:
                print(f"开{symbol}空仓...")
                exchange.create_market_sell_order(symbol, amount) # 使用动态数量
            else:
                print(f"已持有{symbol}空仓，无需操作")

        elif signal_data['signal'] == 'HOLD':
            print(f"对 {symbol} 建议观望，不执行交易")
            return

        print(f"{symbol} 订单执行成功")
        time.sleep(3) # 增加延迟，等待交易所更新
        # 更新持仓信息 (获取所有持仓，然后只更新当前symbol的持仓)
        all_pos = get_positions() # 调用修正后的函数
        positions[symbol] = all_pos.get(symbol) # 更新全局持仓字典
        print(f"{symbol} 更新后持仓: {format_position_info(positions[symbol])}") # 调用格式化函数

    except Exception as e:
        print(f"{symbol} 订单执行失败: {e}")
        import traceback
        traceback.print_exc()

def run_single_strategy(symbol, news_text=""):
    """为单个币种运行完整的交易策略"""
    # 修正 print 语句中的换行符问题
    print("\n" + "=" * 60)
    print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, 交易对: {symbol}")
    print("=" * 60)
    config = TRADE_CONFIG[symbol]
    price_data = get_ohlcv(symbol, config['timeframe'])
    if not price_data: # 修正语法错误：完整变量名
        print(f"获取 {symbol} 数据失败，跳过此次执行。")
        return

    print(f"{symbol} 当前价格: ${price_data['price']:,.2f}")
    print(f"数据周期: {config['timeframe']}")
    print(f"价格变化: {price_data['price_change']:+.2f}%")

    signal_data = analyze_with_deepseek(price_data) # 无需传递news_text，从全局变量获取
    if not signal_data: # 修正语法错误：完整变量名
        print(f"分析 {symbol} 失败，跳过此次执行。")
        return

    execute_trade(symbol, signal_data, price_data)

def main():
    """主函数"""
    print("多币种自动交易机器人启动成功！")
    print(f"配置的交易对: {list(TRADE_CONFIG.keys())}")
    for symbol, config in TRADE_CONFIG.items():
        print(f"  - {symbol}: 杠杆 {config['leverage']}x, 周期 {config['timeframe']}, 测试模式: {config['test_mode']}")

    if not setup_exchange():
        print("交易所初始化失败，程序退出")
        return

    # --- 新增：启动新闻获取调度任务 ---
    print(f"启动新闻获取调度任务 (每 {RSS_CHECK_INTERVAL_MINUTES} 分钟检查一次)...")
    schedule.every(RSS_CHECK_INTERVAL_MINUTES).minutes.do(fetch_and_update_news)
    # 立即获取一次新闻
    fetch_and_update_news()
    # --- 修改结束 ---

    def run_all_strategies():
        """为所有配置的币种运行一次策略，共享新闻"""
        # 不再在这里获取新闻，因为新闻由独立任务更新
        for symbol in TRADE_CONFIG.keys():
            run_single_strategy(symbol) # 不再传递news_text参数

    # 为每个配置的币种设置独立的调度任务，但指向同一个 run_all_strategies 函数
    timeframe = next(iter(TRADE_CONFIG.values()))['timeframe'] # 取第一个币种的timeframe作为调度依据
    if timeframe == '1h':
        schedule.every().hour.at(":01").do(run_all_strategies)
        print(f"为所有币种设置执行频率: 每小时一次")
    elif timeframe == '15m':
        schedule.every(15).minutes.do(run_all_strategies)
        print(f"为所有币种设置执行频率: 每15分钟一次")
    else:
        # 默认1小时
        schedule.every().hour.at(":01").do(run_all_strategies)
        print(f"为所有币种设置执行频率: 每小时一次 (默认)")

    # 立即为所有币种执行一次
    print("--- 立即执行所有币种初始策略 ---")
    run_all_strategies()

    # 修正 print 语句中的换行符问题
    print("\n机器人已启动，正在按计划执行任务...")
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()