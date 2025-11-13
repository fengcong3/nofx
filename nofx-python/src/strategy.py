"""
BTC区间梯形策略
基于 prompts/BTC-Range-Ladder.txt
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import time
from src.logger import get_logger


class Direction(Enum):
    """市场方向"""
    BULLISH = "bullish"  # 偏多
    BEARISH = "bearish"  # 偏空
    RANGING = "ranging"  # 震荡


class PositionSide(Enum):
    """持仓方向"""
    LONG = "long"
    SHORT = "short"


@dataclass
class Range:
    """震荡区间"""
    support: float  # 支撑位
    resistance: float  # 阻力位
    amplitude: float  # 波动幅度(%)
    
    def get_position_percentage(self, price: float) -> float:
        """计算价格在区间中的位置百分比"""
        if self.resistance == self.support:
            return 50.0
        return (price - self.support) / (self.resistance - self.support) * 100


@dataclass
class TradeSignal:
    """交易信号"""
    action: str  # "open_long", "open_short", "close_long", "close_short", "hold"
    entry_price: float
    stop_loss: float
    take_profit_1: float  # 30%仓位
    take_profit_2: float  # 30%仓位
    take_profit_3: float  # 40%仓位
    position_size_usd: float
    expected_value: float
    risk_reward_ratio: float
    reason: str


class BTCRangeLadderStrategy:
    """BTC区间梯形交易策略"""
    
    def __init__(self,
                 min_expected_value: float = 1.5,
                 min_risk_reward_ratio: float = 3.0,
                 max_trades_per_hour: int = 1,
                 min_holding_minutes: int = 30):
        """
        初始化策略
        
        Args:
            min_expected_value: 最小期望值
            min_risk_reward_ratio: 最小风险回报比
            max_trades_per_hour: 每小时最大交易次数
            min_holding_minutes: 最小持仓时间(分钟)
        """
        self.logger = get_logger()
        self.min_expected_value = min_expected_value
        self.min_risk_reward_ratio = min_risk_reward_ratio
        self.max_trades_per_hour = max_trades_per_hour
        self.min_holding_minutes = min_holding_minutes
        
        # 交易记录
        self.trade_history: List[Dict] = []
        self.last_trade_time: float = 0
        self.current_direction: Optional[Direction] = None
        self.direction_change_time: float = 0
    
    def analyze_market_direction(self,
                                 price_4h: List[float],
                                 ema20_4h: List[float],
                                 ema50_4h: List[float]) -> Direction:
        """
        分析市场大方向
        
        Args:
            price_4h: 4小时价格序列
            ema20_4h: 4小时EMA20
            ema50_4h: 4小时EMA50
            
        Returns:
            市场方向
        """
        if not price_4h or not ema20_4h or not ema50_4h:
            return Direction.RANGING
        
        current_price = price_4h[-1]
        current_ema20 = ema20_4h[-1]
        current_ema50 = ema50_4h[-1]
        
        bullish_count = 0
        bearish_count = 0
        
        # 条件1: 价格与EMA关系
        if current_price > current_ema20 and current_ema20 > current_ema50:
            bullish_count += 1
        elif current_price < current_ema20 and current_ema20 < current_ema50:
            bearish_count += 1
        
        # 条件2: 高点/低点趋势（简化版，检查最近3天）
        recent_prices = price_4h[-18:]  # 最近3天的4小时数据
        if len(recent_prices) >= 18:
            highs = [max(recent_prices[i:i+6]) for i in range(0, 12, 6)]
            if len(highs) >= 2 and all(highs[i] < highs[i+1] for i in range(len(highs)-1)):
                bullish_count += 1
            
            lows = [min(recent_prices[i:i+6]) for i in range(0, 12, 6)]
            if len(lows) >= 2 and all(lows[i] > lows[i+1] for i in range(len(lows)-1)):
                bearish_count += 1
        
        # 判断方向
        if bullish_count >= 2:
            direction = Direction.BULLISH
        elif bearish_count >= 2:
            direction = Direction.BEARISH
        else:
            direction = Direction.RANGING
        
        self.logger.info(f"📊 市场方向分析: {direction.value} (多:{bullish_count}, 空:{bearish_count})")
        return direction
    
    def identify_range(self,
                      prices: List[float],
                      timeframe: str) -> Optional[Range]:
        """
        识别震荡区间
        
        Args:
            prices: 价格序列
            timeframe: 时间周期
            
        Returns:
            震荡区间对象
        """
        if not prices or len(prices) < 10:
            return None
        
        support = min(prices)
        resistance = max(prices)
        amplitude = (resistance - support) / support * 100
        
        # 最小波动幅度要求
        min_amplitude = {
            "4h": 2.0,
            "1h": 1.5,
            "15m": 1.0
        }.get(timeframe, 1.0)
        
        if amplitude < min_amplitude:
            self.logger.debug(f"  {timeframe} 区间幅度不足: {amplitude:.2f}% < {min_amplitude}%")
            return None
        
        range_obj = Range(support, resistance, amplitude)
        self.logger.info(f"  ✓ {timeframe} 区间: {support:.2f} - {resistance:.2f} (幅度: {amplitude:.2f}%)")
        return range_obj
    
    def calculate_expected_value(self,
                                profit_probability: float,
                                profit_amount: float,
                                loss_amount: float) -> float:
        """
        计算期望值
        
        Args:
            profit_probability: 盈利概率
            profit_amount: 盈利金额
            loss_amount: 亏损金额
            
        Returns:
            期望值
        """
        if loss_amount == 0:
            return 0
        return (profit_probability * profit_amount) / loss_amount
    
    def check_trade_frequency(self) -> bool:
        """
        检查交易频率限制
        
        Returns:
            是否允许交易
        """
        # 如果设置为0，表示不限制交易频率
        if self.max_trades_per_hour == 0:
            return True
        
        current_time = time.time()
        one_hour_ago = current_time - 3600
        
        # 统计过去1小时内的交易次数
        recent_trades = [t for t in self.trade_history 
                        if t.get('timestamp', 0) > one_hour_ago]
        
        if len(recent_trades) >= self.max_trades_per_hour:
            self.logger.warning(f"⚠️ 交易频率限制: 过去1小时已交易{len(recent_trades)}次（限制={self.max_trades_per_hour}）")
            return False
        
        return True
    
    def generate_signal(self,
                       current_price: float,
                       price_4h: List[float],
                       price_1h: List[float],
                       price_15m: List[float],
                       ema20_4h: List[float],
                       ema50_4h: List[float],
                       available_balance: float,
                       leverage: int,
                       current_positions: List[Dict]) -> Optional[TradeSignal]:
        """
        生成交易信号
        
        Args:
            current_price: 当前价格
            price_4h: 4小时价格序列
            price_1h: 1小时价格序列
            price_15m: 15分钟价格序列
            ema20_4h: 4小时EMA20
            ema50_4h: 4小时EMA50
            available_balance: 可用余额
            leverage: 杠杆倍数
            current_positions: 当前持仓
            
        Returns:
            交易信号或None
        """
        self.logger.info("=" * 80)
        self.logger.info("🔍 开始策略分析...")
        
        # 步骤1: 检查交易频率
        if not self.check_trade_frequency():
            return None
        
        # 步骤2: 分析市场方向
        direction = self.analyze_market_direction(price_4h, ema20_4h, ema50_4h)
        
        # 步骤3: 识别多周期震荡区间
        range_4h = self.identify_range(price_4h, "4h")
        range_1h = self.identify_range(price_1h, "1h")
        range_15m = self.identify_range(price_15m, "15m")
        
        if not range_1h:
            self.logger.info("❌ 未识别到有效的1小时震荡区间")
            return None
        
        # 步骤4: 评估当前位置
        pos_1h = range_1h.get_position_percentage(current_price)
        self.logger.info(f"📍 当前价格在1小时区间的位置: {pos_1h:.1f}%")
        
        # 步骤5: 判断开仓机会
        signal = None
        
        # 做多机会
        if direction in [Direction.BULLISH, Direction.RANGING] and pos_1h <= 40:
            # 精确入场: 参考15分钟线最低点
            if price_15m:
                min_15m = min(price_15m)
                ideal_entry = min_15m * 1.003  # 最低点上方0.3%
                
                if current_price <= ideal_entry:
                    self.logger.info(f"✅ 做多机会: 当前价格({current_price:.2f}) <= 理想入场价({ideal_entry:.2f})")
                    signal = self._create_long_signal(
                        current_price, range_1h, available_balance, 
                        leverage, direction, pos_1h
                    )
                else:
                    self.logger.info(f"⏳ 等待价格回落: 当前{current_price:.2f} > 理想{ideal_entry:.2f}")
        
        # 做空机会
        elif direction in [Direction.BEARISH, Direction.RANGING] and pos_1h >= 60:
            # 精确入场: 参考15分钟线最高点
            if price_15m:
                max_15m = max(price_15m)
                ideal_entry = max_15m * 0.997  # 最高点下方0.3%
                
                if current_price >= ideal_entry:
                    self.logger.info(f"✅ 做空机会: 当前价格({current_price:.2f}) >= 理想入场价({ideal_entry:.2f})")
                    signal = self._create_short_signal(
                        current_price, range_1h, available_balance,
                        leverage, direction, pos_1h
                    )
                else:
                    self.logger.info(f"⏳ 等待价格反弹: 当前{current_price:.2f} < 理想{ideal_entry:.2f}")
        else:
            self.logger.info(f"❌ 不满足开仓条件 (方向:{direction.value}, 位置:{pos_1h:.1f}%)")
        
        return signal
    
    def _create_long_signal(self,
                           entry_price: float,
                           range_1h: Range,
                           available_balance: float,
                           leverage: int,
                           direction: Direction,
                           position_pct: float) -> Optional[TradeSignal]:
        """创建做多信号"""
        # 计算止损价（清算价+2%）
        liquidation_price = entry_price * (1 - 1/leverage)
        stop_loss = liquidation_price * 1.02
        
        # 计算阶梯止盈
        tp1 = entry_price + 800
        tp2 = entry_price + 1500
        tp3 = range_1h.resistance - 500
        
        # 计算期望值
        profit_amount = tp1 - entry_price
        loss_amount = entry_price - stop_loss
        profit_probability = 0.7  # 简化，实际应根据多周期共振等因素计算
        
        expected_value = self.calculate_expected_value(
            profit_probability, profit_amount, loss_amount
        )
        risk_reward_ratio = profit_amount / loss_amount if loss_amount > 0 else 0
        
        self.logger.info(f"  期望值: {expected_value:.2f} (要求≥{self.min_expected_value})")
        self.logger.info(f"  风险回报比: {risk_reward_ratio:.2f}:1 (要求≥{self.min_risk_reward_ratio}:1)")
        
        # 验证条件
        if expected_value < self.min_expected_value:
            self.logger.warning("❌ 期望值不足")
            return None
        
        if risk_reward_ratio < self.min_risk_reward_ratio:
            self.logger.warning("❌ 风险回报比不足")
            return None
        
        # 计算仓位大小
        margin = available_balance * 0.10  # 10%基数
        position_size_usd = margin * leverage
        
        self.logger.info("✅ 生成做多信号")
        
        return TradeSignal(
            action="open_long",
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit_1=tp1,
            take_profit_2=tp2,
            take_profit_3=tp3,
            position_size_usd=position_size_usd,
            expected_value=expected_value,
            risk_reward_ratio=risk_reward_ratio,
            reason=f"方向:{direction.value}, 位置:{position_pct:.1f}%, EV:{expected_value:.2f}"
        )
    
    def _create_short_signal(self,
                            entry_price: float,
                            range_1h: Range,
                            available_balance: float,
                            leverage: int,
                            direction: Direction,
                            position_pct: float) -> Optional[TradeSignal]:
        """创建做空信号"""
        # 计算止损价（清算价-2%）
        liquidation_price = entry_price * (1 + 1/leverage)
        stop_loss = liquidation_price * 0.98
        
        # 计算阶梯止盈
        tp1 = entry_price - 800
        tp2 = entry_price - 1500
        tp3 = range_1h.support + 500
        
        # 计算期望值
        profit_amount = entry_price - tp1
        loss_amount = stop_loss - entry_price
        profit_probability = 0.7
        
        expected_value = self.calculate_expected_value(
            profit_probability, profit_amount, loss_amount
        )
        risk_reward_ratio = profit_amount / loss_amount if loss_amount > 0 else 0
        
        self.logger.info(f"  期望值: {expected_value:.2f} (要求≥{self.min_expected_value})")
        self.logger.info(f"  风险回报比: {risk_reward_ratio:.2f}:1 (要求≥{self.min_risk_reward_ratio}:1)")
        
        # 验证条件
        if expected_value < self.min_expected_value:
            self.logger.warning("❌ 期望值不足")
            return None
        
        if risk_reward_ratio < self.min_risk_reward_ratio:
            self.logger.warning("❌ 风险回报比不足")
            return None
        
        # 计算仓位大小
        margin = available_balance * 0.10
        position_size_usd = margin * leverage
        
        self.logger.info("✅ 生成做空信号")
        
        return TradeSignal(
            action="open_short",
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit_1=tp1,
            take_profit_2=tp2,
            take_profit_3=tp3,
            position_size_usd=position_size_usd,
            expected_value=expected_value,
            risk_reward_ratio=risk_reward_ratio,
            reason=f"方向:{direction.value}, 位置:{position_pct:.1f}%, EV:{expected_value:.2f}"
        )
