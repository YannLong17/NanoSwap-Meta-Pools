from base64 import b64decode
from pyteal import compileTeal, MAX_TEAL_VERSION, Mode
from metapool.contracts.metapoolContract import approval, clear
from typing import Tuple
from algosdk.v2client.algod import AlgodClient
from algosdk import account, mnemonic

MIN_BALANCE_REQUIREMENT = (
    # min account balance
    100_000
    # additional min balance for 5 assets
    + 100_000 * 5
)


class Account:
    """Represents a private key and address for an Algorand account"""

    def __init__(self, privateKey: str) -> None:
        self.sk = privateKey
        self.addr = account.address_from_private_key(privateKey)

    def getAddress(self) -> str:
        return self.addr

    def getPrivateKey(self) -> str:
        return self.sk

    def getMnemonic(self) -> str:
        return mnemonic.from_private_key(self.sk)

    @classmethod
    def FromMnemonic(cls, m: str) -> "Account":
        return cls(mnemonic.to_private_key(m))


def getPoolTokenId(appGlobalState):
    try:
        return appGlobalState["meta lp id"]
    except KeyError:
        raise RuntimeError(
            "Pool token id doesn't exist. Make sure the app has been set up"
        )


def compiledContract(algod_client: AlgodClient) -> Tuple[bytes, bytes]:
    approval_program = algod_client.compile(
        compileTeal(approval(), mode=Mode.Application, version=MAX_TEAL_VERSION)
    )
    clear_program = algod_client.compile(
        compileTeal(clear(), mode=Mode.Application, version=MAX_TEAL_VERSION)
    )
    return (b64decode(approval_program["result"]), b64decode(clear_program["result"]))
