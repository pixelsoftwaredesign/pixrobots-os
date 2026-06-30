// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title PixelToken — BITROOT (BRT)
/// @notice Token communautaire ERC-20 pour l'écosystème PixelOS
/// @dev Déploiement recommandé : Gnosis Chain (frais quasi-nuls) ou Polygon
/// @custom:website https://pixelos.pxl
/// @custom:community PixelOS DAO

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Burnable.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Pausable.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Permit.sol";

contract PixelToken is ERC20, ERC20Burnable, ERC20Pausable, Ownable, ERC20Permit {
    uint256 public constant MAX_SUPPLY = 1_000_000_000 * 10**18; // 1 milliard BRT
    uint256 public constant COMMUNITY_MINT_CAP = 100_000_000 * 10**18; // 100M pour la communauté
    uint256 public communityMinted;
    
    mapping(address => bool) public communityMembers;
    mapping(address => uint256) public lastTransfer;
    address[] public memberList;
    
    // Événements
    event MemberJoined(address indexed member, uint256 timestamp);
    event CommunityMint(address indexed to, uint256 amount, string reason);
    event PaymentReceived(address indexed from, address indexed to, uint256 amount, string memo);
    
    constructor(address initialOwner)
        ERC20("BITROOT", "BRT")
        Ownable(initialOwner)
        ERC20Permit("BITROOT")
    {
        // Mint initial pour le fondateur (50M BRT pour bootstrap)
        _mint(initialOwner, 50_000_000 * 10**18);
        communityMembers[initialOwner] = true;
        memberList.push(initialOwner);
    }
    
    /// @notice Permet à un membre de la communauté de rejoindre
    function joinCommunity() external {
        require(!communityMembers[msg.sender], "Deja membre");
        communityMembers[msg.sender] = true;
        memberList.push(msg.sender);
        emit MemberJoined(msg.sender, block.timestamp);
    }
    
    /// @notice Mint communautaire réservé aux nouveaux membres
    /// @dev Plafonné à COMMUNITY_MINT_CAP total
    function communityMint(address to, uint256 amount, string calldata reason) 
        external 
        onlyOwner 
    {
        require(communityMinted + amount <= COMMUNITY_MINT_CAP, "Plafond communautaire atteint");
        require(communityMembers[to], "Destinataire non membre");
        _mint(to, amount);
        communityMinted += amount;
        emit CommunityMint(to, amount, reason);
    }
    
    /// @notice Transfert avec mémo (pour traçabilité agricole)
    function transferWithMemo(address to, uint256 amount, string calldata memo) 
        external 
        returns (bool) 
    {
        _transfer(_msgSender(), to, amount);
        emit PaymentReceived(_msgSender(), to, amount, memo);
        return true;
    }
    
    /// @notice Nombre total de membres
    function memberCount() external view returns (uint256) {
        return memberList.length;
    }
    
    /// @notice Vérifie si une adresse est membre
    function isMember(address addr) external view returns (bool) {
        return communityMembers[addr];
    }
    
    /// @notice Liste paginée des membres
    function getMembers(uint256 offset, uint256 limit) 
        external 
        view 
        returns (address[] memory, uint256 total) 
    {
        total = memberList.length;
        if (offset >= total) return (new address[](0), total);
        uint256 end = offset + limit > total ? total : offset + limit;
        address[] memory result = new address[](end - offset);
        for (uint256 i = offset; i < end; i++) {
            result[i - offset] = memberList[i];
        }
        return (result, total);
    }
    
    // Surcharges requises par Solidity
    function _update(address from, address to, uint256 value)
        internal
        override(ERC20, ERC20Pausable)
    {
        super._update(from, to, value);
        if (from != address(0) && to != address(0)) {
            lastTransfer[from] = block.timestamp;
            lastTransfer[to] = block.timestamp;
        }
    }
    
    function pause() external onlyOwner {
        _pause();
    }
    
    function unpause() external onlyOwner {
        _unpause();
    }
}
