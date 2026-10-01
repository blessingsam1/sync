from app.chains.evm import EVMChainAdapter


class EthereumMainnetAdapter(EVMChainAdapter):
    chain = "ethereum"
    asset = "ETH"
    expected_chain_id = 1
