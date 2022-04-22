from algofi_amm.utils import get_account_balances
from metapool.metapoolAMMClient import MetapoolAMMClient
from metapool.testing.configTestnet import METAPOOL_APP_ID
from metapool.testing.resources import startup

# STARTUP
amm_client, creator_account = startup()

# Activate Metapool from app ID
metapool = MetapoolAMMClient.fromMetapoolId(amm_client, METAPOOL_APP_ID)

# Get starting balances
creator_balances = get_account_balances(
    amm_client.indexer, creator_account.getAddress()
)
contract_balances = get_account_balances(amm_client.indexer, metapool.metapool_address)

print("Creator Balances:")
print(
    "UStest: %i, Nanopool LP asset: %i, Metapool LP asset: %i"
    % (
        creator_balances[metapool.meta_asset_id],
        creator_balances[metapool.nanopool.lp_asset_id],
        creator_balances[metapool.metapool_lp_asset_id],
    )
)

print("Metapool Balances:")
print(
    "UStest: %i, Nanopool LP asset: %i, Metapool LP asset: %i"
    % (
        contract_balances[metapool.meta_asset_id],
        contract_balances[metapool.nanopool.lp_asset_id],
        contract_balances[metapool.metapool_lp_asset_id],
    )
)

print("Adding Liquidity.")
amount = int(creator_balances[metapool.nanopool.lp_asset_id] / 2)
metapool.add_liquidity(creator_account, amount, amount)

# Get final balances
creator_balances = get_account_balances(
    amm_client.indexer, creator_account.getAddress()
)
contract_balances = get_account_balances(amm_client.indexer, metapool.metapool_address)

print("Creator Balances:")
print(
    "UStest: %i, Nanopool LP asset: %i, Metapool LP asset: %i"
    % (
        creator_balances[metapool.meta_asset_id],
        creator_balances[metapool.nanopool.lp_asset_id],
        creator_balances[metapool.metapool_lp_asset_id],
    )
)

print("Metapool Balances:")
print(
    "UStest: %i, Nanopool LP asset: %i, Metapool LP asset: %i"
    % (
        contract_balances[metapool.meta_asset_id],
        contract_balances[metapool.nanopool.lp_asset_id],
        contract_balances[metapool.metapool_lp_asset_id],
    )
)
