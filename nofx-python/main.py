"""
Nofx Python Trading Bot
基于BTC-Range-Ladder策略的Hyperliquid交易机器人
"""
import time
import sys
from src.config import Config
from src.logger import setup_logger, get_logger
from src.hyperliquid_client import HyperliquidClient
from src.strategy import BTCRangeLadderStrategy
from src.executor import TradeExecutor
from src.market_data import MarketDataManager


def main():
    """主程序"""
    # 加载配置
    try:
        config = Config("config.json")
    except FileNotFoundError:
        print("❌ 配置文件不存在，请复制config.json.example并修改")
        sys.exit(1)
    
    # 初始化日志
    setup_logger(
        level=config.get("logging.level", "INFO"),
        log_to_file=config.get("logging.log_to_file", True),
        log_dir=config.get("logging.log_dir", "logs")
    )
    logger = get_logger()
    
    logger.info("=" * 80)
    logger.info("🚀 Nofx Python Trading Bot 启动")
    logger.info("=" * 80)
    
    # 验证配置
    agent_key = config.get("hyperliquid.agent_private_key")
    main_wallet = config.get("hyperliquid.main_wallet_address")
    
    if not agent_key or not main_wallet:
        logger.error("❌ 配置错误: 请在config.json中填写agent_private_key和main_wallet_address")
        logger.error("   参考: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/nonces-and-api-wallets")
        sys.exit(1)
    
    # 初始化组件
    try:
        # Hyperliquid客户端
        client = HyperliquidClient(
            agent_private_key=agent_key,
            main_wallet_address=main_wallet,
            testnet=config.get("hyperliquid.testnet", False)
        )
        
        # 交易币种
        coin = config.get("trading.symbol", "BTC")
        
        # 策略
        max_trades = config.get("trading.max_trades_per_hour", 0)
        strategy = BTCRangeLadderStrategy(
            min_expected_value=config.get("trading.min_expected_value", 1.5),
            min_risk_reward_ratio=config.get("trading.min_risk_reward_ratio", 3.0),
            max_trades_per_hour=max_trades,
            min_holding_minutes=config.get("trading.min_holding_minutes", 30)
        )
        
        # 执行器
        executor = TradeExecutor(client, coin)
        
        # 市场数据管理器
        market_data_mgr = MarketDataManager(coin)
        
        # 杠杆配置
        leverage = config.get(f"hyperliquid.leverage.{coin}", 
                             config.get("hyperliquid.leverage.default", 10))
        
        logger.info(f"✓ 交易币种: {coin}")
        logger.info(f"✓ 杠杆倍数: {leverage}x")
        logger.info(f"✓ 最小期望值: {strategy.min_expected_value}")
        logger.info(f"✓ 最小风险回报比: {strategy.min_risk_reward_ratio}:1")
        if max_trades > 0:
            logger.info(f"✓ 交易频率限制: 每小时最多{max_trades}次")
        else:
            logger.info(f"✓ 交易频率限制: 无限制")
        
    except Exception as e:
        logger.error(f"❌ 初始化失败: {e}")
        sys.exit(1)
    
    # 主循环
    logger.info("=" * 80)
    logger.info("🔄 开始交易循环...")
    logger.info("=" * 80)
    
    iteration = 0
    
    while True:
        try:
            iteration += 1
            logger.info(f"\n{'=' * 80}")
            logger.info(f"⏰ 第 {iteration} 次循环")
            logger.info(f"{'=' * 80}")
            
            # 1. 获取账户信息
            balance = executor.get_balance()
            positions = executor.get_positions()
            
            if balance["available"] <= 0:
                logger.warning("⚠️ 可用余额不足，跳过本次循环")
                time.sleep(60)
                continue
            
            # 2. 获取市场数据
            market_data = market_data_mgr.get_market_data()
            if not market_data:
                logger.warning("⚠️ 市场数据获取失败，跳过本次循环")
                time.sleep(60)
                continue
            
            # 3. 获取当前价格
            current_price = executor.get_market_price()
            if not current_price:
                logger.warning("⚠️ 价格获取失败，跳过本次循环")
                time.sleep(60)
                continue
            
            # 4. 生成交易信号
            signal = strategy.generate_signal(
                current_price=current_price,
                price_4h=market_data["price_4h"],
                price_1h=market_data["price_1h"],
                price_15m=market_data["price_15m"],
                ema20_4h=market_data["ema20_4h"],
                ema50_4h=market_data["ema50_4h"],
                available_balance=balance["available"],
                leverage=leverage,
                current_positions=positions
            )
            
            # 5. 执行信号
            if signal:
                success = executor.execute_signal(signal, leverage)
                if success:
                    logger.info("✅ 交易执行成功")
                    # 记录到策略历史
                    strategy.trade_history.append({
                        "timestamp": time.time(),
                        "action": signal.action,
                        "price": signal.entry_price,
                        "size": signal.position_size_usd
                    })
                    strategy.last_trade_time = time.time()
                else:
                    logger.error("❌ 交易执行失败")
            else:
                logger.info("⏸️ 当前无交易信号")
            
            # 6. 等待下一次循环
            sleep_seconds = 180  # 3分钟
            logger.info(f"😴 等待 {sleep_seconds} 秒...")
            time.sleep(sleep_seconds)
            
        except KeyboardInterrupt:
            logger.info("\n⏹️ 用户中断，退出程序")
            break
        except Exception as e:
            logger.error(f"❌ 循环出错: {e}", exc_info=True)
            logger.info("⏸️ 等待60秒后继续...")
            time.sleep(60)
    
    logger.info("=" * 80)
    logger.info("👋 Nofx Python Trading Bot 已停止")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
