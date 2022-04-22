from .utils import MIN_BALANCE_REQUIREMENT, compiledContract, getPoolTokenId, Account
from .contracts.poolKeys import metapool_strings
from algofi_amm.v0.client import AlgofiAMMClient
from algofi_amm.v0.pool import Pool
from algofi_amm.v0.config import PoolType
from algofi_amm.utils import (
    int_to_bytes,
    wait_for_confirmation,
    get_application_global_state,
    get_account_balances,
    get_payment_txn,
)
from algosdk.future import transaction
from algosdk.logic import get_application_address
from algosdk.encoding import msgpack_encode
from algosdk import constants
from base64 import b64decode


class MetapoolAMMClient:
    def __init__(
        self,
        client: AlgofiAMMClient,
        nanopool: Pool,
        metaAssetID: int,
        metapoolAppID=None,
    ):
        """Constructor method for :class:`MetapoolAMMClient`
        Args:
            client: An Algofi AMM Client.
            nanopool: Algofi AMM nanopool Pool object.
            metaAssetID: The asset ID of other meta asset to be traded against the nanopool.
            metapoolAppID: Application ID of the metapool, leave none for a new pool.
        """

        self.client = client
        if metapoolAppID:
            self.metapool_application_id = metapoolAppID
            self.metapool_lp_asset_id = getPoolTokenId(
                get_application_global_state(self.client.indexer, metapoolAppID)
            )
            self.metapool_address = get_application_address(metapoolAppID)
        self.nanopool = nanopool
        self.meta_asset_id = metaAssetID

    @classmethod
    def fromMetapoolId(cls, client: AlgofiAMMClient, metapoolAppID: int):
        """Alternative constructor for class MetapoolAMMClient.
        Load the pool arguments from the app global state
        Args:
            client: An Algofi AMM Client.
            metapoolAppID: Application ID of the metapool,
        """
        appGlobalState = get_application_global_state(client.indexer, metapoolAppID)
        try:
            nanopool = client.get_pool(
                PoolType.NANOSWAP,
                appGlobalState[metapool_strings.nanopool_asset_1_id],
                appGlobalState[metapool_strings.nanopool_asset_2_id],
            )
            return cls(
                client,
                nanopool,
                appGlobalState[metapool_strings.meta_asset_id],
                metapoolAppID,
            )
        except KeyError:
            raise RuntimeError("Make sure the metapool app has been set up")

    def createMetapool(self, user: Account) -> int:
        """Create a new metapool amm.
        Args:
            user: Creator Account
        Returns:
            The app ID of the newly created metapool amm.
        """

        global_schema = transaction.StateSchema(num_uints=10, num_byte_slices=1)
        local_schema = transaction.StateSchema(num_uints=0, num_byte_slices=0)
        approval_program, clear_program = compiledContract(self.client.algod)

        create_txn = transaction.ApplicationCreateTxn(
            sender=user.getAddress(),
            sp=self.client.algod.suggested_params(),
            on_complete=transaction.OnComplete.NoOpOC,
            approval_program=approval_program,
            clear_program=clear_program,
            global_schema=global_schema,
            local_schema=local_schema,
            extra_pages=1,
        )

        s_create_txn = create_txn.sign(user.getPrivateKey())
        # Send the transaction to the network and retrieve the txid.
        txid = self.client.algod.send_transaction(s_create_txn)

        # Wait for the transaction to be confirmed
        response = wait_for_confirmation(self.client.algod, txid)
        metapool_contract_id = response["application-index"]

        assert metapool_contract_id is not None and metapool_contract_id > 0
        self.metapool_application_id = metapool_contract_id
        self.metapool_address = get_application_address(self.metapool_application_id)
        return metapool_contract_id

    def setupMetapool(self, user: Account, feeBps: int, minIncrement: int) -> int:
        """Finish setting up a metapool amm.

        This operation funds the pool account, creates pool token,
        and opts app into tokens A and B, as well as both nanopool asset
        all in one atomic transaction group.
        The arguments passed to the app call and in the foreign assets and foreign apps fields
        are saved as global contract variables.

        Args:
            user: Creator Account
            feeBps: The basis point fee to be charged per swap
            minIncrement: minimum quantity to add liquidity to the pool
        Return: metapool LP token id
        """
        params = self.client.algod.suggested_params()
        fundingAmount = (
            MIN_BALANCE_REQUIREMENT
            # additional balance to create pool token and opt into assets (4)
            + 1_000 * 5
        )
        app_args = [
            bytes(metapool_strings.op_set_metapool, "utf-8"),
            feeBps.to_bytes(8, "big"),
            minIncrement.to_bytes(8, "big"),
        ]
        assets = [
            self.nanopool.asset1.asset_id,
            self.nanopool.asset2.asset_id,
            self.nanopool.lp_asset_id,
            self.meta_asset_id,
        ]
        applications = [
            self.nanopool.application_id,
            self.nanopool.manager_application_id,
        ]

        fundAppTxn = transaction.PaymentTxn(
            sender=user.getAddress(),
            receiver=self.metapool_address,
            amt=fundingAmount,
            sp=params,
        )

        setupTxn = transaction.ApplicationCallTxn(
            sender=user.getAddress(),
            index=self.metapool_application_id,
            on_complete=transaction.OnComplete.NoOpOC,
            app_args=app_args,
            foreign_assets=assets,
            foreign_apps=applications,
            sp=params,
        )
        # Group Transaction
        transaction.assign_group_id([fundAppTxn, setupTxn])
        # Sign Transaction
        signedFundAppTxn = fundAppTxn.sign(user.getPrivateKey())
        signedSetupTxn = setupTxn.sign(user.getPrivateKey())
        # Send Transaction
        self.client.algod.send_transactions([signedFundAppTxn, signedSetupTxn])
        # Wait for response
        wait_for_confirmation(self.client.algod, signedFundAppTxn.get_txid())
        # Return Pool token ID
        appGlobalState = get_application_global_state(
            self.client.indexer, self.metapool_application_id
        )
        metaLPID = appGlobalState[metapool_strings.meta_lp_id]
        self.metapool_lp_asset_id = metaLPID
        return metaLPID

    def add_liquidity(self, user: Account, qA: int, qB: int) -> None:
        """Supply liquidity to the pool.
        Let rA, rB denote the existing pool reserves of token A (meta asset) and token B (nanopool LP) respectively.

        First supplier will receive sqrt(qA*qB) tokens, subsequent suppliers will receive
        qA/rA where rA is the amount of token A already in the pool.
        If qA/qB != rA/rB, the pool will first attempt to take full amount qA, returning excess token B.
        Else if there is insufficient amount qB, the pool will then attempt to take the full amount qB, returning
        excess token A.
        Else transaction will be rejected.

        Args:
            user: user Account
            qA: amount of meta asset to supply the pool.
            qB: amount of nanopool LP token to supply to the pool.
        """
        self.assertSetup()
        params = self.client.algod.suggested_params()

        tokenATxn = transaction.AssetTransferTxn(
            sender=user.getAddress(),
            receiver=self.metapool_address,
            index=self.meta_asset_id,
            amt=qA,
            sp=params,
        )
        tokenBTxn = transaction.AssetTransferTxn(
            sender=user.getAddress(),
            receiver=self.metapool_address,
            index=self.nanopool.lp_asset_id,
            amt=qB,
            sp=params,
        )
        # pay for the fee incurred by AMM for sending back the pool token
        params.fee = constants.MIN_TXN_FEE * 3
        params.flat_fee = True
        appCallTxn = transaction.ApplicationCallTxn(
            sender=user.getAddress(),
            index=self.metapool_application_id,
            on_complete=transaction.OnComplete.NoOpOC,
            app_args=[bytes(metapool_strings.op_add_liquidity, "utf-8")],
            foreign_assets=[
                self.meta_asset_id,
                self.nanopool.lp_asset_id,
                self.metapool_lp_asset_id,
            ],
            sp=params,
        )
        transaction.assign_group_id([tokenATxn, tokenBTxn, appCallTxn])
        signedTokenATxn = tokenATxn.sign(user.getPrivateKey())
        signedTokenBTxn = tokenBTxn.sign(user.getPrivateKey())
        signedAppCallTxn = appCallTxn.sign(user.getPrivateKey())

        self.client.algod.send_transactions(
            [signedTokenATxn, signedTokenBTxn, signedAppCallTxn]
        )
        wait_for_confirmation(self.client.algod, signedAppCallTxn.get_txid())

    def withdraw(self, user: Account, poolTokenAmount: int) -> None:
        """Withdraw liquidity  + rewards from the pool back to supplier.
        Supplier should receive tokenA, tokenB + fees proportional to the liquidity share in the pool they choose to withdraw.

        Args:
            user: user Account
            poolTokenAmount: pool token quantity.
        """
        self.assertSetup()
        params = self.client.algod.suggested_params()

        poolTokenTxn = transaction.AssetTransferTxn(
            sender=user.getAddress(),
            receiver=self.metapool_address,
            index=self.metapool_lp_asset_id,
            amt=poolTokenAmount,
            sp=params,
        )
        # pay for the fee incurred by AMM for sending back the tokens
        params.fee = constants.MIN_TXN_FEE * 3
        params.flat_fee = True
        appCallTxn = transaction.ApplicationCallTxn(
            sender=user.getAddress(),
            index=self.metapool_application_id,
            on_complete=transaction.OnComplete.NoOpOC,
            app_args=[bytes(metapool_strings.op_withdraw, "utf-8")],
            foreign_assets=[
                self.meta_asset_id,
                self.nanopool.lp_asset_id,
                self.metapool_lp_asset_id,
            ],
            sp=params,
        )

        transaction.assign_group_id([poolTokenTxn, appCallTxn])
        signedPoolTokenTxn = poolTokenTxn.sign(user.getPrivateKey())
        signedAppCallTxn = appCallTxn.sign(user.getPrivateKey())

        self.client.algod.send_transactions([signedPoolTokenTxn, signedAppCallTxn])
        wait_for_confirmation(self.client.algod, signedAppCallTxn.get_txid())

    def metaswap(self, user: Account, inTokenId: int, amount: int, outTokenId: int):
        """Swap tokenId token for the outTokenId in the pool. If the in token is the meta-asset, then the out token can be one of the nanopool assets pair.
        If the nanopool asset is the in token, then the meta-asset must be out token.
        This action can only happen if there is liquidity in the pool
        A fee (in bps, configured on app creation) is taken out of the input amount before calculating the output amount
        Args:
            user: user Account
            inTokenId: asset Id of the token to swap, must be either meta-asset or one of the nanopool pair
            amount: amount to swap.
            outTokenId: asset if of the token to receive.
        """
        self.assertSetup()
        params = self.client.algod.suggested_params()
        app_args = [bytes(metapool_strings.op_metaswap, "utf-8")]
        # Verify that we have the correct assets pair
        if (
            inTokenId == self.nanopool.asset1.asset_id
            or inTokenId == self.nanopool.asset2.asset_id
        ):
            assert outTokenId == self.meta_asset_id, "Invalid Output token"
            # Small amounts have difficulty going through the zap
            niggle = 100
            assert amount > niggle, "Swap too little"
            # For the zap operation, we calculate the amount in the client and pass it as an argument to the transaction
            zap_amount = self.get_zap_amount(inTokenId, amount)
            app_args.append(int_to_bytes(int(zap_amount)))
        if inTokenId == self.nanopool.asset1.asset_id:
            other_asset = self.nanopool.asset2.asset_id
        elif inTokenId == self.nanopool.asset2.asset_id:
            other_asset = self.nanopool.asset1.asset_id
        elif inTokenId == self.meta_asset_id:
            if outTokenId == self.nanopool.asset1.asset_id:
                other_asset = self.nanopool.asset2.asset_id
            elif outTokenId == self.nanopool.asset2.asset_id:
                other_asset = self.nanopool.asset1.asset_id
            else:
                raise ValueError("Invalid Output token")
        else:
            raise ValueError("Invalid Input token")
        # Verify the user balance
        assert (
            get_account_balances(self.client.indexer, user.getAddress())[inTokenId]
            > amount
        ), "Not Enough Balance"

        assets = [inTokenId, outTokenId, other_asset, self.nanopool.lp_asset_id]

        inSwapTxn = transaction.AssetTransferTxn(
            sender=user.getAddress(),
            receiver=self.metapool_address,
            index=inTokenId,
            amt=amount,
            sp=params,
        )
        params.fee = constants.MIN_TXN_FEE * 8
        params.flat_fee = True

        appCallTxn = transaction.ApplicationNoOpTxn(
            sender=user.getAddress(),
            sp=params,
            index=self.metapool_application_id,
            app_args=app_args,
            foreign_apps=[
                self.nanopool.application_id,
                self.nanopool.manager_application_id,
            ],
            foreign_assets=assets,
            accounts=[self.nanopool.address],
        )

        transaction.assign_group_id([inSwapTxn, appCallTxn])
        signedInSwapTxn = inSwapTxn.sign(user.getPrivateKey())
        signedAppCallTxn = appCallTxn.sign(user.getPrivateKey())

        self.client.algod.send_transactions([signedInSwapTxn, signedAppCallTxn])
        wait_for_confirmation(self.client.algod, signedAppCallTxn.get_txid())

    def get_zap_amount(self, asset_id, in_swap_amt):
        """Iteratively find the optimal amount to swap in the nanopool such that the resulting balances have the same assets ratio."""
        self.nanopool.refresh_state()
        # First take a best guess that holds true if the exchange ratio is 1:1 (ignoring fees)
        if asset_id == self.nanopool.asset1.asset_id:
            y = (in_swap_amt * self.nanopool.asset2_balance) / (
                self.nanopool.asset1_balance
                + self.nanopool.asset2_balance
                + in_swap_amt
            )
            # sign = 1
        elif asset_id == self.nanopool.asset2.asset_id:
            y = (in_swap_amt * self.nanopool.asset1_balance) / (
                self.nanopool.asset2_balance
                + self.nanopool.asset1_balance
                + in_swap_amt
            )
            # sign = -1

        # Account for the fees on our best guess
        f_y = self.nanopool.get_swap_exact_for_quote(asset_id, y)
        if asset_id == self.nanopool.asset1.asset_id:
            # y = in_swap_amt - (f_y.asset2_delta*(self.nanopool.asset1_balance + in_swap_amt)/self.nanopool.asset2_balance)
            a_b = (self.nanopool.asset1_balance - f_y.asset1_delta) / (
                self.nanopool.asset2_balance - f_y.asset2_delta
            )
            if f_y.asset2_delta == 0:
                return y
            else:
                xmy_fy = (in_swap_amt - y) / (f_y.asset2_delta)
        else:
            # y = in_swap_amt - (f_y.asset1_delta*(self.nanopool.asset2_balance + in_swap_amt)/self.nanopool.asset1_balance)
            a_b = (self.nanopool.asset2_balance - f_y.asset2_delta) / (
                self.nanopool.asset1_balance - f_y.asset1_delta
            )
            if f_y.asset1_delta == 0:
                return y
            else:
                xmy_fy = (in_swap_amt - y) / (f_y.asset1_delta)

        # Iteratively adjust the zap amount y by accounting for the pool price and fees
        MAX_ITERATION = 1_000_000
        i = 1
        are_we_there_yet = 1 - xmy_fy / a_b
        while i < MAX_ITERATION:
            # Check if we succeeded
            # print(y, are_we_there_yet)
            if are_we_there_yet == 0:
                break
            elif are_we_there_yet < 0:
                y = y + 1
            else:
                y = y - 1

            f_y = self.nanopool.get_swap_exact_for_quote(asset_id, y)
            if asset_id == self.nanopool.asset1.asset_id:
                a_b = (self.nanopool.asset1_balance - f_y.asset1_delta) / (
                    self.nanopool.asset2_balance - f_y.asset2_delta
                )
                xmy_fy = (in_swap_amt - y) / (f_y.asset2_delta)
            else:
                a_b = (self.nanopool.asset2_balance - f_y.asset2_delta) / (
                    self.nanopool.asset1_balance - f_y.asset1_delta
                )
                xmy_fy = (in_swap_amt - y) / (f_y.asset1_delta)

            getting_there = are_we_there_yet
            are_we_there_yet = 1 - xmy_fy / a_b
            if getting_there * are_we_there_yet < 0:
                # we just cross the best possible ratio
                if are_we_there_yet < 0:
                    y = y + 1
                    break
                else:
                    break

            i += 1

        return y

    def fundMetapool(self, user: Account, amount):
        """Send Algos to the metapool contract to paid for the inner nanoswap transaction fees"""
        fundingTxn = get_payment_txn(
            self.client.algod.suggested_params(),
            user.getAddress(),
            self.metapool_address,
            amount,
        )
        txid = self.client.algod.send_transaction(fundingTxn.sign(user.getPrivateKey()))
        return wait_for_confirmation(self.client.algod, txid)

    def closeMetapool(self, user: Account):
        """Close a metapool.

        This action can only happen if there is no liquidity in the pool (outstanding pool tokens = 0).
        """

        deleteTxn = transaction.ApplicationDeleteTxn(
            sender=user.getAddress(),
            index=self.metapool_application_id,
            sp=self.client.algod.suggested_params(),
        )
        signedDeleteTxn = deleteTxn.sign(user.getPrivateKey())

        self.client.algod.send_transaction(signedDeleteTxn)

        wait_for_confirmation(self.client.algod, signedDeleteTxn.get_txid())

    def assertSetup(self) -> None:
        try:
            balances = get_account_balances(self.client.indexer, self.metapool_address)
            assert balances[1] >= MIN_BALANCE_REQUIREMENT
        except:
            raise Exception("AMM must be set up and funded first.")

    def optInToPoolToken(self, user: Account):
        self.assertSetup()
        appGlobalState = get_application_global_state(
            self.client.indexer, self.metapool_application_id
        )
        poolToken = getPoolTokenId(appGlobalState)

        optInTxn = transaction.AssetOptInTxn(
            sender=user.getAddress(),
            index=poolToken,
            sp=self.client.algod.suggested_params(),
        )

        signedOptInTxn = optInTxn.sign(user.getPrivateKey())

        self.client.algod.send_transaction(signedOptInTxn)
        wait_for_confirmation(self.client.algod, signedOptInTxn.get_txid())

    def metaswap_dryrun(
        self, user: Account, inTokenId: int, amount: int, outTokenId: int
    ):
        """Metaswap operation but it write the transaction context to a dryrun file instead of sending the transaction."""
        self.assertSetup()
        params = self.client.algod.suggested_params()
        app_args = [bytes(metapool_strings.op_metaswap, "utf-8")]
        if (
            inTokenId == self.nanopool.asset1.asset_id
            or inTokenId == self.nanopool.asset2.asset_id
        ):
            assert outTokenId == self.meta_asset_id
            zap_amount = self.get_zap_amount(inTokenId, amount)
            app_args.append(int_to_bytes(int(zap_amount)))
        if inTokenId == self.nanopool.asset1.asset_id:
            other_asset = self.nanopool.asset2.asset_id
        elif inTokenId == self.nanopool.asset2.asset_id:
            other_asset = self.nanopool.asset1.asset_id
        elif inTokenId == self.meta_asset_id:
            if outTokenId == self.nanopool.asset1.asset_id:
                other_asset = self.nanopool.asset2.asset_id
            elif outTokenId == self.nanopool.asset2.asset_id:
                other_asset = self.nanopool.asset1.asset_id
            else:
                raise ValueError("Invalid Output token")
        else:
            raise ValueError("Invalid Input token")
        assets = [inTokenId, outTokenId, other_asset, self.nanopool.lp_asset_id]

        inSwapTxn = transaction.AssetTransferTxn(
            sender=user.getAddress(),
            receiver=self.metapool_address,
            index=inTokenId,
            amt=amount,
            sp=params,
        )
        params.fee = constants.MIN_TXN_FEE * 8
        params.flat_fee = True

        appCallTxn = transaction.ApplicationNoOpTxn(
            sender=user.getAddress(),
            sp=params,
            index=self.metapool_application_id,
            app_args=app_args,
            foreign_apps=[
                self.nanopool.application_id,
                self.nanopool.manager_application_id,
            ],
            foreign_assets=assets,
            accounts=[self.nanopool.address],
        )

        transaction.assign_group_id([inSwapTxn, appCallTxn])
        signedInSwapTxn = inSwapTxn.sign(user.getPrivateKey())
        signedAppCallTxn = appCallTxn.sign(user.getPrivateKey())
        drr = transaction.create_dryrun(
            self.client.algod, [signedInSwapTxn, signedAppCallTxn]
        )
        filename = "dryrun.msgp"
        with open(filename, "wb") as f:
            f.write(b64decode(msgpack_encode(drr)))

    def metaswap_unsafe(
        self, user: Account, inTokenId: int, amount: int, outTokenId: int
    ):
        """Same as meta-swap but it allows to send ill-transaction. For testing only."""
        self.assertSetup()
        params = self.client.algod.suggested_params()
        app_args = [bytes(metapool_strings.op_metaswap, "utf-8")]
        # Verify that we have the correct assets pair
        if (
            inTokenId == self.nanopool.asset1.asset_id
            or inTokenId == self.nanopool.asset2.asset_id
        ):
            # assert outTokenId==self.meta_asset_id, "Invalid Output token"
            # For the zap operation, we calculate the amount in the client and pass it as an argument to the transaction
            zap_amount = self.get_zap_amount(inTokenId, amount)
            app_args.append(int_to_bytes(int(zap_amount)))
            # Small amounts have difficulty going through the zap
            # niggle = 100
            # assert amount > niggle, "Swaped too little"
        if inTokenId == self.nanopool.asset1.asset_id:
            other_asset = self.nanopool.asset2.asset_id
        elif inTokenId == self.nanopool.asset2.asset_id:
            other_asset = self.nanopool.asset1.asset_id
        elif inTokenId == self.meta_asset_id:
            if outTokenId == self.nanopool.asset1.asset_id:
                other_asset = self.nanopool.asset2.asset_id
            elif outTokenId == self.nanopool.asset2.asset_id:
                other_asset = self.nanopool.asset1.asset_id
            else:
                other_asset = self.nanopool.asset2.asset_id
                # raise ValueError("Invalid Output token")
        else:
            other_asset = self.nanopool.asset2.asset_id
            # raise ValueError("Invalid Input token")
        # Verify the user balance
        # assert get_account_balances(self.client.indexer, user.getAddress()[inTokenId]) > amount, ValueError("Not Enough Balance")

        assets = [inTokenId, outTokenId, other_asset, self.nanopool.lp_asset_id]

        inSwapTxn = transaction.AssetTransferTxn(
            sender=user.getAddress(),
            receiver=self.metapool_address,
            index=inTokenId,
            amt=amount,
            sp=params,
        )
        params.fee = constants.MIN_TXN_FEE * 8
        params.flat_fee = True

        appCallTxn = transaction.ApplicationNoOpTxn(
            sender=user.getAddress(),
            sp=params,
            index=self.metapool_application_id,
            app_args=app_args,
            foreign_apps=[
                self.nanopool.application_id,
                self.nanopool.manager_application_id,
            ],
            foreign_assets=assets,
            accounts=[self.nanopool.address],
        )

        transaction.assign_group_id([inSwapTxn, appCallTxn])
        signedInSwapTxn = inSwapTxn.sign(user.getPrivateKey())
        signedAppCallTxn = appCallTxn.sign(user.getPrivateKey())

        self.client.algod.send_transactions([signedInSwapTxn, signedAppCallTxn])
        wait_for_confirmation(self.client.algod, signedAppCallTxn.get_txid())
