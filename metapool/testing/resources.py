import os
from dotenv import dotenv_values
from algofi_amm.v0.client import AlgofiAMMTestnetClient
from ..utils import compiledContract, Account
from algofi_amm.v0.client import AlgofiAMMClient
from algosdk.v2client.algod import AlgodClient
from algosdk.future import transaction
from random import randint


def startup():
    """
    Initialize an algofi amm testnet client and a creator account.
    """
    # Local Algod Address
    ALGOD_TOKEN = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    ALGOD_ADDRESS = "http://localhost:4001"

    creator_account = get_creator_account()
    # We have to use a local algod client because the algoexplorer api does not support get function anymore
    amm_client = AlgofiAMMTestnetClient(
        algod_client=AlgodClient(ALGOD_TOKEN, ALGOD_ADDRESS),
        indexer_client=None,
        user_address=creator_account.getAddress(),
    )
    return amm_client, creator_account


def get_creator_account():
    """
    Securely load key-pair from mnemonic file
    .env file in the testing folder containing mnemonic = your 25 words
    """
    # Securely load key-pair from mnemonic file
    my_path = os.path.abspath(os.path.dirname(__file__))
    ENV_PATH = os.path.join(my_path, ".env")
    user = dotenv_values(ENV_PATH)
    return Account.FromMnemonic(user["mnemonic"])


def newTestToken(client: AlgofiAMMClient, creator: Account) -> int:
    """
    Transaction to create a new test asset.
    """
    randomNumber = randint(0, 99)
    txn = transaction.AssetConfigTxn(
        sender=creator.getAddress(),
        sp=client.algod.suggested_params(),
        total=10**12,
        default_frozen=False,
        unit_name=f"UST{randomNumber}",
        asset_name=f"USTest{randomNumber}",
        manager=creator.getAddress(),
        reserve=None,
        freeze=None,
        clawback=None,
        strict_empty_address_check=False,
        url=None,
        metadata_hash=None,
        decimals=0,
    )

    # Sign with secret key of creator
    stxn = txn.sign(creator.getPrivateKey())

    # Send the transaction to the network and retrieve the txid.
    txid = client.algod.send_transaction(stxn)
    print("Asset Creation Transaction ID: {}".format(txid))

    # Wait for the transaction to be confirmed
    confirmed_txn = transaction.wait_for_confirmation(client.algod, txid, 4)
    print("TXID: ", txid)
    print("Result confirmed in round: {}".format(confirmed_txn["confirmed-round"]))
    try:
        ptx = client.algod.pending_transaction_info(txid)
        us_test_id = ptx["asset-index"]
        # print(client.indexer.accounts(asset_id=us_test_id)["accounts"]["created-assets"])
        return us_test_id
    except Exception as e:
        print(e)


def update_metapool(algod_client: AlgodClient, creator: Account, metapool_app_id: int):
    """
    Update an Existing Metapool
    """
    approval_program, clear_program = compiledContract(algod_client)
    # create unsigned transaction
    txn = transaction.ApplicationUpdateTxn(
        creator.getAddress(),
        algod_client.suggested_params(),
        metapool_app_id,
        approval_program,
        clear_program,
    )
    # sign, send, await
    stxn = txn.sign(creator.getPrivateKey())
    txid = algod_client.send_transaction(stxn)
    confirmed_txn = transaction.wait_for_confirmation(algod_client, txid, 4)
    print("TXID: ", txid)
    print("Result confirmed in round: {}".format(confirmed_txn["confirmed-round"]))
    try:
        ptx = algod_client.pending_transaction_info(txid)
        app_id = ptx["txn"]["txn"]["apid"]
        print("Updated existing app-id: ", app_id)
    except Exception as e:
        print(e)


def is_close(a, b, e=1):
    return abs(a - b) <= e
