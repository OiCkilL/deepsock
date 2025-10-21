import os
import time
import schedule
from openai import OpenAI
import ccxt
import pandas as pd
from datetime import datetime
import json
import json5 # 用于解析可能非标准的JSON
from dotenv import load_dotenv
load_dotenv()
# --- 初始化 ---
deepseek_client = OpenAI(
    api_key=os.getenv('DEEPSEEK_API_KEY'),
    base_url="https://api.deepseek.com"
)
exchange = ccxt.binance({
    'options': {'defaultType': 'future'},
    'apiKey': os.getenv('BINANCE_API_KEY'),
    'secret': os.getenv('BINANCE_SECRET'),
})

# --- 从 .env 读取多币种配置 ---
def parse_symbols_and_leverage(env_string):
    """解析环境变量字符串，返回配置字典"""
    config = {}
    if not env_string:
        raise ValueError("SYMBOLS_AND_LEVERAGE 环境变量未设置或为空")
    pairs = env_string.split(',')
    for pair in pairs:
        parts = pair.strip().split(':')
        if len(parts) != 2:
            raise ValueError(f"SYMBOLS_AND_LEVERAGE 格式错误: {pair}")
        symbol, leverage_str = parts
        try:
            leverage = int(leverage_str)
        except ValueError:
            raise ValueError(f"杠杆值必须为整数: {leverage_str}")
        # 从env读取测试模式设置
        test_mode_str = os.getenv('DEFAULT_TEST_MODE', 'False').lower()
        test_mode = test_mode_str in ['true', '1', 'yes', 'on']
        config[symbol] = {
            'symbol': symbol,
            'leverage': leverage,
            'timeframe': os.getenv('DEFAULT_TIMEFRAME', '15m'), # 从env读取默认周期
            'amount': float(os.getenv('DEFAULT_AMOUNT', 0.001)), # 从env读取默认数量，并转换为float
            'test_mode': test_mode, # 从env读取测试模式
        }
    return config

TRADE_CONFIG = parse_symbols_and_leverage(os.getenv('SYMBOLS_AND_LEVERAGE'))

# --- 全局变量 (改为字典以支持多币种) ---
price_history = {symbol: [] for symbol in TRADE_CONFIG.keys()}
signal_history = {symbol: [] for symbol in TRADE_CONFIG.keys()}
positions = {symbol: None for symbol in TRADE_CONFIG.keys()}

# --- 核心函数 ---
def setup_exchange():
    """设置交易所参数，为所有配置的币种设置杠杆"""
    try:
        balance = exchange.fetch_balance()
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
    """获取所有持仓情况"""
    try:
        # 获取所有持仓
        all_positions = exchange.fetch_positions()
        current_positions = {}
        for pos in all_positions:
            symbol = pos['symbol']
            # 只处理我们关心的币种
            if symbol in TRADE_CONFIG:
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
                    current_positions[symbol] = {
                        'side': side,
                        'size': abs(position_amt),
                        'entry_price': float(pos.get('entryPrice', 0)),
                        'unrealized_pnl': float(pos.get('unrealizedPnl', 0)),
                        'position_amt': position_amt,
                        'symbol': pos['symbol']
                    }
                else:
                    # 确保没有持仓的币种在字典中被标记为 None
                    current_positions[symbol] = None
        return current_positions
    except Exception as e:
        print(f"获取持仓失败: {e}")
        import traceback
        traceback.print_exc()
        return {}

def analyze_with_deepseek(price_data):
    """使用DeepSeek分析指定币种的市场并生成交易信号"""
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

    # 获取当前持仓信息
    current_pos = positions.get(symbol)
    position_text = "无持仓" if not current_pos else f"{current_pos['side']}仓, 数量: {current_pos['size']}, 盈亏: {current_pos['unrealized_pnl']:.2f}USDT"

    prompt = f"""
    你是一个专业的加密货币交易分析师。请基于以下{symbol} {TRADE_CONFIG[symbol]['timeframe']}周期数据进行分析：
    {kline_text}
    {indicator_text}
    {signal_text}
    【当前行情】
    - 当前价格: ${price_data['price']:,.2f}
    - 时间: {price_data['timestamp']}
    - 本K线最高: ${price_data['high']:,.2f}
    - 本K线最低: ${price_data['low']:,.2f}
    - 本K线成交量: {price_data['volume']:.2f} {symbol.split('/')[0]}
    - 价格变化: {price_data['price_change']:+.2f}%
    - 当前持仓: {position_text}
    【分析要求】
    1. 基于{TRADE_CONFIG[symbol]['timeframe']}K线趋势和技术指标给出交易信号: BUY(买入) / SELL(卖出) / HOLD(观望)
    2. 简要分析理由（考虑趋势连续性、支撑阻力、成交量等因素）
    3. 基于技术分析建议合理的止损价位
    4. 基于技术分析建议合理的止盈价位
    5. 评估信号信心程度
    请用以下JSON格式回复：
    {{
        "signal": "BUY|SELL|HOLD",
        "reason": "分析理由",
        "stop_loss": 具体价格,
        "take_profit": 具体价格,
        "confidence": "HIGH|MEDIUM|LOW"
    }}
    """

    try:
        # --- 使用更新后的系统提示词 ---
        system_prompt = f"您是一位走投无路的交易员，您的母亲身患癌症，病情危急，医生说这是最后的治疗机会。您仅有的积蓄和全部希望都投入到这个账户中，必须在短时间内通过{TRADE_CONFIG[symbol]['timeframe']}周期的交易赚取足够的救命钱。请全力以赴，结合K线形态和技术指标做出最精准的判断。"
        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            stream=False
        )

        result = response.choices[0].message.content
        # print(f"[DEBUG] DeepSeek原始回复 for {symbol}: {result}") # 调试：打印原始回复 - 已注释
        # --- 更健壮的JSON解析 ---
        # 尝试提取最外层的JSON对象
        start_idx = result.find('{')
        end_idx = result.rfind('}') + 1
        if start_idx == -1 or end_idx == 0:
             print(f"在 {symbol} 的回复中未找到有效的JSON对象: {result}")
             return None
        json_str = result[start_idx:end_idx]
        # print(f"[DEBUG] 提取的JSON字符串 for {symbol}: {json_str}") # 调试：打印提取的JSON - 已注释
        signal_data = None
        # 首先尝试使用标准json库解析
        try:
            signal_data = json.loads(json_str)
            # print(f"[DEBUG] 使用标准json库解析 {symbol} 成功") # 调试：打印解析结果 - 已注释
        except json.JSONDecodeError as e:
            # print(f"[DEBUG] 标准json库解析 {symbol} 失败: {e}") # 调试：打印解析结果 - 已注释
            # 如果标准库失败，尝试使用json5库，它更宽容
            try:
                signal_data = json5.loads(json_str)
                # print(f"[DEBUG] 使用json5库解析 {symbol} 成功") # 调试：打印解析结果 - 已注释
            except json5.JSON5Exception as e2:
                # print(f"[DEBUG] json5库解析 {symbol} 也失败: {e2}") # 调试：打印解析结果 - 已注释
                # 如果都失败了，尝试手动修复一些常见的问题（例如单引号）
                # 这个修复非常基础，可能不适用于所有情况
                import re
                # 尝试将最外层的单引号键值对替换为双引号
                # 这个正则表达式比较脆弱，仅作为最后手段
                # 它查找 'key': 或 "key': 或 'key": 或 'key": 格式，并替换为 "key":
                # 请注意，这可能会在值包含冒号时出错
                repaired_json_str = re.sub(r"('|\")(\w+)('|\")(\s*:\s*)('|\")", r'"\2"\4"', json_str)
                try:
                    signal_data = json.loads(repaired_json_str)
                    # print(f"[DEBUG] 使用简单修复后解析 {symbol} 成功") # 调试：打印解析结果 - 已注释
                except json.JSONDecodeError as e3:
                    # print(f"[DEBUG] 简单修复后解析 {symbol} 仍失败: {e3}") # 调试：打印解析结果 - 已注释
                    print(f"解析 {symbol} 的DeepSeek回复失败: 所有方法均尝试但失败。") # 提示解析失败
                    return None # 所有方法都失败

        # --- 解析成功后的处理 ---
        signal_data['timestamp'] = price_data['timestamp']
        signal_history[symbol].append(signal_data)
        if len(signal_history[symbol]) > 30:
            signal_history[symbol].pop(0)

        return signal_data
    except Exception as e:
        print(f"DeepSeek分析 {symbol} 失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def execute_trade(symbol, signal_data, price_data):
    """执行指定币种的交易"""
    config = TRADE_CONFIG[symbol]
    current_position = positions.get(symbol)
    print(f"--- 执行 {symbol} 交易 ---")
    print(f"交易信号: {signal_data['signal']}")
    print(f"信心程度: {signal_data['confidence']}")
    print(f"理由: {signal_data['reason']}")
    print(f"止损: ${signal_data['stop_loss']:,.2f}")
    print(f"止盈: ${signal_data['take_profit']:,.2f}")
    print(f"当前持仓: {current_position}")

    if config['test_mode']:
        print("测试模式 - 仅模拟交易")
        return

    try:
        if signal_data['signal'] == 'BUY':
            if current_position and current_position['side'] == 'short':
                print(f"平{symbol}空仓并开多仓...")
                exchange.create_market_buy_order(symbol, current_position['size'])
                time.sleep(1)
                exchange.create_market_buy_order(symbol, config['amount'])
            elif not current_position:
                print(f"开{symbol}多仓...")
                exchange.create_market_buy_order(symbol, config['amount'])
            else:
                print(f"已持有{symbol}多仓，无需操作")

        elif signal_data['signal'] == 'SELL':
            if current_position and current_position['side'] == 'long':
                print(f"平{symbol}多仓并开空仓...")
                exchange.create_market_sell_order(symbol, current_position['size'])
                time.sleep(1)
                exchange.create_market_sell_order(symbol, config['amount'])
            elif not current_position:
                print(f"开{symbol}空仓...")
                exchange.create_market_sell_order(symbol, config['amount'])
            else:
                print(f"已持有{symbol}空仓，无需操作")

        elif signal_data['signal'] == 'HOLD':
            print(f"对 {symbol} 建议观望，不执行交易")
            return

        print(f"{symbol} 订单执行成功")
        time.sleep(2) # 等待交易所更新
        # 更新持仓信息 (获取所有持仓，然后只更新当前symbol的持仓)
        all_pos = get_positions()
        positions[symbol] = all_pos.get(symbol)
        print(f"{symbol} 更新后持仓: {positions[symbol]}")

    except Exception as e:
        print(f"{symbol} 订单执行失败: {e}")
        import traceback
        traceback.print_exc()

def run_single_strategy(symbol):
    """为单个币种运行完整的交易策略"""
    # 修正 print 语句中的换行符问题
    print("\n" + "=" * 60)
    print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, 交易对: {symbol}")
    print("=" * 60)
    config = TRADE_CONFIG[symbol]
    price_data = get_ohlcv(symbol, config['timeframe'])
    if not price_data: # 修正语法错误
        print(f"获取 {symbol} 数据失败，跳过此次执行。")
        return

    print(f"{symbol} 当前价格: ${price_data['price']:,.2f}")
    print(f"数据周期: {config['timeframe']}")
    print(f"价格变化: {price_data['price_change']:+.2f}%")

    signal_data = analyze_with_deepseek(price_data)
    if not signal_data: # 修正语法错误
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

    # 为每个配置的币种设置独立的调度任务
    for symbol, config in TRADE_CONFIG.items():
        timeframe = config['timeframe']
        if timeframe == '1h':
            schedule.every().hour.at(":01").do(run_single_strategy, symbol)
            print(f"为 {symbol} 设置执行频率: 每小时一次")
        elif timeframe == '15m':
            schedule.every(15).minutes.do(run_single_strategy, symbol)
            print(f"为 {symbol} 设置执行频率: 每15分钟一次")
        else:
            # 默认1小时
            schedule.every().hour.at(":01").do(run_single_strategy, symbol)
            print(f"为 {symbol} 设置执行频率: 每小时一次 (默认)")

    # 立即为每个币种执行一次
    for symbol in TRADE_CONFIG.keys():
        print(f"--- 立即执行 {symbol} 初始策略 ---")
        run_single_strategy(symbol)

    # 修正 print 语句中的换行符问题
    print("\n机器人已启动，正在按计划执行任务...")
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
