from metapool.contracts.poolKeys import *
from pyteal import *
from pyteal.ast import *
from algofi_amm.contract_strings import algofi_pool_strings


@Subroutine(TealType.none)
def nanoswap(asset_in, amount, asset_out) -> Expr:
    """
    Inner Transaction call to the nanoswap pool
    """
    return Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                # Asset Transfer to the Nanoswap pool
                TxnField.type_enum: TxnType.AssetTransfer,
                TxnField.xfer_asset: asset_in,
                TxnField.asset_receiver: App.globalGet(NANOPOOL_ADDRESS_KEY),
                TxnField.asset_amount: amount,
            }
        ),
        InnerTxnBuilder.Next(),
        InnerTxnBuilder.SetFields(
            {
                # Nanoswap pool call
                TxnField.type_enum: TxnType.ApplicationCall,
                TxnField.application_id: App.globalGet(NANOPOOL_APP_ID_KEY),
                TxnField.on_completion: OnComplete.NoOp,
                TxnField.application_args: [
                    Bytes(algofi_pool_strings.swap_exact_for),
                    Itob(Int(0)),
                ],  # Slippage arg
                TxnField.applications: [
                    App.globalGet(NANOPOOL_MANAGER_ID_KEY)
                ],  # Manager application ID in foreign apps field
                TxnField.assets: [asset_out],  # asset to receive in foreign assets
                TxnField.note: Itob(Global.latest_timestamp() * Int(1000000)),
                TxnField.fee: Int(4000),  # Fee is imposed by the nanopool contract
            }
        ),
        InnerTxnBuilder.Submit(),
    )


def nanoburn(burn_amount, desired_asset) -> Expr:
    """
    Inner Transaction call to burn the nanopool LP token
    then swap for the desired asset via a second contract call to the nanopool.
    returns the desired asset to the transaction sender
    """
    receive_balance_ass1 = ScratchVar(TealType.uint64)
    receive_balance_ass2 = ScratchVar(TealType.uint64)

    return Seq(
        # Burn the nanopool LP
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                # LP Asset Transfer to the Nanoswap pool
                TxnField.type_enum: TxnType.AssetTransfer,
                TxnField.xfer_asset: App.globalGet(NANOPOOL_LP_ID_KEY),
                TxnField.asset_receiver: App.globalGet(NANOPOOL_ADDRESS_KEY),
                TxnField.asset_amount: burn_amount,
            }
        ),
        InnerTxnBuilder.Next(),
        InnerTxnBuilder.SetFields(
            {
                # Nanoswap pool call
                TxnField.type_enum: TxnType.ApplicationCall,
                TxnField.application_id: App.globalGet(NANOPOOL_APP_ID_KEY),
                TxnField.on_completion: OnComplete.NoOp,
                TxnField.application_args: [Bytes(algofi_pool_strings.burn_asset1_out)],
                TxnField.assets: [App.globalGet(NANOPOOL_ASSET_1_ID_KEY)],
                TxnField.note: Itob(Global.latest_timestamp() * Int(1000000)),
            }
        ),
        InnerTxnBuilder.Next(),
        InnerTxnBuilder.SetFields(
            {
                # Nanoswap pool call
                TxnField.type_enum: TxnType.ApplicationCall,
                TxnField.application_id: App.globalGet(NANOPOOL_APP_ID_KEY),
                TxnField.on_completion: OnComplete.NoOp,
                TxnField.application_args: [Bytes(algofi_pool_strings.burn_asset2_out)],
                TxnField.assets: [App.globalGet(NANOPOOL_ASSET_2_ID_KEY)],
                TxnField.note: Itob(Global.latest_timestamp() * Int(1000000)),
            }
        ),
        InnerTxnBuilder.Submit(),
        # Assert that the nanoswap pool has send us back the expected assets.
        receive_balance_ass1.store(
            asset_balance(App.globalGet(NANOPOOL_ASSET_1_ID_KEY))
        ),
        receive_balance_ass2.store(
            asset_balance(App.globalGet(NANOPOOL_ASSET_2_ID_KEY))
        ),
        Assert(
            And(
                receive_balance_ass1.load() > Int(0),
                receive_balance_ass2.load() > Int(0),
            ),
        ),
        # Swap the asset for the desired. Inner Transaction call to the nanoswap pool.
        If(desired_asset == App.globalGet(NANOPOOL_ASSET_1_ID_KEY))
        .Then(
            Seq(
                nanoswap(
                    App.globalGet(NANOPOOL_ASSET_2_ID_KEY),
                    receive_balance_ass2.load(),
                    App.globalGet(NANOPOOL_ASSET_1_ID_KEY),
                ),
                receive_balance_ass1.store(
                    asset_balance(App.globalGet(NANOPOOL_ASSET_1_ID_KEY))
                ),
                receive_balance_ass2.store(
                    asset_balance(App.globalGet(NANOPOOL_ASSET_2_ID_KEY))
                ),
            ),
        )
        .ElseIf(desired_asset == App.globalGet(NANOPOOL_ASSET_2_ID_KEY))
        .Then(
            Seq(
                nanoswap(
                    App.globalGet(NANOPOOL_ASSET_1_ID_KEY),
                    receive_balance_ass1.load(),
                    App.globalGet(NANOPOOL_ASSET_2_ID_KEY),
                ),
                receive_balance_ass1.store(
                    asset_balance(App.globalGet(NANOPOOL_ASSET_2_ID_KEY))
                ),
                receive_balance_ass2.store(
                    asset_balance(App.globalGet(NANOPOOL_ASSET_1_ID_KEY))
                ),
            ),
        )
        .Else(Reject()),
        # Assert that the nanoswap pool has send us back the expected assed
        Assert(
            And(
                receive_balance_ass1.load() > Int(0),
                receive_balance_ass2.load() == Int(0),
            ),
        ),
        # Return the asset to papa
        sendToken(desired_asset, Txn.sender(), receive_balance_ass1.load()),
    )


def nanozap(app_call_txn_index):
    """
    Inner transaction call to the nanopool to zap the input asset by
    first calling the nanopool swap to obtain the correct ratio to
    pool the 2 nanopool asset for LP token.
    returns any residual to the sender.
    """
    return Seq(
        # Swap for the second asset
        nanoswap(
            Gtxn[app_call_txn_index].assets[0],
            Btoi(Gtxn[app_call_txn_index].application_args[1]),
            Gtxn[app_call_txn_index].assets[2],
        ),
        # Add liquidity to the nanopool
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                # Asset Transfer to the Nanoswap pool
                TxnField.type_enum: TxnType.AssetTransfer,
                TxnField.xfer_asset: App.globalGet(NANOPOOL_ASSET_1_ID_KEY),
                TxnField.asset_receiver: Gtxn[app_call_txn_index].accounts[
                    1
                ],  # Nanopool Address
                TxnField.asset_amount: asset_balance(
                    App.globalGet(NANOPOOL_ASSET_1_ID_KEY)
                ),
            }
        ),
        InnerTxnBuilder.Next(),
        InnerTxnBuilder.SetFields(
            {
                # Asset Transfer to the Nanoswap pool
                TxnField.type_enum: TxnType.AssetTransfer,
                TxnField.xfer_asset: App.globalGet(NANOPOOL_ASSET_2_ID_KEY),
                TxnField.asset_receiver: Gtxn[app_call_txn_index].accounts[
                    1
                ],  # Nanopool Address
                TxnField.asset_amount: asset_balance(
                    App.globalGet(NANOPOOL_ASSET_2_ID_KEY)
                ),
            }
        ),
        InnerTxnBuilder.Next(),
        InnerTxnBuilder.SetFields(
            {
                # Nanoswap pool call
                TxnField.type_enum: TxnType.ApplicationCall,
                TxnField.application_id: Gtxn[app_call_txn_index].applications[
                    1
                ],  # Nanopool Application ID
                TxnField.on_completion: OnComplete.NoOp,
                TxnField.fee: Int(4000),  # Fee Imposed by nanopool contract
                TxnField.application_args: [
                    Bytes(algofi_pool_strings.pool),
                    Itob(Int(10000)),
                ],  # Slippage Arg
                TxnField.applications: [
                    Gtxn[app_call_txn_index].applications[2]
                ],  # Manager application ID in foreign apps field
                TxnField.assets: [
                    Gtxn[app_call_txn_index].assets[3]
                ],  # LP token asset ID in foreign assets
                TxnField.note: Itob(Global.latest_timestamp() * Int(1000000)),
            }
        ),
        InnerTxnBuilder.Next(),
        InnerTxnBuilder.SetFields(
            {
                # Nanoswap redeem residual
                TxnField.type_enum: TxnType.ApplicationCall,
                TxnField.application_id: Gtxn[app_call_txn_index].applications[
                    1
                ],  # Nanopool Application ID
                TxnField.on_completion: OnComplete.NoOp,
                TxnField.application_args: [
                    Bytes(algofi_pool_strings.redeem_pool_asset1_residual)
                ],
                TxnField.assets: [App.globalGet(NANOPOOL_ASSET_1_ID_KEY)],
                TxnField.note: Itob(Global.latest_timestamp() * Int(1000000)),
            }
        ),
        InnerTxnBuilder.Next(),
        InnerTxnBuilder.SetFields(
            {
                # Nanoswap redeem residual
                TxnField.type_enum: TxnType.ApplicationCall,
                TxnField.application_id: Gtxn[app_call_txn_index].applications[
                    1
                ],  # Nanopool Application ID
                TxnField.on_completion: OnComplete.NoOp,
                TxnField.application_args: [
                    Bytes(algofi_pool_strings.redeem_pool_asset2_residual)
                ],
                TxnField.assets: [App.globalGet(NANOPOOL_ASSET_2_ID_KEY)],
                TxnField.note: Itob(Global.latest_timestamp() * Int(1000000)),
            }
        ),
        InnerTxnBuilder.Submit(),
        # Return the asset to papa
        If(asset_balance(Gtxn[app_call_txn_index].assets[0]) > Int(0)).Then(
            sendToken(
                Gtxn[app_call_txn_index].assets[0],
                Txn.sender(),
                asset_balance(Gtxn[app_call_txn_index].assets[0]),
            )
        ),
        If(asset_balance(Gtxn[app_call_txn_index].assets[2]) > Int(0)).Then(
            sendToken(
                Gtxn[app_call_txn_index].assets[2],
                Txn.sender(),
                asset_balance(Gtxn[app_call_txn_index].assets[2]),
            )
        ),
    )


def validateAppCall(app_call_txn_index, in_swap_txn_index) -> Expr:
    """
    Validate the application call by comparing the transaction arguments to the global stored value
    """
    return And(
        # Enough Fee Passed
        Gtxn[app_call_txn_index].fee() >= Int(6) * Global.min_txn_fee(),
        # Validate applications
        Gtxn[app_call_txn_index].application_id() == Global.current_application_id(),
        Gtxn[app_call_txn_index].applications.length() == Int(2),
        Gtxn[app_call_txn_index].applications[1] == App.globalGet(NANOPOOL_APP_ID_KEY),
        Gtxn[app_call_txn_index].applications[2]
        == App.globalGet(NANOPOOL_MANAGER_ID_KEY),
        Gtxn[app_call_txn_index].accounts.length() == Int(1),
        Gtxn[app_call_txn_index].accounts[1] == App.globalGet(NANOPOOL_ADDRESS_KEY),
        # Validate assets
        Gtxn[app_call_txn_index].assets.length() == Int(4),
        Gtxn[app_call_txn_index].assets[0] == Gtxn[in_swap_txn_index].xfer_asset(),
        Or(
            And(
                Gtxn[app_call_txn_index].assets[0] == App.globalGet(META_ASSET_ID_KEY),
                Or(
                    And(
                        Gtxn[app_call_txn_index].assets[1]
                        == App.globalGet(NANOPOOL_ASSET_1_ID_KEY),
                        Gtxn[app_call_txn_index].assets[2]
                        == App.globalGet(NANOPOOL_ASSET_2_ID_KEY),
                    ),
                    And(
                        Gtxn[app_call_txn_index].assets[1]
                        == App.globalGet(NANOPOOL_ASSET_2_ID_KEY),
                        Gtxn[app_call_txn_index].assets[2]
                        == App.globalGet(NANOPOOL_ASSET_1_ID_KEY),
                    ),
                ),
            ),
            And(
                Gtxn[app_call_txn_index].assets[0]
                == App.globalGet(NANOPOOL_ASSET_1_ID_KEY),
                Gtxn[app_call_txn_index].assets[1] == App.globalGet(META_ASSET_ID_KEY),
                Gtxn[app_call_txn_index].assets[2]
                == App.globalGet(NANOPOOL_ASSET_2_ID_KEY),
            ),
            And(
                Gtxn[app_call_txn_index].assets[0]
                == App.globalGet(NANOPOOL_ASSET_2_ID_KEY),
                Gtxn[app_call_txn_index].assets[1] == App.globalGet(META_ASSET_ID_KEY),
                Gtxn[app_call_txn_index].assets[2]
                == App.globalGet(NANOPOOL_ASSET_1_ID_KEY),
            ),
        ),
        Gtxn[app_call_txn_index].assets[3] == App.globalGet(NANOPOOL_LP_ID_KEY),
    )


def event(
    init: Expr = Reject(),
    delete: Expr = Reject(),
    update: Expr = Reject(),
    opt_in: Expr = Reject(),
    close_out: Expr = Reject(),
    no_op: Expr = Reject(),
) -> Expr:
    return Cond(
        [Txn.application_id() == Int(0), init],
        [Txn.on_completion() == OnComplete.DeleteApplication, delete],
        [Txn.on_completion() == OnComplete.UpdateApplication, update],
        [Txn.on_completion() == OnComplete.OptIn, opt_in],
        [Txn.on_completion() == OnComplete.CloseOut, close_out],
        [Txn.on_completion() == OnComplete.NoOp, no_op],
    )


def check_rekey_zero(num_transactions: int):
    return Assert(
        And(
            *[
                Gtxn[i].rekey_to() == Global.zero_address()
                for i in range(num_transactions)
            ]
        )
    )


@Subroutine(TealType.none)
def check_self(
    group_size,
    group_index,
):
    return Assert(
        And(
            Global.group_size() == group_size,
            Txn.group_index() == group_index,
        )
    )


@Subroutine(TealType.uint64)
def asset_balance(asset_id):
    AssetBalance = AssetHolding.balance(Global.current_application_address(), asset_id)
    return Seq(
        AssetBalance,
        Return(AssetBalance.value()),
    )


@Subroutine(TealType.none)
def sendToken(token_id, receiver, amount) -> Expr:
    return Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.AssetTransfer,
                TxnField.xfer_asset: token_id,
                TxnField.asset_receiver: receiver,
                TxnField.asset_amount: amount,
            }
        ),
        InnerTxnBuilder.Submit(),
    )


def createPoolToken(pool_token_amount) -> Expr:
    return Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.AssetConfig,
                TxnField.config_asset_total: pool_token_amount,
                TxnField.config_asset_default_frozen: Int(0),
                TxnField.config_asset_decimals: Int(0),
                TxnField.config_asset_reserve: Global.current_application_address(),
            }
        ),
        InnerTxnBuilder.Submit(),
        App.globalPut(META_LP_ID_KEY, InnerTxn.created_asset_id()),
    )


@Subroutine(TealType.none)
def optIn(token_id) -> Expr:
    return sendToken(token_id, Global.current_application_address(), Int(0))


@Subroutine(TealType.uint64)
def validateTokenReceived(transaction_index, asset_id) -> Expr:
    return And(
        Gtxn[transaction_index].type_enum() == TxnType.AssetTransfer,
        Gtxn[transaction_index].sender() == Txn.sender(),
        Gtxn[transaction_index].asset_receiver()
        == Global.current_application_address(),
        Gtxn[transaction_index].xfer_asset() == asset_id,
        Gtxn[transaction_index].asset_amount() > Int(0),
        Gtxn[transaction_index].close_remainder_to() == Global.zero_address(),
    )


@Subroutine(TealType.none)
def mintAndSendPoolToken(receiver, amount) -> Expr:
    return Seq(
        sendToken(App.globalGet(META_LP_ID_KEY), receiver, amount),
        App.globalPut(
            POOL_TOKENS_OUTSTANDING_KEY,
            App.globalGet(POOL_TOKENS_OUTSTANDING_KEY) + amount,
        ),
    )


@Subroutine(TealType.uint64)
def xMulYDivZ(x, y, z) -> Expr:
    return WideRatio([x, y, SCALING_FACTOR], [z, SCALING_FACTOR])


@Subroutine(TealType.none)
def returnRemainder(token_id, received_amount, to_keep_amount) -> Expr:
    remainder = received_amount - to_keep_amount
    return Seq(
        If(remainder > Int(0)).Then(
            sendToken(
                token_id,
                Txn.sender(),
                remainder,
            )
        ),
    )


@Subroutine(TealType.uint64)
def tryTakeAdjustedAmounts(
    to_keep_token_txn_amt,
    to_keep_token_before_txn_amt,
    other_token_id,
    other_token_txn_amt,
    other_token_before_txn_amt,
) -> Expr:
    """
    Given supplied token amounts, try to keep all of one token and the corresponding amount of other token
    as determined by market price before transaction. If corresponding amount is less than supplied, send the remainder back.
    If successful, mint and sent pool tokens in proportion to new liquidity over old liquidity.
    """
    other_corresponding_amount = ScratchVar(TealType.uint64)

    return Seq(
        other_corresponding_amount.store(
            xMulYDivZ(
                to_keep_token_txn_amt,
                other_token_before_txn_amt,
                to_keep_token_before_txn_amt,
            )
        ),
        If(
            And(
                other_corresponding_amount.load() > Int(0),
                other_token_txn_amt >= other_corresponding_amount.load(),
            )
        ).Then(
            Seq(
                returnRemainder(
                    other_token_id,
                    other_token_txn_amt,
                    other_corresponding_amount.load(),
                ),
                mintAndSendPoolToken(
                    Txn.sender(),
                    xMulYDivZ(
                        App.globalGet(POOL_TOKENS_OUTSTANDING_KEY),
                        to_keep_token_txn_amt,
                        to_keep_token_before_txn_amt,
                    ),
                ),
                Return(Int(1)),
            )
        ),
        Return(Int(0)),
    )


@Subroutine(TealType.none)
def withdrawGivenPoolToken(
    receiver,
    to_withdraw_token_id,
    pool_token_amount,
    pool_tokens_outstanding,
) -> Expr:
    token_holding = AssetHolding.balance(
        Global.current_application_address(), to_withdraw_token_id
    )
    return Seq(
        token_holding,
        If(
            And(
                pool_tokens_outstanding > Int(0),
                pool_token_amount > Int(0),
                token_holding.hasValue(),
                token_holding.value() > Int(0),
            )
        ).Then(
            Seq(
                Assert(
                    xMulYDivZ(
                        token_holding.value(),
                        pool_token_amount,
                        pool_tokens_outstanding,
                    )
                    > Int(0)
                ),
                sendToken(
                    to_withdraw_token_id,
                    receiver,
                    xMulYDivZ(
                        token_holding.value(),
                        pool_token_amount,
                        pool_tokens_outstanding,
                    ),
                ),
            )
        ),
    )


@Subroutine(TealType.uint64)
def assessFee(amount):
    fee_num = Int(10000) - App.globalGet(FEE_BPS_KEY)
    fee_denom = Int(10000)
    return xMulYDivZ(amount, fee_num, fee_denom)


@Subroutine(TealType.uint64)
def computeOtherTokenOutputPerGivenTokenInput(
    input_amount,
    previous_given_token_amount,
    previous_other_token_amount,
):
    k = previous_given_token_amount * previous_other_token_amount
    amount_sub_fee = assessFee(input_amount)
    to_send = previous_other_token_amount - k / (
        previous_given_token_amount + amount_sub_fee
    )
    return to_send
