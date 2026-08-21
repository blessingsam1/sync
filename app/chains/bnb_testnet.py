from app.chains.evm import EVMChainAdapter


class BnbMainnetAdapter(EVMChainAdapter):
    chain = "bnb"
    asset = "BNB"
    expected_chain_id = 56
