"""
市场数据管理
"""
from typing import List, Dict, Optional
import requests
from src.logger import get_logger


class MarketDataManager:
    """市场数据管理器"""
    
    def __init__(self, coin: str = "BTC"):
        """
        初始化数据管理器
        
        Args:
            coin: 币种
        """
        self.coin = coin
        self.logger = get_logger()
    
    def get_kline_data(self, 
                       interval: str,
                       limit: int = 200) -> Optional[List[float]]:
        """
        获取K线数据（使用公开API）
        
        Args:
            interval: 时间间隔 ("1m", "15m", "1h", "4h", "1d")
            limit: 数据条数
            
        Returns:
            价格列表
        """
        try:
            # 这里使用Binance的公开API获取历史数据
            # 实际应该使用Hyperliquid的API，但目前文档不完整
            symbol = f"{self.coin}USDT"
            url = f"https://api.binance.com/api/v3/klines"
            params = {
                "symbol": symbol,
                "interval": interval,
                "limit": limit
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            prices = [float(item[4]) for item in data]  # 收盘价
            
            self.logger.debug(f"✓ 获取{interval}数据: {len(prices)}条")
            return prices
        except Exception as e:
            self.logger.error(f"❌ 获取K线数据失败: {e}")
            return None
    
    def calculate_ema(self, prices: List[float], period: int) -> List[float]:
        """
        计算EMA指标
        
        Args:
            prices: 价格序列
            period: 周期
            
        Returns:
            EMA序列
        """
        if not prices or len(prices) < period:
            return []
        
        ema = []
        multiplier = 2 / (period + 1)
        
        # 初始EMA = SMA
        sma = sum(prices[:period]) / period
        ema.append(sma)
        
        # 计算后续EMA
        for price in prices[period:]:
            ema_value = (price - ema[-1]) * multiplier + ema[-1]
            ema.append(ema_value)
        
        return ema
    
    def get_market_data(self) -> Dict[str, List[float]]:
        """
        获取完整的市场数据
        
        Returns:
            市场数据字典
        """
        self.logger.info("📊 获取市场数据...")
        
        # 获取各周期K线
        price_4h = self.get_kline_data("4h", limit=200)
        price_1h = self.get_kline_data("1h", limit=200)
        price_15m = self.get_kline_data("15m", limit=200)
        
        if not price_4h or not price_1h or not price_15m:
            self.logger.error("❌ 市场数据获取失败")
            return {}
        
        # 计算技术指标
        ema20_4h = self.calculate_ema(price_4h, 20)
        ema50_4h = self.calculate_ema(price_4h, 50)
        
        return {
            "price_4h": price_4h,
            "price_1h": price_1h,
            "price_15m": price_15m,
            "ema20_4h": ema20_4h,
            "ema50_4h": ema50_4h
        }
