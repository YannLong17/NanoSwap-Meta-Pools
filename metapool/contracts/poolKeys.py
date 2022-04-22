from pyteal import Bytes, Int


class metapool_strings:
    nanopool_app_id = "nanopool app id"
    nanopool_manager_id = "nanopool manager id"
    nanopool_address = "nanopool address"
    nanopool_asset_1_id = "nanopool asset 1 id"
    nanopool_asset_2_id = "nanopool asset 2 id"
    nanopool_lp_id = "nanopool lp id"
    meta_asset_id = "meta asset id"
    meta_lp_id = "meta lp id"
    fee_bps = "fee bps"
    min_increment = "min increment"
    pool_token_outstanding = "pool tokens outstanding"
    op_metaswap = "swap"
    op_set_metapool = "set metapool"
    op_add_liquidity = "add liquidity"
    op_withdraw = "withdraw"
    scaling_factor = 10**13
    pool_token_default_amount = 10**13


# Contract Global variables (10 global ints, 1 global byteslice)
NANOPOOL_APP_ID_KEY = Bytes(metapool_strings.nanopool_app_id)  # Int
NANOPOOL_MANAGER_ID_KEY = Bytes(metapool_strings.nanopool_manager_id)  # Int
NANOPOOL_ADDRESS_KEY = Bytes(metapool_strings.nanopool_address)  # byteslice
NANOPOOL_ASSET_1_ID_KEY = Bytes(metapool_strings.nanopool_asset_1_id)  # Int
NANOPOOL_ASSET_2_ID_KEY = Bytes(metapool_strings.nanopool_asset_2_id)  # Int
NANOPOOL_LP_ID_KEY = Bytes(metapool_strings.nanopool_lp_id)  # Int
META_ASSET_ID_KEY = Bytes(metapool_strings.meta_asset_id)  # Int
META_LP_ID_KEY = Bytes(metapool_strings.meta_lp_id)  # Int
FEE_BPS_KEY = Bytes(metapool_strings.fee_bps)  # Int
MIN_INCREMENT_KEY = Bytes(metapool_strings.min_increment)  # Int
POOL_TOKENS_OUTSTANDING_KEY = Bytes(metapool_strings.pool_token_outstanding)  # Int

# Constants
SCALING_FACTOR = Int(metapool_strings.scaling_factor)
POOL_TOKEN_DEFAULT_AMOUNT = Int(metapool_strings.pool_token_default_amount)

# Operations
OP_METASWAP = Bytes(metapool_strings.op_metaswap)
OP_SET_METAPOOL = Bytes(metapool_strings.op_set_metapool)
OP_ADD_LIQUIDITY = Bytes(metapool_strings.op_add_liquidity)
OP_WITHDRAW = Bytes(metapool_strings.op_withdraw)
