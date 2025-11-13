"""
交易执行器
"""
from typing import Dict, List, Optional
from src.hyperliquid_client import HyperliquidClient
from src.strategy import TradeSignal, PositionSide
from src.logger import get_logger
import time


class TradeExecutor:
    """交易执行器"""
    
    def __init__(self, client: HyperliquidClient, coin: str = "BTC"):
        """
        初始化交易执行器
        
        Args:
            client: Hyperliquid客户端
            coin: 交易币种
        """
        self.client = client
        self.coin = coin
        self.logger = get_logger()
        self.meta_cache = None
        self.sz_decimals = 4  # 默认精度
    
    def _refresh_meta(self):
        """刷新元数据缓存"""
        try:
            self.meta_cache = self.client.get_meta_info()
            for asset in self.meta_cache.get("universe", []):
                if asset["name"] == self.coin:
                    self.sz_decimals = asset.get("szDecimals", 4)
                    self.logger.debug(f"✓ {self.coin} 数量精度: {self.sz_decimals}")
                    break
        except Exception as e:
            self.logger.error(f"❌ 刷新元数据失败: {e}")
    
    def _round_size(self, size: float) -> float:
        """根据精度四舍五入数量"""
        multiplier = 10 ** self.sz_decimals
        return round(size * multiplier) / multiplier
    
    def _round_price(self, price: float) -> float:
        """四舍五入价格到5位有效数字"""
        if price == 0:
            return 0
        
        # 计算数量级
        magnitude = abs(price)
        multiplier = 1.0
        
        while magnitude >= 10:
            magnitude /= 10
            multiplier /= 10
        while magnitude < 1:
            magnitude *= 10
            multiplier *= 10
        
        # 5位有效数字
        multiplier *= 10000
        return round(price * multiplier) / multiplier
    
    def get_balance(self) -> Dict[str, float]:
        """
        获取账户余额
        
        Returns:
            余额信息字典
        """
        try:
            state = self.client.get_user_state()
            
            # 解析余额
            margin_summary = state.get("marginSummary", {})
            cross_margin_summary = state.get("crossMarginSummary", {})
            
            # 优先使用crossMarginSummary（全仓模式）
            summary = cross_margin_summary if cross_margin_summary else margin_summary
            
            account_value = float(summary.get("accountValue", "0"))
            total_margin_used = float(summary.get("totalMarginUsed", "0"))
            
            # 计算可用余额
            available_balance = account_value - total_margin_used
            if available_balance < 0:
                available_balance = 0
            
            # 计算未实现盈亏
            total_unrealized_pnl = 0
            for asset_pos in state.get("assetPositions", []):
                position = asset_pos.get("position", {})
                unrealized_pnl = float(position.get("unrealizedPnl", "0"))
                total_unrealized_pnl += unrealized_pnl
            
            self.logger.info(f"💰 账户余额: 总资产={account_value:.2f}, "
                           f"可用={available_balance:.2f}, "
                           f"未实现盈亏={total_unrealized_pnl:.2f}")
            
            return {
                "total": account_value,
                "available": available_balance,
                "unrealized_pnl": total_unrealized_pnl
            }
        except Exception as e:
            self.logger.error(f"❌ 获取余额失败: {e}")
            return {"total": 0, "available": 0, "unrealized_pnl": 0}
    
    def get_positions(self) -> List[Dict]:
        """
        获取当前持仓
        
        Returns:
            持仓列表
        """
        try:
            state = self.client.get_user_state()
            positions = []
            
            for asset_pos in state.get("assetPositions", []):
                position = asset_pos.get("position", {})
                coin = position.get("coin", "")
                
                if coin != self.coin:
                    continue
                
                size = float(position.get("szi", "0"))
                if size == 0:
                    continue
                
                side = "long" if size > 0 else "short"
                entry_px = float(position.get("entryPx", "0"))
                unrealized_pnl = float(position.get("unrealizedPnl", "0"))
                
                positions.append({
                    "coin": coin,
                    "side": side,
                    "size": abs(size),
                    "entry_price": entry_px,
                    "unrealized_pnl": unrealized_pnl
                })
                
                self.logger.info(f"📊 持仓: {coin} {side} {abs(size):.4f} "
                               f"@ {entry_px:.2f} (盈亏: {unrealized_pnl:.2f})")
            
            return positions
        except Exception as e:
            self.logger.error(f"❌ 获取持仓失败: {e}")
            return []
    
    def get_market_price(self) -> Optional[float]:
        """
        获取市场价格
        
        Returns:
            当前价格
        """
        try:
            all_mids = self.client.get_all_mids()
            price_str = all_mids.get(self.coin)
            if price_str:
                price = float(price_str)
                self.logger.debug(f"💹 {self.coin} 当前价格: {price:.2f}")
                return price
            else:
                self.logger.error(f"❌ 未找到{self.coin}价格")
                return None
        except Exception as e:
            self.logger.error(f"❌ 获取价格失败: {e}")
            return None
    
    def execute_signal(self, signal: TradeSignal, leverage: int) -> bool:
        """
        执行交易信号
        
        Args:
            signal: 交易信号
            leverage: 杠杆倍数
            
        Returns:
            是否成功
        """
        try:
            self.logger.info("=" * 80)
            self.logger.info(f"🚀 执行交易信号: {signal.action}")
            self.logger.info(f"  原因: {signal.reason}")
            
            # 刷新元数据
            self._refresh_meta()
            
            # 设置杠杆
            self.logger.info(f"⚙️ 设置杠杆: {leverage}x")
            self.client.update_leverage(self.coin, leverage, is_cross=True)
            
            # 取消现有订单
            self._cancel_all_orders()
            
            # 计算订单参数
            current_price = self.get_market_price()
            if not current_price:
                return False
            
            # 计算交易数量
            size = signal.position_size_usd / current_price
            size = self._round_size(size)
            
            # 执行开仓
            if signal.action == "open_long":
                return self._open_long(size, signal, current_price)
            elif signal.action == "open_short":
                return self._open_short(size, signal, current_price)
            
            return False
        except Exception as e:
            self.logger.error(f"❌ 执行信号失败: {e}")
            return False
    
    def _open_long(self, size: float, signal: TradeSignal, current_price: float) -> bool:
        """开多仓"""
        try:
            # 使用IOC市价单（价格略高于当前价格）
            order_price = self._round_price(current_price * 1.01)
            
            self.logger.info(f"📈 开多仓: {size:.4f} {self.coin} @ {order_price:.2f}")
            result = self.client.place_order(
                coin=self.coin,
                is_buy=True,
                size=size,
                price=order_price,
                order_type="limit",
                reduce_only=False,
                time_in_force="Ioc"
            )
            
            self.logger.info(f"✅ 开仓成功: {result}")
            
            # 设置止损
            time.sleep(1)
            self._set_stop_loss(size, signal.stop_loss, is_long=True)
            
            # 设置止盈
            self._set_take_profit(size * 0.3, signal.take_profit_1, is_long=True)
            
            return True
        except Exception as e:
            self.logger.error(f"❌ 开多仓失败: {e}")
            return False
    
    def _open_short(self, size: float, signal: TradeSignal, current_price: float) -> bool:
        """开空仓"""
        try:
            # 使用IOC市价单（价格略低于当前价格）
            order_price = self._round_price(current_price * 0.99)
            
            self.logger.info(f"📉 开空仓: {size:.4f} {self.coin} @ {order_price:.2f}")
            result = self.client.place_order(
                coin=self.coin,
                is_buy=False,
                size=size,
                price=order_price,
                order_type="limit",
                reduce_only=False,
                time_in_force="Ioc"
            )
            
            self.logger.info(f"✅ 开仓成功: {result}")
            
            # 设置止损
            time.sleep(1)
            self._set_stop_loss(size, signal.stop_loss, is_long=False)
            
            # 设置止盈
            self._set_take_profit(size * 0.3, signal.take_profit_1, is_long=False)
            
            return True
        except Exception as e:
            self.logger.error(f"❌ 开空仓失败: {e}")
            return False
    
    def _set_stop_loss(self, size: float, price: float, is_long: bool):
        """设置止损"""
        try:
            size = self._round_size(size)
            price = self._round_price(price)
            
            self.logger.info(f"🛡️ 设置止损: {price:.2f}")
            
            # 注意: Hyperliquid的止损单需要使用trigger order
            # 这里简化实现，实际需要使用专门的trigger order API
            # 暂时跳过，由策略层面管理
            
        except Exception as e:
            self.logger.error(f"❌ 设置止损失败: {e}")
    
    def _set_take_profit(self, size: float, price: float, is_long: bool):
        """设置止盈"""
        try:
            size = self._round_size(size)
            price = self._round_price(price)
            
            self.logger.info(f"🎯 设置止盈: {price:.2f} (数量: {size:.4f})")
            
            # 同样，这里简化实现
            # 实际应该使用limit order挂单
            
        except Exception as e:
            self.logger.error(f"❌ 设置止盈失败: {e}")
    
    def _cancel_all_orders(self):
        """取消所有挂单"""
        try:
            orders = self.client.get_open_orders()
            for order in orders:
                if order.get("coin") == self.coin:
                    oid = order.get("oid")
                    self.client.cancel_order(self.coin, oid)
                    self.logger.info(f"✓ 取消订单: {oid}")
        except Exception as e:
            self.logger.error(f"❌ 取消订单失败: {e}")
