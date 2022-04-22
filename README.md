# NanoSwap Meta Pools
Algofi NanoSwap is an automated market maker stableswap protocol that supports trading of stablecoins for much cheaper due to an efficient stableswap invariant algorithm. For this HackAlgo Bountie, the challenge was to realize a Meta pool that would allow to swap another token against an existing nanopool pair. Thus expending the range of trading pair, and potential fees collected by the protocol, without removing liquidity from the base pool.

I have developed a smart contract that uses contract-to-contract calls to implement a metapool that can be used to swap a stablecoin like UST against an Algofi NanoSwap pools. A python sdk allows to deploy and interact with the pyteal contract which can be tested toroughly via a pytest testing script.

## Algorand AMM
At the fundamental level, this contract implement a AMM between a token (the meta-asset) and the liquidity token of an existing nanopool. Because this is not the focus of this challenge, I used maks-ivanov [AMM Demo](https://github.com/maks-ivanov/amm-demo) to achieve an elementary infrastructure for my project. 

## Metapool



### Burn


### Zap


### Fees

## Installation
Clone the repository and create a virtual environment
`python -m venv venv`
Activate the virtual environment
`source ./venv/Scripts/activate` (win)
Install the requirements
`pip install -r requirements.txt`
Create a metapool/testing/.env file containing:
`mnemonic = your creator account 25 words`
To use the example and testing script, also install this package to the virtual environment, from the root folder:
`pip install -e .`
 
## Examples

### Initialize

### Add Liquidity

### MetaSwap

## Testing