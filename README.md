# NanoSwap Meta Pools
Algofi NanoSwap is an automated market maker stableswap protocol that supports trading of stablecoins for much cheaper due to an efficient stableswap invariant algorithm. For this HackAlgo Bountie, the challenge was to realize a Meta pool that would allow to swap another token against an existing nanopool pair. Thus expending the range of trading pair, and potential fees collected by the protocol, without removing liquidity from the base pool.  

I have developed a smart contract that uses contract-to-contract calls to implement a metapool that can be used to swap a stablecoin like UST against an Algofi NanoSwap pools. A python sdk allows to deploy and interact with the pyteal contract which can be tested thoroughly via a pytest testing script.

## Algorand AMM
At the fundamental level, this contract implement an AMM between a token (the meta-asset) and the liquidity token of an existing nanopool. Because this is not the focus of this challenge, I used maks-ivanov [AMM Demo](https://github.com/maks-ivanov/amm-demo) to achieve an elementary infrastructure for my project. 

## Metapool
While the base is a normal constant product AMM, the metapool does not permit users to trade between its two assets directly. Instead, the contract makes the appropriate inner transaction application call to an existing nanopool to allow the user to seamlessly trade between the meta asset and any of the nanopool paired assets. To facilitate the interaction with the metapool contract, I provided a [MetapoolClient](https://github.com/YannLong17/NanoSwap-Meta-Pools/blob/main/metapool/metapoolAMMClient.py) which contains the metapool operations.

### Burn: Swapping UST -> USDC
1. Swap UST -> nanopool LP in the metapool  
2. Burn the nanopool LP into USDC + STBL  
3. Swap STBL -> USDC in the nanopool  

### Zap: Swapping USDC -> UST
1. Swap USDC -> STBL to get the appropriate pooling ratio  
2. pool USDC-STBL for nanopool LP  
3. Swap nanopool LP -> UST  

The zapping operation poses an additional challenge because the metapool contract needs to discover the proper zap amount to have an appropriate resulting distribution. Initially, I had a heuristic to calculate this quantity inside the contract. Ultimately, this method was too gluttonous in op code budget so I move the calculation to the front end and pass the zap amount as an input argument to the contract.

### Fees
Ideally, inner transaction should have no fee set, to allow fee pooling to occur and the outer transaction to pay for the whole bill. However, the nanopool contract cannot be called this way as it imposes that the inner transaction has a set fee transaction field. As such, the swap, burn and pool operation carry a fee which comes out of the metapool contract account, instead of the user's, as intended. To function, the contract account must be funded properly.

## Installation
Clone the repository and create a virtual environment  
`python -m venv venv`  
Activate the virtual environment  
`source ./venv/Scripts/activate` (win)  
Install the requirements  
`pip install -r requirements.txt`  
Create a `metapool/testing/.env` file containing:  
`mnemonic = your creator account 25 words`  
To use the example and testing script, also install the metapool package to the virtual environment, from the root folder:  
`pip install -e .`  

## Examples
Run the examples using `python examples/...py`
### Initialize
[Initialize.py](https://github.com/YannLong17/NanoSwap-Meta-Pools/blob/main/examples/Initialize.py)  
Before running, run the `new_test_token.py` or your own test asset and set the newly minted asset ID in `metapool/testing/configTestnet.py`  
This routine creates and setup a metapool. After the script is completed, copy the ID of the newly minted application to `metapool/testing/configTestnet.py`  

### Add Liquidity
[add_liquidity.py](https://github.com/YannLong17/NanoSwap-Meta-Pools/blob/main/examples/add_liquidity.py)  
Make sure that your creator account is funded with nanopool lp asset to provide liquidity to the metapool.

### MetaSwap
[metaswap.py](https://github.com/YannLong17/NanoSwap-Meta-Pools/blob/main/examples/metaswap.py)   
The metapool account needs to remain funded with some algo to pay for the inner transaction fee.

## Testing
The [testing scrip](https://github.com/YannLong17/NanoSwap-Meta-Pools/blob/main/metapool/testing/test_operations.py) can be run from the root directory using the `pytest` command. It will verify the pool math and assert that the contract is sound.
