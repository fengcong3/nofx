"""
Hyperliquid API 客户端
基于官方文档实现: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api
"""
import json
import time
import requests
from typing import Dict, List, Any, Optional
from eth_account import Account
from eth_account.messages import encode_defunct
from src.logger import get_logger


class HyperliquidClient:
    """Hyperliquid REST API 客户端"""
    
    MAINNET_API_URL = "https://api.hyperliquid.xyz"
    TESTNET_API_URL = "https://api.hyperliquid-testnet.xyz"
    
    def __init__(self, 
                 agent_private_key: str,
                 main_wallet_address: str,
                 testnet: bool = False):
        """
        初始化Hyperliquid客户端
        
        Args:
            agent_private_key: 代理钱包私钥（用于签名）
            main_wallet_address: 主钱包地址（持有资金）
            testnet: 是否使用测试网
        """
        self.logger = get_logger()
        
        # 去除0x前缀
        if agent_private_key.startswith('0x'):
            agent_private_key = agent_private_key[2:]
        
        # 创建账户
        self.account = Account.from_key(agent_private_key)
        self.agent_address = self.account.address
        self.main_wallet_address = main_wallet_address
        
        # API URL
        self.base_url = self.TESTNET_API_URL if testnet else self.MAINNET_API_URL
        
        # 安全检查
        if self.agent_address.lower() == self.main_wallet_address.lower():
            self.logger.warning("⚠️⚠️⚠️ 警告: 主钱包地址与代理钱包地址相同!")
            self.logger.warning("   这表示您可能在使用主钱包私钥，存在极高安全风险!")
            self.logger.warning("   建议: 立即在Hyperliquid官网创建独立的API钱包")
        else:
            self.logger.info("✓ 使用代理钱包模式（安全）")
            self.logger.info(f"  └─ 代理钱包地址: {self.agent_address} (用于签名)")
            self.logger.info(f"  └─ 主钱包地址: {self.main_wallet_address} (持有资金)")
        
        self.logger.info(f"✓ Hyperliquid客户端初始化成功 (testnet={testnet})")
    
    def _sign_l1_action(self, action: Dict[str, Any], nonce: int) -> Dict[str, Any]:
        """
        签名L1 Action
        
        Args:
            action: 操作内容
            nonce: 时间戳(毫秒)
            
        Returns:
            包含签名的请求数据
        """
        # 构造签名消息
        connection_id = json.dumps({
            "type": "l1Action",
            "action": action,
            "nonce": nonce,
            "chainId": "421614" if "testnet" in self.base_url else "42161"
        }, separators=(',', ':'))
        
        # 签名
        message = encode_defunct(text=connection_id)
        signed_message = self.account.sign_message(message)
        
        return {
            "action": action,
            "nonce": nonce,
            "signature": {
                "r": "0x" + signed_message.r.to_bytes(32, 'big').hex(),
                "s": "0x" + signed_message.s.to_bytes(32, 'big').hex(),
                "v": signed_message.v
            }
        }
    
    def _post_request(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送POST请求
        
        Args:
            endpoint: API端点
            data: 请求数据
            
        Returns:
            响应数据
        """
        url = f"{self.base_url}/{endpoint}"
        headers = {"Content-Type": "application/json"}
        
        try:
            response = requests.post(url, json=data, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"❌ API请求失败: {e}")
            raise
    
    def get_user_state(self, address: Optional[str] = None) -> Dict[str, Any]:
        """
        获取用户账户状态
        
        Args:
            address: 钱包地址，默认为主钱包
            
        Returns:
            账户状态数据
        """
        address = address or self.main_wallet_address
        data = {
            "type": "clearinghouseState",
            "user": address
        }
        return self._post_request("info", data)
    
    def get_meta_info(self) -> Dict[str, Any]:
        """
        获取市场元数据（币种精度等信息）
        
        Returns:
            元数据
        """
        data = {"type": "meta"}
        return self._post_request("info", data)
    
    def get_all_mids(self) -> Dict[str, str]:
        """
        获取所有币种的市场价格
        
        Returns:
            币种->价格的字典
        """
        data = {"type": "allMids"}
        return self._post_request("info", data)
    
    def get_open_orders(self, address: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取当前挂单
        
        Args:
            address: 钱包地址，默认为主钱包
            
        Returns:
            挂单列表
        """
        address = address or self.main_wallet_address
        data = {
            "type": "openOrders",
            "user": address
        }
        return self._post_request("info", data)
    
    def place_order(self,
                   coin: str,
                   is_buy: bool,
                   size: float,
                   price: float,
                   order_type: str = "limit",
                   reduce_only: bool = False,
                   time_in_force: str = "Ioc") -> Dict[str, Any]:
        """
        下单
        
        Args:
            coin: 币种名称（如"BTC"）
            is_buy: 是否买入
            size: 数量
            price: 价格
            order_type: 订单类型 ("limit" 或 "market")
            reduce_only: 是否只减仓
            time_in_force: 时效类型 ("Gtc", "Ioc", "Alo")
            
        Returns:
            下单结果
        """
        # 获取asset ID
        meta = self.get_meta_info()
        asset_id = None
        for i, asset in enumerate(meta.get("universe", [])):
            if asset["name"] == coin:
                asset_id = i
                break
        
        if asset_id is None:
            raise ValueError(f"未找到币种: {coin}")
        
        # 构造订单
        order = {
            "asset": asset_id,
            "isBuy": is_buy,
            "limitPx": str(price),
            "sz": str(size),
            "reduceOnly": reduce_only,
            "orderType": {"limit": {"tif": time_in_force}}
        }
        
        # 构造action
        action = {
            "type": "order",
            "orders": [order],
            "grouping": "na"
        }
        
        # 签名并发送
        nonce = int(time.time() * 1000)
        signed_data = self._sign_l1_action(action, nonce)
        
        return self._post_request("exchange", signed_data)
    
    def cancel_order(self, coin: str, oid: int) -> Dict[str, Any]:
        """
        取消订单
        
        Args:
            coin: 币种名称
            oid: 订单ID
            
        Returns:
            取消结果
        """
        # 获取asset ID
        meta = self.get_meta_info()
        asset_id = None
        for i, asset in enumerate(meta.get("universe", [])):
            if asset["name"] == coin:
                asset_id = i
                break
        
        if asset_id is None:
            raise ValueError(f"未找到币种: {coin}")
        
        action = {
            "type": "cancel",
            "cancels": [{"a": asset_id, "o": oid}]
        }
        
        nonce = int(time.time() * 1000)
        signed_data = self._sign_l1_action(action, nonce)
        
        return self._post_request("exchange", signed_data)
    
    def update_leverage(self, coin: str, leverage: int, is_cross: bool = True) -> Dict[str, Any]:
        """
        更新杠杆倍数
        
        Args:
            coin: 币种名称
            leverage: 杠杆倍数
            is_cross: 是否全仓模式
            
        Returns:
            更新结果
        """
        # 获取asset ID
        meta = self.get_meta_info()
        asset_id = None
        for i, asset in enumerate(meta.get("universe", [])):
            if asset["name"] == coin:
                asset_id = i
                break
        
        if asset_id is None:
            raise ValueError(f"未找到币种: {coin}")
        
        action = {
            "type": "updateLeverage",
            "asset": asset_id,
            "isCross": is_cross,
            "leverage": leverage
        }
        
        nonce = int(time.time() * 1000)
        signed_data = self._sign_l1_action(action, nonce)
        
        return self._post_request("exchange", signed_data)
