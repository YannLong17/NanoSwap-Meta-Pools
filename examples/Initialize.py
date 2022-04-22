from algofi_amm.v0.asset import Asset
from algofi_amm.v0.config import PoolType
from algofi_amm.utils import get_payment_txn, send_and_wait
from metapool.metapoolAMMClient import MetapoolAMMClient
from metapool.testing.resources import startup, newTestToken, update_metapool
from metapool.testing.configTestnet import (
    ASSET1_ID,
    ASSET2_ID,
    USTEST_ID,
    METAPOOL_APP_ID,
    FEE_BPS,
    MIN_INCREMENT,
)

# STARTUP
amm_client, creator_account = startup()

# Initialize a nanopool
nanopool = amm_client.get_pool(PoolType.NANOSWAP, ASSET1_ID, ASSET2_ID)
lp_asset_id = nanopool.lp_asset_id
lp_asset = Asset(amm_client, lp_asset_id)
print("lp id: %i" % lp_asset_id)

print("ustest id: %i" % USTEST_ID)

# SET ASSETS
asset1 = Asset(amm_client, ASSET1_ID)
asset2 = Asset(amm_client, ASSET2_ID)

# make sure user is opted in assets
for asset in [asset1, asset2, lp_asset]:
    if not amm_client.is_opted_into_asset(asset):
        print(creator_account.getAddress() + " not opted into asset " + asset.name)
        txn = get_payment_txn(
            amm_client.algod.suggested_params(),
            creator_account.getAddress(),
            creator_account.getAddress(),
            int(0),
            asset_id=asset.asset_id,
        )
        send_and_wait(amm_client.algod, [txn.sign(creator_account.getPrivateKey())])

# Publish the metaswap contract
if not METAPOOL_APP_ID:
    # Create a new metapool client
    Metapool = MetapoolAMMClient(
        client=amm_client,
        nanopool=nanopool,
        metaAssetID=USTEST_ID,
    )
    metapool_app_id = Metapool.createMetapool(creator_account)
    print("Metapool Created")
    print("Metapool App ID: %i" % metapool_app_id)
    # Fund the account and initialize the contract
    metapool_lp_id = Metapool.setupMetapool(
        creator_account, feeBps=FEE_BPS, minIncrement=MIN_INCREMENT
    )
    print("Metapool set up")
    print("Metapool LP token ID: %i" % metapool_lp_id)

    # Opt in to the Metapool LP token asset
    print("Opting in to pool token")
    Metapool.optInToPoolToken(creator_account)

# Update the contract
else:
    update_metapool(amm_client.algod, creator_account, METAPOOL_APP_ID)
