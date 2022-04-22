from pyteal import *
from metapool.contracts.poolKeys import *
from metapool.contracts.functions import *


def get_setup_program():
    nanopool_address = AppParam.address(
        Int(1)
    )  # Address of the 1st foreign app, maybevalue
    return Seq(
        nanopool_address,
        Assert(
            And(
                App.globalGet(NANOPOOL_APP_ID_KEY)
                == Int(0),  # can only initialize once
                Txn.sender() == Global.creator_address(),  # is_contract_admin
                # Check that enough Args where passed
                Txn.application_args.length() == Int(3),
                Txn.applications.length() == Int(2),
                Txn.assets.length() == Int(4),
                Balance(Global.current_application_address())
                >= Global.min_balance() * Int(5),  # Check that the contract is funded
                nanopool_address.hasValue(),  # maybevalue
            ),
        ),
        # Store relevant nanopool application info in global variables
        App.globalPut(NANOPOOL_APP_ID_KEY, Txn.applications[1]),
        App.globalPut(NANOPOOL_MANAGER_ID_KEY, Txn.applications[2]),
        App.globalPut(NANOPOOL_ADDRESS_KEY, nanopool_address.value()),
        # Store asset ID in global variable and opt in to assets
        App.globalPut(NANOPOOL_ASSET_1_ID_KEY, Txn.assets[0]),
        optIn(Txn.assets[0]),
        App.globalPut(NANOPOOL_ASSET_2_ID_KEY, Txn.assets[1]),
        optIn(Txn.assets[1]),
        App.globalPut(NANOPOOL_LP_ID_KEY, Txn.assets[2]),
        optIn(Txn.assets[2]),
        App.globalPut(META_ASSET_ID_KEY, Txn.assets[3]),
        optIn(Txn.assets[3]),
        # Store Pool configuration
        App.globalPut(FEE_BPS_KEY, Btoi(Txn.application_args[1])),
        App.globalPut(MIN_INCREMENT_KEY, Btoi(Txn.application_args[2])),
        # Intitialize Pool LP token
        createPoolToken(POOL_TOKEN_DEFAULT_AMOUNT),
        Approve(),
    )


token_a_holding = AssetHolding.balance(
    Global.current_application_address(), App.globalGet(META_ASSET_ID_KEY)
)
token_b_holding = AssetHolding.balance(
    Global.current_application_address(), App.globalGet(NANOPOOL_LP_ID_KEY)
)


def get_add_liquidity_program():
    token_a_txn_index = Int(0)
    token_b_txn_index = Int(1)
    app_call_txn_index = Int(2)

    pool_token_holding = AssetHolding.balance(
        Global.current_application_address(), App.globalGet(META_LP_ID_KEY)
    )

    token_a_before_txn: ScratchVar = ScratchVar(TealType.uint64)
    token_b_before_txn: ScratchVar = ScratchVar(TealType.uint64)

    return Seq(
        check_self(Int(3), app_call_txn_index),
        check_rekey_zero(3),
        pool_token_holding,
        token_a_holding,
        token_b_holding,
        Assert(
            And(
                pool_token_holding.hasValue(),
                pool_token_holding.value() > Int(0),
                validateTokenReceived(
                    token_a_txn_index, App.globalGet(META_ASSET_ID_KEY)
                ),
                validateTokenReceived(
                    token_b_txn_index, App.globalGet(NANOPOOL_LP_ID_KEY)
                ),
                Gtxn[token_a_txn_index].asset_amount()
                >= App.globalGet(MIN_INCREMENT_KEY),
                Gtxn[token_b_txn_index].asset_amount()
                >= App.globalGet(MIN_INCREMENT_KEY),
                Gtxn[app_call_txn_index].assets.length() == Int(3),
            )
        ),
        token_a_before_txn.store(
            token_a_holding.value() - Gtxn[token_a_txn_index].asset_amount()
        ),
        token_b_before_txn.store(
            token_b_holding.value() - Gtxn[token_b_txn_index].asset_amount()
        ),
        If(
            Or(
                token_a_before_txn.load() == Int(0),
                token_b_before_txn.load() == Int(0),
            )
        )
        .Then(
            # no liquidity yet, take everything
            Seq(
                mintAndSendPoolToken(
                    Txn.sender(),
                    Sqrt(
                        Gtxn[token_a_txn_index].asset_amount()
                        * Gtxn[token_b_txn_index].asset_amount()
                    ),
                ),
                Approve(),
            ),
        )
        .ElseIf(
            tryTakeAdjustedAmounts(
                Gtxn[token_a_txn_index].asset_amount(),
                token_a_before_txn.load(),
                App.globalGet(NANOPOOL_LP_ID_KEY),
                Gtxn[token_b_txn_index].asset_amount(),
                token_b_before_txn.load(),
            )
        )
        .Then(Approve())
        .ElseIf(
            tryTakeAdjustedAmounts(
                Gtxn[token_b_txn_index].asset_amount(),
                token_b_before_txn.load(),
                App.globalGet(META_ASSET_ID_KEY),
                Gtxn[token_a_txn_index].asset_amount(),
                token_a_before_txn.load(),
            ),
        )
        .Then(Approve())
        .Else(Reject()),
    )


def get_withdraw_program():
    pool_token_txn_index = Int(0)
    app_call_txn_index = Int(1)

    return Seq(
        check_self(Int(2), app_call_txn_index),
        check_rekey_zero(2),
        token_a_holding,
        token_b_holding,
        Assert(
            And(
                token_a_holding.hasValue(),
                token_a_holding.value() > Int(0),
                token_b_holding.hasValue(),
                token_b_holding.value() > Int(0),
                validateTokenReceived(
                    pool_token_txn_index, App.globalGet(META_LP_ID_KEY)
                ),
                Gtxn[app_call_txn_index].assets.length() == Int(3),
            )
        ),
        withdrawGivenPoolToken(
            Txn.sender(),
            App.globalGet(META_ASSET_ID_KEY),
            Gtxn[pool_token_txn_index].asset_amount(),
            App.globalGet(POOL_TOKENS_OUTSTANDING_KEY),
        ),
        withdrawGivenPoolToken(
            Txn.sender(),
            App.globalGet(NANOPOOL_LP_ID_KEY),
            Gtxn[pool_token_txn_index].asset_amount(),
            App.globalGet(POOL_TOKENS_OUTSTANDING_KEY),
        ),
        App.globalPut(
            POOL_TOKENS_OUTSTANDING_KEY,
            App.globalGet(POOL_TOKENS_OUTSTANDING_KEY)
            - Gtxn[pool_token_txn_index].asset_amount(),
        ),
        Approve(),
    )


def get_metaswap_program():
    in_swap_txn_index = Int(0)
    app_call_txn_index = Int(1)
    token_b_before = ScratchVar(TealType.uint64)
    out_swap_amount = ScratchVar(TealType.uint64)

    return Seq(
        check_self(Int(2), app_call_txn_index),
        check_rekey_zero(2),
        Assert(
            And(
                App.globalGet(POOL_TOKENS_OUTSTANDING_KEY) > Int(0),
                # validateAppCall(app_call_txn_index, in_swap_txn_index),
                validateTokenReceived(
                    in_swap_txn_index, Gtxn[app_call_txn_index].assets[0]
                ),
            ),
        ),
        If(Gtxn[in_swap_txn_index].xfer_asset() == App.globalGet(META_ASSET_ID_KEY))
        .Then(
            Seq(
                token_b_before.store(asset_balance(Gtxn[app_call_txn_index].assets[3])),
                # Compute how many LP asset to swap for
                out_swap_amount.store(
                    computeOtherTokenOutputPerGivenTokenInput(
                        Gtxn[in_swap_txn_index].asset_amount(),
                        asset_balance(Gtxn[app_call_txn_index].assets[0])
                        - Gtxn[in_swap_txn_index].asset_amount(),
                        token_b_before.load(),
                    ),
                ),
                Assert(
                    And(
                        out_swap_amount.load() > Int(0),
                        out_swap_amount.load() < token_b_before.load(),
                    ),
                ),
                # Burn the nanopool LP for the desired asset
                nanoburn(out_swap_amount.load(), Gtxn[app_call_txn_index].assets[1]),
            ),
        )
        .ElseIf(
            Or(
                Gtxn[in_swap_txn_index].xfer_asset()
                == App.globalGet(NANOPOOL_ASSET_1_ID_KEY),
                Gtxn[in_swap_txn_index].xfer_asset()
                == App.globalGet(NANOPOOL_ASSET_2_ID_KEY),
            ),
        )
        .Then(
            Seq(
                token_b_before.store(asset_balance(Gtxn[app_call_txn_index].assets[3])),
                # Zap the asset to the LP token in one step, use that amount to compute the output
                nanozap(app_call_txn_index),
                out_swap_amount.store(
                    computeOtherTokenOutputPerGivenTokenInput(
                        asset_balance(Gtxn[app_call_txn_index].assets[3])
                        - token_b_before.load(),
                        token_b_before.load(),
                        asset_balance(Gtxn[app_call_txn_index].assets[1]),
                    ),
                ),
                Assert(
                    And(
                        out_swap_amount.load() > Int(0),
                        out_swap_amount.load()
                        < asset_balance(Gtxn[app_call_txn_index].assets[1]),
                    ),
                ),
                sendToken(
                    Gtxn[app_call_txn_index].assets[1],
                    Txn.sender(),
                    out_swap_amount.load(),
                ),
            ),
        )
        .Else(Reject()),
        Approve(),
    )


def approval():
    # Initial Sequence
    on_creation = Seq(
        Assert(Txn.application_args.length() == Int(0)),
        App.globalPut(NANOPOOL_APP_ID_KEY, Int(0)),
        App.globalPut(NANOPOOL_MANAGER_ID_KEY, Int(0)),
        App.globalPut(NANOPOOL_ASSET_1_ID_KEY, Int(0)),
        App.globalPut(NANOPOOL_ASSET_2_ID_KEY, Int(0)),
        App.globalPut(NANOPOOL_LP_ID_KEY, Int(0)),
        App.globalPut(META_ASSET_ID_KEY, Int(0)),
        App.globalPut(NANOPOOL_ADDRESS_KEY, Bytes("")),
        App.globalPut(FEE_BPS_KEY, Int(0)),
        App.globalPut(MIN_INCREMENT_KEY, Int(0)),
        App.globalPut(POOL_TOKENS_OUTSTANDING_KEY, Int(0)),
        Approve(),
    )

    is_contract_admin = Seq(
        Assert(Txn.sender() == Global.creator_address()),
        Approve(),
    )

    on_delete = Seq(
        If(App.globalGet(POOL_TOKENS_OUTSTANDING_KEY) == Int(0))
        .Then(is_contract_admin)
        .Else(Reject()),
    )

    on_swap = get_metaswap_program()
    on_setup = get_setup_program()
    on_supply = get_add_liquidity_program()
    on_withdraw = get_withdraw_program()
    on_call_method = Txn.application_args[0]
    on_call = Seq(
        Cond(
            [on_call_method == OP_METASWAP, on_swap],
            [on_call_method == OP_ADD_LIQUIDITY, on_supply],
            [on_call_method == OP_WITHDRAW, on_withdraw],
            [on_call_method == OP_SET_METAPOOL, on_setup],
        ),
        Reject(),
    )

    return event(
        init=on_creation,
        delete=on_delete,
        update=is_contract_admin,
        opt_in=Reject(),
        close_out=Reject(),
        no_op=on_call,
    )


def clear():
    return Approve()


if __name__ == "__main__":
    with open("metapool_approval.teal", "w") as f:
        compiled = compileTeal(
            approval(), mode=Mode.Application, version=MAX_TEAL_VERSION
        )
        f.write(compiled)

    with open("clear_state.teal", "w") as f:
        compiled = compileTeal(clear(), mode=Mode.Application, version=MAX_TEAL_VERSION)
        f.write(compiled)
