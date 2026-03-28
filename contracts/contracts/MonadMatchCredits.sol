// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import "@openzeppelin/contracts/access/Ownable.sol";

contract MonadMatchCredits is Ownable {
    uint256 public constant MESSAGE_COST = 25;
    uint256 public constant CREDITS_PER_PURCHASE = 1000;
    uint256 public constant PURCHASE_PRICE = 1 ether;

    mapping(address => uint256) public credits;

    event CreditsPurchased(address indexed buyer, uint256 amountPaid, uint256 creditsGranted);
    event CreditsGranted(address indexed user, uint256 creditsGranted);
    event MessageRecorded(
        address indexed user,
        bytes32 indexed chatId,
        bytes32 indexed profileId,
        bytes32 messageHash,
        uint256 remainingCredits
    );

    constructor(address initialOwner) Ownable(initialOwner) {}

    function purchaseCredits() external payable {
        require(msg.value == PURCHASE_PRICE, "Send exactly 1 MON");

        credits[msg.sender] += CREDITS_PER_PURCHASE;
        emit CreditsPurchased(msg.sender, msg.value, CREDITS_PER_PURCHASE);
    }

    function grantCredits(address user, uint256 amount) external onlyOwner {
        credits[user] += amount;
        emit CreditsGranted(user, amount);
    }

    function recordMessage(bytes32 chatId, bytes32 profileId, bytes32 messageHash) external {
        require(credits[msg.sender] >= MESSAGE_COST, "Not enough credits");

        credits[msg.sender] -= MESSAGE_COST;
        emit MessageRecorded(msg.sender, chatId, profileId, messageHash, credits[msg.sender]);
    }
}
