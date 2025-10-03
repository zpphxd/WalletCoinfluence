"""DEX router addresses for filtering real swaps."""

# Popular DEX router addresses by chain
DEX_ROUTERS = {
    "ethereum": [
        # Uniswap V2
        "0x7a250d5630b4cf539739df2c5dacb4c659f2488d",
        # Uniswap V3
        "0xe592427a0aece92de3edee1f18e0157c05861564",
        "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45",
        # SushiSwap
        "0xd9e1ce17f2641f24ae83637ab66a2cca9c378b9f",
        # 1inch
        "0x1111111254fb6c44bac0bed2854e76f90643097d",
        # 0x Exchange Proxy
        "0xdef1c0ded9bec7f1a1670819833240f027b25eff",
        # Balancer V2
        "0xba12222222228d8ba445958a75a0704d566bf2c8",
        # Curve
        "0x99a58482bd75cbab83b27ec03ca68ff489b5788f",
    ],
    "base": [
        # Uniswap V3
        "0x2626664c2603336e57b271c5c0b26f421741e481",
        # BaseSwap
        "0x327df1e6de05895d2ab08513aadd9313fe505d86",
        # Aerodrome
        "0xcf77a3ba9a5ca399b7c97c74d54e5b1beb874e43",
    ],
    "arbitrum": [
        # Uniswap V3
        "0xe592427a0aece92de3edee1f18e0157c05861564",
        "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45",
        # SushiSwap
        "0x1b02da8cb0d097eb8d57a175b88c7d8b47997506",
        # Camelot
        "0xc873fecbd354f5a56e00e710b90ef4201db2448d",
    ],
    "solana": [
        # Raydium AMM
        "675kpx9mhtps2uysqtfcrn7exrqz56wnbs5qvaxtbqcsp",
        # Orca
        "9w4ndk37p8urxj9b6sqejktpa6suzaw4n4ctvucr7zjt",
        # Jupiter Aggregator
        "jupsobzvjsshzgqdc9fpqagvdtd2tfpgfoyk5aeny4uanmh",
        # Pump.fun
        "6ebqnewfymuxpbkvmuajqrfchnqbeudtcfhrzsbsac3tkgq",
    ]
}

def is_dex_router(address: str, chain_id: str) -> bool:
    """Check if address is a known DEX router.

    Args:
        address: Contract/program address
        chain_id: Chain identifier

    Returns:
        True if address is a DEX router
    """
    if not address or not chain_id:
        return False

    # Normalize address to lowercase for comparison
    address = address.lower()

    routers = DEX_ROUTERS.get(chain_id, [])
    return address in routers

def get_dex_name(address: str, chain_id: str) -> str:
    """Get DEX name from router address.

    Args:
        address: Router address
        chain_id: Chain identifier

    Returns:
        DEX name or 'unknown'
    """
    if not address:
        return "unknown"

    address = address.lower()

    # Map of router addresses to DEX names
    dex_names = {
        # Ethereum
        "0x7a250d5630b4cf539739df2c5dacb4c659f2488d": "uniswap_v2",
        "0xe592427a0aece92de3edee1f18e0157c05861564": "uniswap_v3",
        "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45": "uniswap_v3",
        "0xd9e1ce17f2641f24ae83637ab66a2cca9c378b9f": "sushiswap",
        "0x1111111254fb6c44bac0bed2854e76f90643097d": "1inch",
        "0xdef1c0ded9bec7f1a1670819833240f027b25eff": "0x",
        "0xba12222222228d8ba445958a75a0704d566bf2c8": "balancer",
        "0x99a58482bd75cbab83b27ec03ca68ff489b5788f": "curve",
        # Base
        "0x2626664c2603336e57b271c5c0b26f421741e481": "uniswap_v3",
        "0x327df1e6de05895d2ab08513aadd9313fe505d86": "baseswap",
        "0xcf77a3ba9a5ca399b7c97c74d54e5b1beb874e43": "aerodrome",
        # Arbitrum
        "0x1b02da8cb0d097eb8d57a175b88c7d8b47997506": "sushiswap",
        "0xc873fecbd354f5a56e00e710b90ef4201db2448d": "camelot",
        # Solana
        "675kpx9mhtps2uysqtfcrn7exrqz56wnbs5qvaxtbqcsp": "raydium",
        "9w4ndk37p8urxj9b6sqejktpa6suzaw4n4ctvucr7zjt": "orca",
        "jupsobzvjsshzgqdc9fpqagvdtd2tfpgfoyk5aeny4uanmh": "jupiter",
        "6ebqnewfymuxpbkvmuajqrfchnqbeudtcfhrzsbsac3tkgq": "pumpfun",
    }

    return dex_names.get(address, "unknown")