package service

import (
	"context"
	"fmt"
	"math/big"

	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core/types"
	"github.com/ethereum/go-ethereum/ethclient"
)

// TxSigner wraps WalletService to implement the dex.Signer interface.
// It handles the full transaction signing flow using the wallet's private key.
type TxSigner struct {
	walletSvc *WalletService
}

// NewTxSigner creates a new transaction signer backed by a wallet service.
func NewTxSigner(walletSvc *WalletService) *TxSigner {
	return &TxSigner{walletSvc: walletSvc}
}

// GetAddress returns the wallet's Ethereum address.
func (s *TxSigner) GetAddress() common.Address {
	return s.walletSvc.GetAddress()
}

// GetClient returns the Ethereum client from the wallet service.
func (s *TxSigner) GetClient() *ethclient.Client {
	return s.walletSvc.GetClient()
}

// GetChainID returns the chain ID.
func (s *TxSigner) GetChainID() *big.Int {
	return s.walletSvc.GetChainID()
}

// SignTransaction signs an Ethereum transaction using the wallet's private key
// with EIP155 signing.
func (s *TxSigner) SignTransaction(ctx context.Context, tx *types.Transaction) (*types.Transaction, error) {
	return s.walletSvc.SignTransaction(ctx, tx)
}

// SendTransaction broadcasts a signed transaction to the network.
func (s *TxSigner) SendTransaction(ctx context.Context, signedTx *types.Transaction) error {
	if s.walletSvc.GetClient() == nil {
		return fmt.Errorf("ethereum client not available")
	}
	_, err := s.walletSvc.SendTransaction(ctx, signedTx)
	return err
}
