from algofi_amm.utils import get_account_balances
from metapool.metapoolAMMClient import MetapoolAMMClient
from metapool.testing.configTestnet import METAPOOL_APP_ID
from metapool.testing.resources import startup
from algofi_amm.utils import get_account_balances

# STARTUP
amm_client, creator_account = startup()

# Activate Metapool from app ID
metapool = MetapoolAMMClient.fromMetapoolId(amm_client, METAPOOL_APP_ID)

# Fund Metapool
metapool.fundMetapool(creator_account, 1_000_000)

# Get starting balances
creator_balances = get_account_balances(
    amm_client.indexer, creator_account.getAddress()
)
print("User Balances:")
print(
    "UStest: %i, Nanopool asset 1: %i, Nanopool asset 2: %i"
    % (
        creator_balances[metapool.meta_asset_id],
        creator_balances[metapool.nanopool.asset1.asset_id],
        creator_balances[metapool.nanopool.asset2.asset_id],
    )
)
x = 10000  # Swap Amount
# Swap UStest for asset1
metapool.metaswap(
    creator_account, metapool.meta_asset_id, x, metapool.nanopool.asset1.asset_id
)
creator_balances_2 = get_account_balances(
    amm_client.indexer, creator_account.getAddress()
)
print("Swapped %i UStest for Nanopool asset 2, Balance delta:" % x)
print(
    "UStest: %i, Nanopool asset 1: %i, Nanopool asset 2: %i"
    % (
        creator_balances_2[metapool.meta_asset_id]
        - creator_balances[metapool.meta_asset_id],
        creator_balances_2[metapool.nanopool.asset1.asset_id]
        - creator_balances[metapool.nanopool.asset1.asset_id],
        creator_balances_2[metapool.nanopool.asset2.asset_id]
        - creator_balances[metapool.nanopool.asset2.asset_id],
    )
)
creator_balances = creator_balances_2
# Swap asset 2 for US test
metapool.metaswap(
    creator_account, metapool.nanopool.asset2.asset_id, x, metapool.meta_asset_id
)
creator_balances_2 = get_account_balances(
    amm_client.indexer, creator_account.getAddress()
)
print("Swapped %i Nanopool asset 2 for UStest, Balance delta:" % x)
print(
    "UStest: %i, Nanopool asset 1: %i, Nanopool asset 2: %i"
    % (
        creator_balances_2[metapool.meta_asset_id]
        - creator_balances[metapool.meta_asset_id],
        creator_balances_2[metapool.nanopool.asset1.asset_id]
        - creator_balances[metapool.nanopool.asset1.asset_id],
        creator_balances_2[metapool.nanopool.asset2.asset_id]
        - creator_balances[metapool.nanopool.asset2.asset_id],
    )
)
creator_balances = creator_balances_2
# swap asset 1 for US test
metapool.metaswap(
    creator_account, metapool.nanopool.asset1.asset_id, x, metapool.meta_asset_id
)
creator_balances_2 = get_account_balances(
    amm_client.indexer, creator_account.getAddress()
)
print("Swapped %i Nanopool asset 1 for UStest, Balance delta:" % x)
print(
    "UStest: %i, Nanopool asset 1: %i, Nanopool asset 2: %i"
    % (
        creator_balances_2[metapool.meta_asset_id]
        - creator_balances[metapool.meta_asset_id],
        creator_balances_2[metapool.nanopool.asset1.asset_id]
        - creator_balances[metapool.nanopool.asset1.asset_id],
        creator_balances_2[metapool.nanopool.asset2.asset_id]
        - creator_balances[metapool.nanopool.asset2.asset_id],
    )
)
