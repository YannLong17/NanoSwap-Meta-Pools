from metapool.metapoolAMMClient import MetapoolAMMClient
from metapool.contracts.poolKeys import metapool_strings
from algofi_amm.v0.config import PoolType
from algofi_amm.utils import get_application_global_state, get_account_balances
from metapool.testing.resources import startup, is_close
from metapool.testing.configTestnet import (
    ASSET1_ID,
    ASSET2_ID,
    USTEST_ID,
    MIN_INCREMENT,
    FEE_BPS,
)
from metapool.utils import MIN_BALANCE_REQUIREMENT
from algosdk.encoding import decode_address
import pytest
import base64
from math import sqrt


def test_create():
    amm_client, creator_account = startup()
    nanopool = amm_client.get_pool(PoolType.NANOSWAP, ASSET1_ID, ASSET2_ID)

    # Create a new metapool client
    Metapool = MetapoolAMMClient(
        client=amm_client, nanopool=nanopool, metaAssetID=USTEST_ID
    )

    metapool_app_id = Metapool.createMetapool(creator_account)
    actual_state = get_application_global_state(amm_client.indexer, metapool_app_id)

    expected_state = {
        metapool_strings.nanopool_app_id: 0,
        metapool_strings.nanopool_manager_id: 0,
        metapool_strings.nanopool_address: "",
        metapool_strings.nanopool_asset_1_id: 0,
        metapool_strings.nanopool_asset_2_id: 0,
        metapool_strings.nanopool_lp_id: 0,
        metapool_strings.meta_asset_id: 0,
        metapool_strings.fee_bps: 0,
        metapool_strings.min_increment: 0,
        metapool_strings.pool_token_outstanding: 0,
    }

    assert actual_state == expected_state

    Metapool.closeMetapool(creator_account)


def test_setup():
    amm_client, creator_account = startup()
    nanopool = amm_client.get_pool(PoolType.NANOSWAP, ASSET1_ID, ASSET2_ID)

    # Create a new metapool client
    Metapool = MetapoolAMMClient(
        client=amm_client,
        nanopool=nanopool,
        metaAssetID=USTEST_ID,
    )
    Metapool.createMetapool(creator_account)

    # Try to set up with negative fees
    with pytest.raises(OverflowError):
        Metapool.setupMetapool(
            creator_account, feeBps=-FEE_BPS, minIncrement=MIN_INCREMENT
        )

    metapool_lp_id = Metapool.setupMetapool(
        creator_account, feeBps=FEE_BPS, minIncrement=MIN_INCREMENT
    )

    actual_state = get_application_global_state(
        amm_client.indexer, Metapool.metapool_application_id
    )
    expected_state = {
        metapool_strings.nanopool_app_id: nanopool.application_id,
        metapool_strings.nanopool_manager_id: nanopool.manager_application_id,
        metapool_strings.nanopool_address: base64.b64encode(
            decode_address(nanopool.address)
        ).decode(),
        metapool_strings.nanopool_asset_1_id: ASSET1_ID,
        metapool_strings.nanopool_asset_2_id: ASSET2_ID,
        metapool_strings.nanopool_lp_id: nanopool.lp_asset_id,
        metapool_strings.meta_asset_id: USTEST_ID,
        metapool_strings.meta_lp_id: metapool_lp_id,
        metapool_strings.fee_bps: FEE_BPS,
        metapool_strings.min_increment: MIN_INCREMENT,
        metapool_strings.pool_token_outstanding: 0,
    }

    assert actual_state == expected_state

    actual_balances = get_account_balances(
        amm_client.indexer, Metapool.metapool_address
    )
    expected_balances = {
        1: MIN_BALANCE_REQUIREMENT,
        USTEST_ID: 0,
        nanopool.lp_asset_id: 0,
        metapool_lp_id: metapool_strings.pool_token_default_amount,
        ASSET1_ID: 0,
        ASSET2_ID: 0,
    }

    assert actual_balances == expected_balances

    Metapool.closeMetapool(creator_account)


def test_not_setup():
    amm_client, creator_account = startup()
    nanopool = amm_client.get_pool(PoolType.NANOSWAP, ASSET1_ID, ASSET2_ID)

    # Create a new metapool client
    Metapool = MetapoolAMMClient(
        client=amm_client, nanopool=nanopool, metaAssetID=USTEST_ID
    )

    Metapool.createMetapool(creator_account)

    ops = [
        lambda: Metapool.add_liquidity(creator_account, 2000, 2000),
        lambda: Metapool.withdraw(creator_account, 2000),
        lambda: Metapool.metaswap(creator_account, ASSET1_ID, 1000, USTEST_ID),
    ]

    for op in ops:
        with pytest.raises(Exception) as e:
            op()
            assert "AMM must be set up and funded first." == str(e)
    Metapool.closeMetapool(creator_account)


def test_add_liquidity():
    amm_client, creator_account = startup()
    nanopool = amm_client.get_pool(PoolType.NANOSWAP, ASSET1_ID, ASSET2_ID)

    # Create a new metapool client
    Metapool = MetapoolAMMClient(
        client=amm_client, nanopool=nanopool, metaAssetID=USTEST_ID
    )

    metapool_app_id = Metapool.createMetapool(creator_account)
    metapool_lp_id = Metapool.setupMetapool(
        creator_account, feeBps=FEE_BPS, minIncrement=MIN_INCREMENT
    )
    Metapool.optInToPoolToken(creator_account)

    Metapool.add_liquidity(creator_account, 2000, 1000)

    actual_tokens_outstanding = get_application_global_state(
        amm_client.indexer, metapool_app_id
    )[metapool_strings.pool_token_outstanding]
    expected_tokens_outstanding = int(sqrt(2000 * 1000))
    first_pool_tokens = get_account_balances(
        amm_client.indexer, creator_account.getAddress()
    )[metapool_lp_id]
    assert actual_tokens_outstanding == expected_tokens_outstanding
    assert first_pool_tokens == expected_tokens_outstanding

    # should take 2000 : 1000 again
    Metapool.add_liquidity(creator_account, 2000, 2000)
    actual_tokens_outstanding = get_application_global_state(
        amm_client.indexer, metapool_app_id
    )[metapool_strings.pool_token_outstanding]
    expected_tokens_outstanding = first_pool_tokens * 2
    second_pool_tokens = (
        get_account_balances(amm_client.indexer, creator_account.getAddress())[
            metapool_lp_id
        ]
        - first_pool_tokens
    )

    assert actual_tokens_outstanding == expected_tokens_outstanding
    assert second_pool_tokens == first_pool_tokens

    # should take 20000 : 10000
    Metapool.add_liquidity(creator_account, 20000, 12000)
    actual_tokens_outstanding = get_application_global_state(
        amm_client.indexer, metapool_app_id
    )[metapool_strings.pool_token_outstanding]
    expected_tokens_outstanding = first_pool_tokens * 12  # 2 + 10
    third_pool_tokens = (
        get_account_balances(amm_client.indexer, creator_account.getAddress())[
            metapool_lp_id
        ]
        - first_pool_tokens
        - second_pool_tokens
    )

    assert actual_tokens_outstanding == expected_tokens_outstanding
    assert third_pool_tokens == first_pool_tokens * 10

    Metapool.withdraw(
        creator_account,
        get_account_balances(amm_client.indexer, creator_account.getAddress())[
            metapool_lp_id
        ],
    )
    Metapool.closeMetapool(creator_account)


def test_withdraw():
    amm_client, creator_account = startup()
    nanopool = amm_client.get_pool(PoolType.NANOSWAP, ASSET1_ID, ASSET2_ID)

    # Create a new metapool client
    Metapool = MetapoolAMMClient(
        client=amm_client, nanopool=nanopool, metaAssetID=USTEST_ID
    )

    metapool_app_id = Metapool.createMetapool(creator_account)
    metapool_lp_id = Metapool.setupMetapool(
        creator_account, feeBps=FEE_BPS, minIncrement=MIN_INCREMENT
    )
    Metapool.optInToPoolToken(creator_account)

    initial_balances = get_account_balances(
        amm_client.indexer, creator_account.getAddress()
    )
    Metapool.add_liquidity(creator_account, 2000, 1000)
    initial_pool_tokens_outstanding = int(sqrt(2000 * 1000))

    # return one third of pool tokens to the pool, keep two thirds
    Metapool.withdraw(creator_account, initial_pool_tokens_outstanding // 3)
    first_pool_tokens = get_account_balances(
        amm_client.indexer, creator_account.getAddress()
    )[metapool_lp_id]
    expected_pool_tokens = (
        initial_pool_tokens_outstanding - initial_pool_tokens_outstanding // 3
    )
    assert first_pool_tokens == expected_pool_tokens

    first_token_A_amount = get_account_balances(
        amm_client.indexer, creator_account.getAddress()
    )[USTEST_ID]
    expected_token_A_amount = initial_balances[USTEST_ID] - 2000 + 2000 // 3
    assert first_token_A_amount == expected_token_A_amount

    first_token_B_amount = get_account_balances(
        amm_client.indexer, creator_account.getAddress()
    )[nanopool.lp_asset_id]
    expected_token_B_amount = initial_balances[nanopool.lp_asset_id] - 1000 + 1000 // 3
    assert first_token_B_amount == expected_token_B_amount

    # double the original liquidity
    Metapool.add_liquidity(creator_account, 2000 + 2000 // 3, 1000 + 1000 // 3)
    actual_tokens_outstanding = get_application_global_state(
        amm_client.indexer, metapool_app_id
    )[metapool_strings.pool_token_outstanding]
    assert is_close(actual_tokens_outstanding, initial_pool_tokens_outstanding * 2)

    Metapool.withdraw(creator_account, initial_pool_tokens_outstanding)

    pool_balances = get_account_balances(amm_client.indexer, Metapool.metapool_address)

    expected_token_A_amount = 2000
    expected_token_B_amount = 1000
    supplier_pool_tokens = get_account_balances(
        amm_client.indexer, creator_account.getAddress()
    )[metapool_lp_id]
    assert is_close(pool_balances[USTEST_ID], expected_token_A_amount)
    assert is_close(pool_balances[nanopool.lp_asset_id], expected_token_B_amount)
    assert is_close(supplier_pool_tokens, initial_pool_tokens_outstanding)

    Metapool.withdraw(creator_account, supplier_pool_tokens)
    Metapool.closeMetapool(creator_account)


def test_metaswap():
    amm_client, creator_account = startup()
    nanopool = amm_client.get_pool(PoolType.NANOSWAP, ASSET1_ID, ASSET2_ID)

    # Create a new metapool client
    Metapool = MetapoolAMMClient(
        client=amm_client, nanopool=nanopool, metaAssetID=USTEST_ID
    )

    metapool_app_id = Metapool.createMetapool(creator_account)
    metapool_lp_id = Metapool.setupMetapool(
        creator_account, feeBps=FEE_BPS, minIncrement=MIN_INCREMENT
    )
    Metapool.optInToPoolToken(creator_account)

    m, n = 2_000_000, 1_000_000
    Metapool.add_liquidity(creator_account, m, n)
    a = 100_000
    Metapool.fundMetapool(
        creator_account, a
    )  # send 1 algo to contract to pay for inner transactions

    # Wrong input values should be cought in the client
    with pytest.raises(ValueError) as e:
        # Wrong input token
        Metapool.metaswap(
            creator_account, metapool_lp_id, 1000, Metapool.nanopool.asset1.asset_id
        )
        assert "Invalid Input token" in str(e)

    with pytest.raises(ValueError) as e:
        # Wrong output token
        Metapool.metaswap(
            creator_account, Metapool.meta_asset_id, 1000, Metapool.nanopool.lp_asset_id
        )
        assert "Invalid Output token" in str(e)

    with pytest.raises(AssertionError) as e:
        # Wrong output token
        Metapool.metaswap(
            creator_account,
            Metapool.nanopool.asset2.asset_id,
            1000,
            Metapool.nanopool.asset1.asset_id,
        )
        assert "Invalid Output token" in str(e)

    with pytest.raises(AssertionError) as e:
        # Swap more than in possessioon
        Metapool.metaswap(
            creator_account,
            Metapool.meta_asset_id,
            10**16,
            Metapool.nanopool.asset1.asset_id,
        )
        assert "Not Enough Balance" in str(e)

    with pytest.raises(AssertionError) as e:
        # swap too little
        Metapool.metaswap(
            creator_account,
            Metapool.nanopool.asset2.asset_id,
            1,
            Metapool.meta_asset_id,
        )
        assert "Swap too little" in str(e)

    # Test The swap USTest -> Nanopool asset 1
    x = 5000
    initial_balances = get_account_balances(
        amm_client.indexer, creator_account.getAddress()
    )
    initial_contract_algo = get_account_balances(
        amm_client.indexer, Metapool.metapool_address
    )[1]
    Metapool.nanopool.refresh_state()
    Metapool.metaswap(
        creator_account, Metapool.meta_asset_id, x, Metapool.nanopool.asset1.asset_id
    )
    initial_product = m * n
    expected_burned_token_b = n - initial_product // (
        m + (100_00 - FEE_BPS) * x // 100_00
    )
    pool_balances = get_account_balances(amm_client.indexer, Metapool.metapool_address)
    actual_burned_token_b = n - pool_balances[Metapool.nanopool.lp_asset_id]
    actual_received_token_a = pool_balances[Metapool.meta_asset_id] - m
    burn_quote = Metapool.nanopool.get_burn_quote(actual_burned_token_b)
    swap_quote = Metapool.nanopool.get_swap_exact_for_quote(
        Metapool.nanopool.asset2.asset_id, burn_quote.asset2_delta
    )
    expected_asset_1_received = swap_quote.asset1_delta + burn_quote.asset1_delta
    actual_asset_1_received = (
        get_account_balances(amm_client.indexer, creator_account.getAddress())[
            Metapool.nanopool.asset1.asset_id
        ]
        - initial_balances[Metapool.nanopool.asset1.asset_id]
    )

    is_close(actual_asset_1_received, expected_asset_1_received)
    assert actual_burned_token_b == expected_burned_token_b
    assert actual_received_token_a == x
    assert (
        pool_balances[1] == initial_contract_algo - 4000
    )  # only paid 4000 (forced) for inner swap transaction

    expected_new_product = initial_product - expected_burned_token_b * (m + x) + (x * n)
    actual_new_product = (
        pool_balances[Metapool.meta_asset_id]
        * pool_balances[Metapool.nanopool.lp_asset_id]
    )

    assert expected_new_product == actual_new_product
    assert actual_new_product > initial_product

    # Test The reverse swap Nanopool asset 1 -> UStest
    mm, nn = (
        pool_balances[Metapool.meta_asset_id],
        pool_balances[Metapool.nanopool.lp_asset_id],
    )
    y = x * 2
    zap_amout = Metapool.get_zap_amount(Metapool.nanopool.asset1.asset_id, y)
    Metapool.metaswap(
        creator_account, Metapool.nanopool.asset1.asset_id, y, Metapool.meta_asset_id
    )
    new_pool_balances = get_account_balances(
        amm_client.indexer, Metapool.metapool_address
    )
    swap_quote = Metapool.nanopool.get_swap_exact_for_quote(
        Metapool.nanopool.asset1.asset_id, zap_amout
    )
    pool_quote = Metapool.nanopool.get_pool_quote(
        Metapool.nanopool.asset2.asset_id, swap_quote.asset2_delta
    )
    expected_received_token_b = pool_quote.lp_delta
    actual_received_token_b = (
        new_pool_balances[Metapool.nanopool.lp_asset_id]
        - pool_balances[Metapool.nanopool.lp_asset_id]
    )

    is_close(pool_quote.asset1_delta, y - zap_amout)
    is_close(expected_received_token_b, actual_received_token_b, 5)

    expected_received_token_a = mm - actual_new_product // (
        nn + (10000 - FEE_BPS) * actual_received_token_b // 10000
    )
    actual_received_token_a = mm - new_pool_balances[Metapool.meta_asset_id]
    assert (
        new_pool_balances[1] == pool_balances[1] - 8000
    )  # check force inner transaction fee is only spending
    assert expected_received_token_a == actual_received_token_a

    expected_new_product = (
        actual_new_product
        - expected_received_token_a * (nn + actual_received_token_b)
        + (actual_received_token_b * mm)
    )
    actual_new_product = (
        new_pool_balances[Metapool.meta_asset_id]
        * new_pool_balances[Metapool.nanopool.lp_asset_id]
    )
    assert actual_new_product == expected_new_product
    assert actual_new_product > initial_product

    expected_ratio = (m + x - expected_received_token_a) / (
        n - expected_burned_token_b + actual_received_token_b
    )
    actual_ratio = (
        new_pool_balances[Metapool.meta_asset_id]
        / new_pool_balances[Metapool.nanopool.lp_asset_id]
    )
    assert actual_ratio == expected_ratio

    to_withdraw = int(sqrt(initial_product) // 2)
    Metapool.withdraw(creator_account, to_withdraw)
    new2_pool_balances = get_account_balances(
        amm_client.indexer, Metapool.metapool_address
    )
    actual_ratio = (
        new2_pool_balances[Metapool.meta_asset_id]
        / new2_pool_balances[Metapool.nanopool.lp_asset_id]
    )
    ratio_close_enough = 0.001
    is_close(actual_ratio, expected_ratio, ratio_close_enough)
    is_close(
        new2_pool_balances[Metapool.meta_asset_id]
        / new_pool_balances[Metapool.meta_asset_id],
        0.5,
        ratio_close_enough,
    )
    is_close(
        new2_pool_balances[Metapool.nanopool.lp_asset_id]
        / new_pool_balances[Metapool.nanopool.lp_asset_id],
        0.5,
        ratio_close_enough,
    )

    Metapool.withdraw(
        creator_account,
        get_account_balances(amm_client.indexer, creator_account.getAddress())[
            metapool_lp_id
        ],
    )
    Metapool.closeMetapool(creator_account)
