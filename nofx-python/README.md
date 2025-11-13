# Nofx Python Trading Bot

基于 **BTC-Range-Ladder 策略**的 Hyperliquid 自动交易机器人，使用 Python 实现。

## 🎯 项目特点

- ✅ **纯策略驱动**: 完全基于技术分析，无需大模型AI，响应速度快
- ✅ **低成本**: 无API调用费用，只有交易手续费
- ✅ **安全设计**: 支持 Hyperliquid Agent Wallet 模式，分离签名权限与资金
- ✅ **详细日志**: 完整的交易日志记录，便于分析和调试
- ✅ **区间震荡策略**: 专注于震荡市场，多开仓、多止盈、少止损

## 📋 功能特性

### 策略实现
- 多周期市场分析（4小时、1小时、15分钟）
- 震荡区间识别和位置评估
- 期望值和风险回报比双重验证
- 精确入场时机判断
- 阶梯止盈（3级：30%、30%、40%）
- 防爆仓止损（清算价+2%安全边距）

### 交易管理
- 交易频率限制（可配置，0=不限制）
- 仓位管理（默认10%可用余额）
- 自动设置杠杆
- 市价单快速成交

### 安全特性
- Agent Wallet 模式（推荐）
- 余额安全检查
- 错误处理和重试
- 详细的操作日志

## 🛠️ 安装步骤

### 1. 环境要求

- Python 3.8+
- pip

### 2. 安装依赖

```bash
cd nofx-python
pip install -r requirements.txt
```

### 3. 配置文件

复制配置示例并修改：

```bash
cp config.json config.json.example
```

编辑 `config.json`：

```json
{
  "hyperliquid": {
    "agent_private_key": "你的代理钱包私钥（0x开头）",
    "main_wallet_address": "你的主钱包地址（0x开头）",
    "testnet": false,
    "leverage": {
      "BTC": 20,
      "ETH": 20,
      "default": 10
    }
  },
  "trading": {
    "symbol": "BTC",
    "initial_capital": 0,
    "max_position_percentage": 15,
    "min_expected_value": 1.5,
    "min_risk_reward_ratio": 3.0,
    "max_trades_per_hour": 0,
    "min_holding_minutes": 30
  },
  "logging": {
    "level": "INFO",
    "log_to_file": true,
    "log_dir": "logs"
  }
}
```

## 🔐 安全配置（重要！）

### Hyperliquid Agent Wallet 模式

**强烈建议**使用 Agent Wallet 模式，这是官方推荐的安全实践：

1. **主钱包**（Main Wallet）
   - 持有所有资金
   - **私钥绝不暴露**
   - 用于登录 Hyperliquid 网站

2. **代理钱包**（Agent Wallet）
   - 仅用于签名交易
   - **余额应接近0**（建议 < 10 USDC）
   - 私钥用于机器人配置
   - 在 Hyperliquid 网站授权后才能代理主钱包交易

### 设置步骤

1. 访问 [Hyperliquid](https://app.hyperliquid.xyz/)
2. 使用主钱包登录
3. 进入 Settings → API Wallets
4. 创建新的 API Wallet（代理钱包）
5. 授权该代理钱包可以代表主钱包交易
6. 复制代理钱包私钥到 `config.json` 的 `agent_private_key`
7. 填写主钱包地址到 `main_wallet_address`

### 安全检查

程序启动时会自动检查：
- ✅ 是否使用 Agent Wallet 模式
- ⚠️ 代理钱包余额是否过高（> 100 USDC 会报错）
- ⚠️ 是否误用主钱包私钥

参考文档：[Hyperliquid API Wallets](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/nonces-and-api-wallets)

## 🚀 运行

```bash
python main.py
```

### 日志输出示例

```
================================================================================
🚀 Nofx Python Trading Bot 启动
================================================================================
✓ 使用代理钱包模式（安全）
  └─ 代理钱包地址: 0x1234... (用于签名)
  └─ 主钱包地址: 0x5678... (持有资金)
✓ Hyperliquid客户端初始化成功 (testnet=False)
✓ 交易币种: BTC
✓ 杠杆倍数: 20x
✓ 最小期望值: 1.5
✓ 最小风险回报比: 3.0:1
================================================================================
🔄 开始交易循环...
================================================================================

================================================================================
⏰ 第 1 次循环
================================================================================
💰 账户余额: 总资产=1000.00, 可用=950.00, 未实现盈亏=0.00
📊 获取市场数据...
✓ 获取4h数据: 200条
✓ 获取1h数据: 200条
✓ 获取15m数据: 200条
💹 BTC 当前价格: 95432.50
🔍 开始策略分析...
📊 市场方向分析: bullish (多:2, 空:0)
  ✓ 1h 区间: 94000.00 - 96500.00 (幅度: 2.66%)
📍 当前价格在1小时区间的位置: 57.3%
⏸️ 当前无交易信号
😴 等待 180 秒...
```

## 📊 策略说明

### BTC-Range-Ladder 策略核心

1. **多周期分析**
   - 4小时：判断大方向（偏多/偏空/震荡）
   - 1小时：识别震荡区间
   - 15分钟：精确入场时机

2. **开仓条件（必须同时满足）**
   - 大方向一致（偏多时做多，偏空时做空）
   - 位置优势（做多在区间下方0-40%，做空在上方60-100%）
   - 期望值 ≥ 1.5
   - 风险回报比 ≥ 3:1
   - 精确入场（做多在15分钟最低点+0.3%，做空在最高点-0.3%）

3. **止盈止损**
   - **止损**: 清算价 + 2%安全边距（防爆仓优先）
   - **止盈**: 阶梯式
     - TP1: 入场价 ± 800 USDT（30%仓位）
     - TP2: 入场价 ± 1500 USDT（30%仓位）
     - TP3: 区间边界 ± 500 USDT（40%仓位）

4. **仓位管理**
   - 每次开仓使用可用余额的 10%
   - 配合杠杆倍数计算名义价值
   - 交易频率可配置（默认不限制，可设置每小时最大次数）

## 📁 项目结构

```
nofx-python/
├── main.py                 # 主程序入口
├── config.json            # 配置文件（需自行创建）
├── requirements.txt       # Python依赖
├── .gitignore            # Git忽略文件
├── README.md             # 本文档
├── logs/                 # 日志目录（自动创建）
└── src/                  # 源代码
    ├── __init__.py
    ├── config.py         # 配置管理
    ├── logger.py         # 日志系统
    ├── hyperliquid_client.py  # Hyperliquid API客户端
    ├── strategy.py       # BTC-Range-Ladder策略
    ├── executor.py       # 交易执行器
    └── market_data.py    # 市场数据管理
```

## 🔧 配置参数说明

### Hyperliquid 配置

- `agent_private_key`: 代理钱包私钥（用于签名）
- `main_wallet_address`: 主钱包地址（持有资金）
- `testnet`: 是否使用测试网（默认false）
- `leverage`: 杠杆倍数配置

### 交易配置

- `symbol`: 交易币种（默认BTC）
- `initial_capital`: 初始资金（设为0则从账户实时获取永续合约余额）
- `max_position_percentage`: 最大仓位百分比
- `min_expected_value`: 最小期望值（建议1.5）
- `min_risk_reward_ratio`: 最小风险回报比（建议3.0）
- `max_trades_per_hour`: 每小时最大交易次数（设为0则不限制）
- `min_holding_minutes`: 最小持仓时间（分钟）

### 日志配置

- `level`: 日志级别（DEBUG/INFO/WARNING/ERROR）
- `log_to_file`: 是否写入文件
- `log_dir`: 日志目录

## ⚠️ 风险提示

1. **加密货币交易风险极高**，可能导致全部本金损失
2. **杠杆交易风险更高**，务必谨慎设置杠杆倍数
3. 本项目仅供学习研究使用，**不构成投资建议**
4. 使用前请充分理解策略逻辑和风险
5. 建议先在**测试网**测试，确认无误后再使用实盘
6. **强烈建议**使用 Agent Wallet 模式，保护主钱包安全

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 License

MIT License

## 📚 参考资料

- [Hyperliquid 官方文档](https://hyperliquid.gitbook.io/hyperliquid-docs)
- [Hyperliquid API 文档](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api)
- [Agent Wallets 安全指南](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/nonces-and-api-wallets)
- BTC-Range-Ladder 策略文档（见原仓库 `prompts/BTC-Range-Ladder.txt`）

## 💡 常见问题

### Q: 为什么要使用 Agent Wallet？
A: Agent Wallet 可以将签名权限与资金分离，即使私钥泄露，攻击者也只能操作授权范围内的交易，无法直接转走资金。

### Q: 代理钱包需要充值吗？
A: 不需要！代理钱包仅用于签名，余额应保持接近0。所有资金都在主钱包中。

### Q: 如何停止机器人？
A: 按 `Ctrl+C` 优雅退出，程序会完成当前循环后停止。

### Q: 可以同时交易多个币种吗？
A: 当前版本仅支持单个币种，如需多币种请运行多个实例（修改配置文件）。

### Q: 日志文件在哪里？
A: 默认在 `logs/` 目录，文件名格式为 `trading_YYYYMMDD_HHMMSS.log`。

---

**Happy Trading! 📈**
