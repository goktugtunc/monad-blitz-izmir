const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("MonadMatchCredits", function () {
  it("sells credits and charges for each message", async function () {
    const [owner, user] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("MonadMatchCredits");
    const contract = await Factory.deploy(owner.address);
    await contract.waitForDeployment();

    await expect(
      contract.connect(user).purchaseCredits({ value: ethers.parseEther("1") })
    ).to.changeEtherBalances([user, contract], [ethers.parseEther("-1"), ethers.parseEther("1")]);

    expect(await contract.credits(user.address)).to.equal(1000n);

    await contract.connect(user).recordMessage(
      ethers.id("chat-1"),
      ethers.id("persona-1"),
      ethers.id("hello")
    );

    expect(await contract.credits(user.address)).to.equal(975n);
  });

  it("lets owner grant credits for demo bootstrapping", async function () {
    const [owner, user] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("MonadMatchCredits");
    const contract = await Factory.deploy(owner.address);
    await contract.waitForDeployment();

    await contract.grantCredits(user.address, 250);
    expect(await contract.credits(user.address)).to.equal(250n);
  });
});
