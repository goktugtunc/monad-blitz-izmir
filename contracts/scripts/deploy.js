const fs = require("fs");
const path = require("path");
const hre = require("hardhat");

async function main() {
  const [deployer] = await hre.ethers.getSigners();
  const Credits = await hre.ethers.getContractFactory("MonadMatchCredits");
  const credits = await Credits.deploy(deployer.address);
  await credits.waitForDeployment();

  const address = await credits.getAddress();
  const artifact = await hre.artifacts.readArtifact("MonadMatchCredits");
  const payload = {
    network: hre.network.name,
    address,
    abi: artifact.abi
  };

  const sharedDir = "/shared";
  if (fs.existsSync(sharedDir)) {
    fs.writeFileSync(path.join(sharedDir, "monad-match-credits.json"), JSON.stringify(payload, null, 2));
  }

  console.log(`MonadMatchCredits deployed to ${address} on ${hre.network.name}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
