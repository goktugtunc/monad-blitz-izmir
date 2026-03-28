require("@nomicfoundation/hardhat-toolbox");
require("dotenv").config();

const { MONAD_RPC_URL, PRIVATE_KEY } = process.env;

module.exports = {
  solidity: "0.8.28",
  networks: {
    hardhat: {
      chainId: 31338
    },
    localhost: {
      url: "http://127.0.0.1:8545"
    },
    monadTestnet: {
      url: MONAD_RPC_URL || "https://testnet-rpc.monad.xyz",
      accounts: PRIVATE_KEY && PRIVATE_KEY !== "replace_with_test_wallet_private_key" ? [PRIVATE_KEY] : []
    }
  }
};
