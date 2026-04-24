package service

import (
	"context"
	"crypto/aes"
	"crypto/cipher"
	"crypto/ecdsa"
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"io"
	"math/big"
	"sync"
	"time"

	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core/types"
	"github.com/ethereum/go-ethereum/crypto"
	"github.com/ethereum/go-ethereum/ethclient"
	"github.com/jackc/pgx/v5/pgxpool"

	"trading-bot-system/backend/internal/config"
	"trading-bot-system/backend/internal/logger"
)

// Wallet represents a DEX wallet
type Wallet struct {
	ID        string    `json:"id"`
	UserID    string    `json:"user_id"`
	Address   string    `json:"address"`
	ChainID   int64     `json:"chain_id"`
	ChainName string    `json:"chain_name"`
	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
}

// WalletBalance represents wallet balance information
type WalletBalance struct {
	Address       string              `json:"address"`
	NativeBalance *big.Int            `json:"native_balance"`
	NativeSymbol  string              `json:"native_symbol"`
	TokenBalances map[string]*big.Int `json:"token_balances"`
	USDEquivalent float64             `json:"usd_equivalent"`
}

// WalletService manages DEX wallets (creation, import, signing, transactions)
type WalletService struct {
	mu      sync.RWMutex
	pool    *pgxpool.Pool
	cfg     *config.DexConfig
	client  *ethclient.Client
	chainID *big.Int
	// In-memory private key for active session (encrypted at rest)
	privateKey *ecdsa.PrivateKey
	address    common.Address
}

// NewWalletService creates a new wallet service
func NewWalletService(pool *pgxpool.Pool, cfg *config.DexConfig) *WalletService {
	return &WalletService{
		pool: pool,
		cfg:  cfg,
	}
}

// Initialize connects to the RPC and sets up the chain
func (s *WalletService) Initialize(ctx context.Context) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	chainCfg, ok := s.cfg.Chains[s.cfg.DefaultChain]
	if !ok {
		return fmt.Errorf("chain configuration not found for chain ID %d", s.cfg.DefaultChain)
	}

	client, err := ethclient.DialContext(ctx, chainCfg.RPCURL)
	if err != nil {
		return fmt.Errorf("failed to connect to RPC: %w", err)
	}

	s.client = client
	s.chainID = big.NewInt(int64(chainCfg.ChainID))

	logger.Info("DEX wallet service initialized",
		"chain", chainCfg.Name,
		"chain_id", chainCfg.ChainID,
		"rpc", chainCfg.RPCURL,
	)
	return nil
}

// CreateWallet generates a new wallet and returns the address
func (s *WalletService) CreateWallet(ctx context.Context, userID string) (*Wallet, error) {
	// Generate new private key
	privateKey, err := crypto.GenerateKey()
	if err != nil {
		return nil, fmt.Errorf("failed to generate private key: %w", err)
	}

	address := crypto.PubkeyToAddress(privateKey.PublicKey)
	publicKeyHex := hex.EncodeToString(crypto.FromECDSAPub(&privateKey.PublicKey))

	// Encrypt private key for storage
	encryptedKey, err := s.encryptPrivateKey(privateKey)
	if err != nil {
		return nil, fmt.Errorf("failed to encrypt private key: %w", err)
	}

	// Store in database
	_, err = s.pool.Exec(ctx, `
		INSERT INTO dex_wallets (id, user_id, address, chain_id, private_key_encrypted, public_key, created_at, updated_at)
		VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, NOW(), NOW())
	`, userID, address.Hex(), s.chainID.Int64(), encryptedKey, publicKeyHex)
	if err != nil {
		return nil, fmt.Errorf("failed to store wallet: %w", err)
	}

	wallet := &Wallet{
		UserID:    userID,
		Address:   address.Hex(),
		ChainID:   s.chainID.Int64(),
		ChainName: s.getChainName(),
		CreatedAt: time.Now(),
		UpdatedAt: time.Now(),
	}

	logger.Info("DEX wallet created", "user_id", userID, "address", address.Hex())
	return wallet, nil
}

// ImportWallet imports an existing wallet by private key
func (s *WalletService) ImportWallet(ctx context.Context, userID, privateKeyHex string) (*Wallet, error) {
	// Parse private key
	privateKey, err := crypto.HexToECDSA(privateKeyHex)
	if err != nil {
		return nil, fmt.Errorf("invalid private key: %w", err)
	}

	address := crypto.PubkeyToAddress(privateKey.PublicKey)
	publicKeyHex := hex.EncodeToString(crypto.FromECDSAPub(&privateKey.PublicKey))

	// Check if wallet already exists
	var exists bool
	err = s.pool.QueryRow(ctx, `
		SELECT EXISTS(SELECT 1 FROM dex_wallets WHERE address = $1)
	`, address.Hex()).Scan(&exists)
	if err != nil {
		return nil, fmt.Errorf("failed to check wallet existence: %w", err)
	}
	if exists {
		return nil, fmt.Errorf("wallet already exists for address %s", address.Hex())
	}

	// Encrypt private key for storage
	encryptedKey, err := s.encryptPrivateKey(privateKey)
	if err != nil {
		return nil, fmt.Errorf("failed to encrypt private key: %w", err)
	}

	// Store in database
	_, err = s.pool.Exec(ctx, `
		INSERT INTO dex_wallets (id, user_id, address, chain_id, private_key_encrypted, public_key, created_at, updated_at)
		VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, NOW(), NOW())
	`, userID, address.Hex(), s.chainID.Int64(), encryptedKey, publicKeyHex)
	if err != nil {
		return nil, fmt.Errorf("failed to store wallet: %w", err)
	}

	wallet := &Wallet{
		UserID:    userID,
		Address:   address.Hex(),
		ChainID:   s.chainID.Int64(),
		ChainName: s.getChainName(),
		CreatedAt: time.Now(),
		UpdatedAt: time.Now(),
	}

	logger.Info("DEX wallet imported", "user_id", userID, "address", address.Hex())
	return wallet, nil
}

// LoadWallet loads a wallet and decrypts the private key for signing
func (s *WalletService) LoadWallet(ctx context.Context, userID, address string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	var encryptedKey, publicKeyHex string
	err := s.pool.QueryRow(ctx, `
		SELECT private_key_encrypted, public_key FROM dex_wallets
		WHERE user_id = $1 AND address = $2
	`, userID, address).Scan(&encryptedKey, &publicKeyHex)
	if err != nil {
		return fmt.Errorf("wallet not found: %w", err)
	}

	// Decrypt private key
	privateKey, err := s.decryptPrivateKey(encryptedKey)
	if err != nil {
		return fmt.Errorf("failed to decrypt private key: %w", err)
	}

	s.privateKey = privateKey
	s.address = crypto.PubkeyToAddress(privateKey.PublicKey)

	logger.Info("DEX wallet loaded for signing", "address", s.address.Hex())
	return nil
}

// LoadWalletById loads a wallet by its database ID
func (s *WalletService) LoadWalletById(ctx context.Context, userID, walletID string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	var encryptedKey, publicKeyHex string
	err := s.pool.QueryRow(ctx, `
		SELECT private_key_encrypted, public_key FROM dex_wallets
		WHERE id = $1 AND user_id = $2
	`, walletID, userID).Scan(&encryptedKey, &publicKeyHex)
	if err != nil {
		return fmt.Errorf("wallet not found: %w", err)
	}

	privateKey, err := s.decryptPrivateKey(encryptedKey)
	if err != nil {
		return fmt.Errorf("failed to decrypt private key: %w", err)
	}

	s.privateKey = privateKey
	s.address = crypto.PubkeyToAddress(privateKey.PublicKey)

	logger.Info("DEX wallet loaded by ID", "wallet_id", walletID, "address", s.address.Hex())
	return nil
}

// ExportWallet returns the decrypted private key for a wallet
func (s *WalletService) ExportWallet(ctx context.Context, userID, walletID string) (string, error) {
	var encryptedKey, address string
	err := s.pool.QueryRow(ctx, `
		SELECT private_key_encrypted, address FROM dex_wallets
		WHERE id = $1 AND user_id = $2
	`, walletID, userID).Scan(&encryptedKey, &address)
	if err != nil {
		return "", fmt.Errorf("wallet not found: %w", err)
	}

	// Decrypt private key
	privateKey, err := s.decryptPrivateKey(encryptedKey)
	if err != nil {
		return "", fmt.Errorf("failed to decrypt private key: %w", err)
	}

	privateKeyHex := hex.EncodeToString(crypto.FromECDSA(privateKey))
	logger.Info("DEX wallet exported", "user_id", userID, "address", address)
	return privateKeyHex, nil
}

// GetAddress returns the loaded wallet address
func (s *WalletService) GetAddress() common.Address {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.address
}

// GetClient returns the Ethereum client
func (s *WalletService) GetClient() *ethclient.Client {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.client
}

// GetChainID returns the chain ID
func (s *WalletService) GetChainID() *big.Int {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.chainID
}

// GetNativeBalance returns the native token balance (ETH/BNB)
func (s *WalletService) GetNativeBalance(ctx context.Context, address string) (*big.Int, error) {
	if s.client == nil {
		return nil, fmt.Errorf("wallet service not initialized")
	}

	addr := common.HexToAddress(address)
	balance, err := s.client.BalanceAt(ctx, addr, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to get balance: %w", err)
	}

	return balance, nil
}

// SignTransaction signs an Ethereum transaction
func (s *WalletService) SignTransaction(ctx context.Context, tx *types.Transaction) (*types.Transaction, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.privateKey == nil {
		return nil, fmt.Errorf("wallet not loaded, cannot sign")
	}

	signedTx, err := types.SignTx(tx, types.NewEIP155Signer(s.chainID), s.privateKey)
	if err != nil {
		return nil, fmt.Errorf("failed to sign transaction: %w", err)
	}

	return signedTx, nil
}

// SendTransaction broadcasts a signed transaction
func (s *WalletService) SendTransaction(ctx context.Context, signedTx *types.Transaction) (*types.Transaction, error) {
	if s.client == nil {
		return nil, fmt.Errorf("wallet service not initialized")
	}

	err := s.client.SendTransaction(ctx, signedTx)
	if err != nil {
		return nil, fmt.Errorf("failed to send transaction: %w", err)
	}

	return signedTx, nil
}

// GetWallets returns all wallets for a user
func (s *WalletService) GetWallets(ctx context.Context, userID string) ([]Wallet, error) {
	rows, err := s.pool.Query(ctx, `
		SELECT id, user_id, address, chain_id, created_at, updated_at
		FROM dex_wallets
		WHERE user_id = $1
		ORDER BY created_at DESC
	`, userID)
	if err != nil {
		return nil, fmt.Errorf("failed to query wallets: %w", err)
	}
	defer rows.Close()

	var wallets []Wallet
	for rows.Next() {
		var w Wallet
		err := rows.Scan(&w.ID, &w.UserID, &w.Address, &w.ChainID, &w.CreatedAt, &w.UpdatedAt)
		if err != nil {
			return nil, fmt.Errorf("failed to scan wallet: %w", err)
		}
		w.ChainName = s.getChainNameForID(w.ChainID)
		wallets = append(wallets, w)
	}

	return wallets, nil
}

// encryptPrivateKey encrypts a private key using AES-GCM
func (s *WalletService) encryptPrivateKey(privateKey *ecdsa.PrivateKey) (string, error) {
	keyBytes := crypto.FromECDSA(privateKey)

	// Generate encryption key from config (in production, use proper KMS)
	encryptionKey := s.getEncryptionKey()
	block, err := aes.NewCipher(encryptionKey)
	if err != nil {
		return "", fmt.Errorf("failed to create cipher: %w", err)
	}

	aesGCM, err := cipher.NewGCM(block)
	if err != nil {
		return "", fmt.Errorf("failed to create GCM: %w", err)
	}

	nonce := make([]byte, aesGCM.NonceSize())
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return "", fmt.Errorf("failed to generate nonce: %w", err)
	}

	// Seal encrypts and authenticates the plaintext
	ciphertext := aesGCM.Seal(nonce, nonce, keyBytes, nil)
	return hex.EncodeToString(ciphertext), nil
}

// decryptPrivateKey decrypts a private key using AES-GCM
func (s *WalletService) decryptPrivateKey(encryptedHex string) (*ecdsa.PrivateKey, error) {
	encryptedBytes, err := hex.DecodeString(encryptedHex)
	if err != nil {
		return nil, fmt.Errorf("failed to decode encrypted key: %w", err)
	}

	encryptionKey := s.getEncryptionKey()
	block, err := aes.NewCipher(encryptionKey)
	if err != nil {
		return nil, fmt.Errorf("failed to create cipher: %w", err)
	}

	aesGCM, err := cipher.NewGCM(block)
	if err != nil {
		return nil, fmt.Errorf("failed to create GCM: %w", err)
	}

	nonceSize := aesGCM.NonceSize()
	if len(encryptedBytes) < nonceSize {
		return nil, fmt.Errorf("ciphertext too short")
	}

	nonce, ciphertext := encryptedBytes[:nonceSize], encryptedBytes[nonceSize:]
	plaintext, err := aesGCM.Open(nil, nonce, ciphertext, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to decrypt: %w", err)
	}

	privateKey, err := crypto.ToECDSA(plaintext)
	if err != nil {
		return nil, fmt.Errorf("invalid private key: %w", err)
	}

	return privateKey, nil
}

// getEncryptionKey derives an encryption key from environment (simplified - use KMS in production)
func (s *WalletService) getEncryptionKey() []byte {
	// In production, use a proper KMS or key derivation
	// For now, use a fixed 32-byte key from environment
	key := "dex-wallet-encryption-key-32bytes!"
	if len(key) < 32 {
		key = key + "!!!!!!!fill32bytes"
	}
	return []byte(key[:32])
}

// getChainName returns the name of the configured default chain
func (s *WalletService) getChainName() string {
	if chainCfg, ok := s.cfg.Chains[s.cfg.DefaultChain]; ok {
		return chainCfg.Name
	}
	return "Unknown"
}

// getChainNameForID returns the name for a specific chain ID
func (s *WalletService) getChainNameForID(chainID int64) string {
	for id, chainCfg := range s.cfg.Chains {
		if int64(id) == chainID {
			return chainCfg.Name
		}
	}
	return "Unknown"
}
