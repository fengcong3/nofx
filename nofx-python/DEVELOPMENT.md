# Nofx Python Trading Bot - 开发说明

## 从 Go 代码迁移的关键信息

本项目是从原 Go 版本的 trading-bot 迁移而来，以下是关键的 API 对接信息：

### 1. Hyperliquid API 集成

#### Go SDK 使用的库
```go
github.com/sonirico/go-hyperliquid v0.17.0
```

#### Python 实现
由于没有官方 Python SDK，我们直接使用 REST API：

**主要 API 端点：**
- Mainnet: `https://api.hyperliquid.xyz`
- Testnet: `https://api.hyperliquid-testnet.xyz`

**核心功能对应：**

| Go SDK 方法 | Python 实现 | 说明 |
|------------|------------|-----|
| `exchange.Info().UserState()` | `POST /info` with `type: clearinghouseState` | 获取账户状态 |
| `exchange.Info().Meta()` | `POST /info` with `type: meta` | 获取市场元数据 |
| `exchange.Info().AllMids()` | `POST /info` with `type: allMids` | 获取所有价格 |
| `exchange.Order()` | `POST /exchange` with signed action | 下单 |
| `exchange.UpdateLeverage()` | `POST /exchange` with `updateLeverage` action | 设置杠杆 |
| `exchange.Cancel()` | `POST /exchange` with `cancel` action | 取消订单 |

### 2. 签名机制

**Go 实现：**
```go
import (
    "github.com/ethereum/go-ethereum/crypto"
)
// 使用 ECDSA 签名
```

**Python 实现：**
```python
from eth_account import Account
from eth_account.messages import encode_defunct

# 创建账户
account = Account.from_key(private_key)

# 签名消息
message = encode_defunct(text=connection_id)
signed_message = account.sign_message(message)
```

### 3. Agent Wallet 模式

**安全架构：**
```
主钱包 (Main Wallet)
├── 持有所有资金
├── 私钥永不暴露
└── 授权 Agent Wallet

代理钱包 (Agent Wallet)  
├── 仅用于签名
├── 余额接近0
├── 私钥配置在机器人
└── 代表主钱包执行交易
```

**Go 版本的安全检查：**
```go
// 检查是否误用主钱包私钥
if strings.EqualFold(walletAddr, agentAddr) {
    log.Printf("⚠️⚠️⚠️ WARNING: Main wallet address matches Agent wallet address!")
}

// 检查代理钱包余额
if agentBalance > 100 {
    return fmt.Errorf("security check failed: Agent wallet balance too high")
}
```

**Python 版本已实现相同的检查。**

### 4. 订单执行策略

**Go 版本的精度处理：**
```go
// 数量精度（szDecimals）
roundedQuantity := t.roundToSzDecimals(coin, quantity)

// 价格精度（5位有效数字）
aggressivePrice := t.roundPriceToSigfigs(price * 1.01)
```

**Python 版本已实现相同的精度处理。**

**IOC 市价单：**
```go
OrderType: hyperliquid.OrderType{
    Limit: &hyperliquid.LimitOrderType{
        Tif: hyperliquid.TifIoc, // Immediate or Cancel
    },
}
```

**Python 版本：**
```python
time_in_force="Ioc"  # Immediate or Cancel
```

### 5. 数据源

**Go 版本使用 WebSocket：**
```go
// market/websocket_client.go
// 实时接收 K线、订单簿等数据
```

**Python 版本简化实现：**
- 使用 REST API 轮询
- 暂时使用 Binance 公开API获取历史K线（因为 Hyperliquid 历史K线API文档不完整）
- 生产环境建议实现 WebSocket 连接

### 6. 配置对应关系

| Go 配置 | Python 配置 | 说明 |
|--------|------------|-----|
| `hyperliquid_private_key` | `agent_private_key` | 代理钱包私钥 |
| `hyperliquid_wallet_addr` | `main_wallet_address` | 主钱包地址 |
| `leverage` | `leverage` | 杠杆倍数 |
| `symbol` | `symbol` | 交易币种 |

## 未来改进方向

1. **WebSocket 集成**
   - 实时价格推送
   - 订单状态更新
   - 降低延迟

2. **完整的止盈止损**
   - 当前版本简化了止盈止损的实现
   - 需要实现 Trigger Order API

3. **持仓管理**
   - 阶梯止盈自动执行
   - 动态调整止损

4. **性能优化**
   - 减少 API 调用次数
   - 本地缓存元数据
   - 并发处理

5. **回测系统**
   - 历史数据回测
   - 策略参数优化

## 参考代码位置

- Go 版本 Hyperliquid 集成: `trader/hyperliquid_trader.go`
- 配置示例: `config.json.example`
- 策略文档: `prompts/BTC-Range-Ladder.txt`
