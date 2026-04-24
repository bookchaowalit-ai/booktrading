package http

import (
	"encoding/json"
	"math/big"
	"net/http"
	"regexp"
	"strconv"
	"strings"

	"trading-bot-system/backend/internal/config"
	"trading-bot-system/backend/internal/domain/service"
	"trading-bot-system/backend/internal/logger"
)

var ethHashRegex = regexp.MustCompile(`^0x[a-fA-F0-9]{64}$`)

// DexHandler handles DEX/AMM HTTP requests
type DexHandler struct {
	dexService  *service.DexService
	walletSvc   *service.WalletService
	authHandler *AuthHandler
}

// NewDexHandler creates a new DEX handler
func NewDexHandler(dexService *service.DexService, walletSvc *service.WalletService, authHandler *AuthHandler) *DexHandler {
	return &DexHandler{
		dexService:  dexService,
		walletSvc:   walletSvc,
		authHandler: authHandler,
	}
}

// getUserID extracts user ID from request context
func (h *DexHandler) getUserID(r *http.Request) string {
	token := extractBearerToken(r)
	if token == "" {
		return ""
	}
	if h.authHandler != nil {
		userID, _ := h.authHandler.ValidateToken(token)
		return userID
	}
	return ""
}

// writeJSON writes a JSON response
func (h *DexHandler) writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

// writeError writes an error response
func (h *DexHandler) writeError(w http.ResponseWriter, status int, msg string) {
	h.writeJSON(w, status, map[string]string{"error": msg})
}

// parseBigInt parses a string to big.Int
func parseBigInt(s string) *big.Int {
	i, _ := new(big.Int).SetString(s, 10)
	if i == nil {
		return big.NewInt(0)
	}
	return i
}

// CreateWallet handles POST /api/dex/wallets - create a new DEX wallet
func (h *DexHandler) CreateWallet(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	userID := h.getUserID(r)
	if userID == "" {
		h.writeError(w, http.StatusUnauthorized, "Unauthorized")
		return
	}

	wallet, err := h.walletSvc.CreateWallet(r.Context(), userID)
	if err != nil {
		logger.Error("Failed to create wallet", "error", err)
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	h.writeJSON(w, http.StatusCreated, wallet)
}

// ImportWallet handles POST /api/dex/wallets/import - import an existing wallet
func (h *DexHandler) ImportWallet(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	userID := h.getUserID(r)
	if userID == "" {
		h.writeError(w, http.StatusUnauthorized, "Unauthorized")
		return
	}

	var req struct {
		PrivateKey string `json:"private_key"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.writeError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	wallet, err := h.walletSvc.ImportWallet(r.Context(), userID, req.PrivateKey)
	if err != nil {
		logger.Error("Failed to import wallet", "error", err)
		h.writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	h.writeJSON(w, http.StatusCreated, wallet)
}

// GetWallets handles GET /api/dex/wallets - list user wallets
func (h *DexHandler) GetWallets(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	userID := h.getUserID(r)
	if userID == "" {
		h.writeError(w, http.StatusUnauthorized, "Unauthorized")
		return
	}

	wallets, err := h.walletSvc.GetWallets(r.Context(), userID)
	if err != nil {
		logger.Error("Failed to get wallets", "error", err)
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	h.writeJSON(w, http.StatusOK, wallets)
}

// LoadWallet handles POST /api/dex/wallets/load - load a wallet for signing
func (h *DexHandler) LoadWallet(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	userID := h.getUserID(r)
	if userID == "" {
		h.writeError(w, http.StatusUnauthorized, "Unauthorized")
		return
	}

	var req struct {
		Address string `json:"address"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.writeError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	err := h.walletSvc.LoadWallet(r.Context(), userID, req.Address)
	if err != nil {
		h.writeError(w, http.StatusNotFound, err.Error())
		return
	}

	h.writeJSON(w, http.StatusOK, map[string]string{"status": "loaded", "address": req.Address})
}

// ExportWallet handles GET /api/dex/wallets/{id}/export - export private key
func (h *DexHandler) ExportWallet(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	userID := h.getUserID(r)
	if userID == "" {
		h.writeError(w, http.StatusUnauthorized, "Unauthorized")
		return
	}

	walletID := r.URL.Query().Get("id")
	if walletID == "" {
		h.writeError(w, http.StatusBadRequest, "Wallet ID required")
		return
	}

	privateKey, err := h.walletSvc.ExportWallet(r.Context(), userID, walletID)
	if err != nil {
		h.writeError(w, http.StatusNotFound, err.Error())
		return
	}

	h.writeJSON(w, http.StatusOK, map[string]string{
		"privateKey": privateKey,
	})
}

// GetBalance handles GET /api/dex/balance - get wallet balance
func (h *DexHandler) GetBalance(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	address := r.URL.Query().Get("address")
	if address == "" {
		h.writeError(w, http.StatusBadRequest, "address parameter required")
		return
	}

	nativeBalance, err := h.walletSvc.GetNativeBalance(r.Context(), address)
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	chainConfig := h.dexService.GetDEXConfig()
	symbol := "ETH"
	if len(chainConfig.Chains) > 0 {
		for _, chain := range chainConfig.Chains {
			symbol = chain.NativeCurrency
			break
		}
	}

	h.writeJSON(w, http.StatusOK, map[string]interface{}{
		"address":        address,
		"native_balance": nativeBalance.String(),
		"native_symbol":  symbol,
		"token_balances": map[string]interface{}{},
	})
}

// GetQuote handles GET /api/dex/quote - get a swap quote
func (h *DexHandler) GetQuote(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	tokenIn := r.URL.Query().Get("token_in")
	tokenOut := r.URL.Query().Get("token_out")
	amountInStr := r.URL.Query().Get("amount_in")
	slippageStr := r.URL.Query().Get("slippage")
	findBest := r.URL.Query().Get("best_route") == "true"

	if tokenIn == "" || tokenOut == "" || amountInStr == "" {
		h.writeError(w, http.StatusBadRequest, "token_in, token_out, and amount_in parameters required")
		return
	}

	amountIn := parseBigInt(amountInStr)
	slippage, err := strconv.ParseFloat(slippageStr, 64)
	if err != nil {
		slippage = 0.5
	}

	quote, err := h.dexService.GetSwapQuote(r.Context(), tokenIn, tokenOut, amountIn, slippage, findBest)
	if err != nil {
		h.writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	h.writeJSON(w, http.StatusOK, quote)
}

// Swap handles POST /api/dex/swap - execute a token swap
func (h *DexHandler) Swap(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	userID := h.getUserID(r)
	if userID == "" {
		h.writeError(w, http.StatusUnauthorized, "Unauthorized")
		return
	}

	var req struct {
		TokenIn     string  `json:"token_in"`
		TokenOut    string  `json:"token_out"`
		AmountIn    string  `json:"amount_in"`
		SlippagePct float64 `json:"slippage_pct"`
		WalletId    string  `json:"wallet_id"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.writeError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	if req.SlippagePct == 0 {
		req.SlippagePct = 0.5
	}

	amountIn := parseBigInt(req.AmountIn)
	result, err := h.dexService.SwapTokens(r.Context(), userID, req.WalletId, req.TokenIn, req.TokenOut, amountIn, req.SlippagePct)
	if err != nil {
		logger.Error("Swap failed", "error", err)
		h.writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	h.writeJSON(w, http.StatusOK, result)
}

// Approve handles POST /api/dex/approve - approve a token for the router
func (h *DexHandler) Approve(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	userID := h.getUserID(r)
	if userID == "" {
		h.writeError(w, http.StatusUnauthorized, "Unauthorized")
		return
	}

	var req struct {
		TokenAddress string `json:"token_address"`
		Amount       string `json:"amount"`
		WalletId     string `json:"wallet_id"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.writeError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	amount := parseBigInt(req.Amount)
	result, err := h.dexService.ApproveToken(r.Context(), userID, req.WalletId, req.TokenAddress, amount)
	if err != nil {
		logger.Error("Approve failed", "error", err)
		h.writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	h.writeJSON(w, http.StatusOK, result)
}

// CheckAllowance handles GET /api/dex/allowance - check token allowance
func (h *DexHandler) CheckAllowance(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	tokenAddress := r.URL.Query().Get("token_address")
	owner := r.URL.Query().Get("owner")
	spender := r.URL.Query().Get("spender")

	if tokenAddress == "" || owner == "" || spender == "" {
		h.writeError(w, http.StatusBadRequest, "token_address, owner, and spender parameters required")
		return
	}

	allowance, err := h.dexService.CheckAllowance(r.Context(), tokenAddress, owner, spender)
	if err != nil {
		h.writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	h.writeJSON(w, http.StatusOK, map[string]interface{}{
		"allowance":   allowance.String(),
		"sufficient": allowance.Cmp(big.NewInt(0)) > 0,
	})
}

// GetLiquidityPools handles GET /api/dex/liquidity - get LP positions
func (h *DexHandler) GetLiquidityPools(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	address := r.URL.Query().Get("address")
	if address == "" {
		h.writeError(w, http.StatusBadRequest, "address parameter required")
		return
	}

	positions, err := h.dexService.GetLiquidityPools(r.Context(), address)
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	h.writeJSON(w, http.StatusOK, positions)
}

// AddLiquidity handles POST /api/dex/liquidity/add - add liquidity
func (h *DexHandler) AddLiquidity(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	userID := h.getUserID(r)
	if userID == "" {
		h.writeError(w, http.StatusUnauthorized, "Unauthorized")
		return
	}

	var req struct {
		Token0  string `json:"token0"`
		Token1  string `json:"token1"`
		Amount0 string `json:"amount0"`
		Amount1 string `json:"amount1"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.writeError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	amount0 := parseBigInt(req.Amount0)
	amount1 := parseBigInt(req.Amount1)

	result, err := h.dexService.AddLiquidity(r.Context(), userID, req.Token0, req.Token1, amount0, amount1)
	if err != nil {
		logger.Error("Add liquidity failed", "error", err)
		h.writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	h.writeJSON(w, http.StatusOK, result)
}

// RemoveLiquidity handles POST /api/dex/liquidity/remove - remove liquidity
func (h *DexHandler) RemoveLiquidity(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	userID := h.getUserID(r)
	if userID == "" {
		h.writeError(w, http.StatusUnauthorized, "Unauthorized")
		return
	}

	var req struct {
		PoolAddress string `json:"pool_address"`
		LPAmount    string `json:"lp_amount"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.writeError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	lpAmount := parseBigInt(req.LPAmount)

	result, err := h.dexService.RemoveLiquidity(r.Context(), userID, req.PoolAddress, lpAmount)
	if err != nil {
		logger.Error("Remove liquidity failed", "error", err)
		h.writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	h.writeJSON(w, http.StatusOK, result)
}

// CalculateIL handles POST /api/dex/impermanent-loss - calculate impermanent loss
func (h *DexHandler) CalculateIL(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	var req struct {
		PriceRatio     float64 `json:"price_ratio"`
		InitialDeposit float64 `json:"initial_deposit_usd"`
		FeeAPR         float64 `json:"fee_apr"`
		DaysHeld       float64 `json:"days_held"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.writeError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	result := h.dexService.CalculateImpermanentLoss(req.PriceRatio, req.InitialDeposit, req.FeeAPR, req.DaysHeld)
	h.writeJSON(w, http.StatusOK, result)
}

// GetTxStatus handles GET /api/dex/tx/{hash}/status - get transaction status
func (h *DexHandler) GetTxStatus(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	// Extract tx hash from URL path: /api/dex/tx/{hash}/status
	path := strings.TrimPrefix(r.URL.Path, "/api/dex/tx/")
	txHash := strings.TrimSuffix(path, "/status")
	if txHash == "" || !ethHashRegex.MatchString(txHash) {
		h.writeError(w, http.StatusBadRequest, "invalid transaction hash")
		return
	}

	result, err := h.dexService.GetTransactionStatus(r.Context(), txHash)
	if err != nil {
		logger.Error("Failed to get tx status", "error", err)
		h.writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	h.writeJSON(w, http.StatusOK, result)
}

// GetConfig handles GET /api/dex/config - get DEX configuration
func (h *DexHandler) GetConfig(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	cfg := h.dexService.GetDEXConfig()
	h.writeJSON(w, http.StatusOK, map[string]interface{}{
		"enabled":          cfg.Enabled,
		"default_chain":    cfg.DefaultChain,
		"default_dex":      cfg.DefaultDEX,
		"slippage_pct":     cfg.SlippagePct,
		"max_price_impact": cfg.MaxPriceImpact,
		"chains":           cfg.Chains,
		"providers":        h.dexService.ListProviders(),
		"current_provider": h.dexService.GetCurrentProvider(),
	})
}

// SwitchProvider handles POST /api/dex/provider/switch - switch DEX provider
func (h *DexHandler) SwitchProvider(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	var req struct {
		Provider string `json:"provider"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.writeError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	err := h.dexService.SwitchProvider(config.DEXProvider(req.Provider))
	if err != nil {
		h.writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	h.writeJSON(w, http.StatusOK, map[string]string{"status": "ok", "provider": req.Provider})
}

// GetTokenInfo handles GET /api/dex/token - get ERC20 token info by address
func (h *DexHandler) GetTokenInfo(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	address := r.URL.Query().Get("address")
	if address == "" {
		h.writeError(w, http.StatusBadRequest, "address parameter required")
		return
	}

	token, err := h.dexService.GetTokenInfo(r.Context(), address)
	if err != nil {
		// Return a generic "Unknown" token instead of an error
		h.writeJSON(w, http.StatusOK, map[string]interface{}{
			"address":  address,
			"symbol":   "Unknown",
			"name":     "Unknown Token",
			"decimals": 18,
		})
		return
	}

	h.writeJSON(w, http.StatusOK, map[string]interface{}{
		"address":  token.Address,
		"symbol":   token.Symbol,
		"name":     token.Name,
		"decimals": token.Decimals,
	})
}

// RegisterRoutes registers all DEX routes
func (h *DexHandler) RegisterRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/api/dex/wallets", h.GetWallets)
	mux.HandleFunc("/api/dex/wallets/create", h.CreateWallet)
	mux.HandleFunc("/api/dex/wallets/import", h.ImportWallet)
	mux.HandleFunc("/api/dex/wallets/load", h.LoadWallet)
	mux.HandleFunc("/api/dex/wallets/export", h.ExportWallet)
	mux.HandleFunc("/api/dex/balance", h.GetBalance)
	mux.HandleFunc("/api/dex/quote", h.GetQuote)
	mux.HandleFunc("/api/dex/swap", h.Swap)
	mux.HandleFunc("/api/dex/approve", h.Approve)
	mux.HandleFunc("/api/dex/token", h.GetTokenInfo)
	mux.HandleFunc("/api/dex/allowance", h.CheckAllowance)
	mux.HandleFunc("/api/dex/liquidity", h.GetLiquidityPools)
	mux.HandleFunc("/api/dex/liquidity/add", h.AddLiquidity)
	mux.HandleFunc("/api/dex/liquidity/remove", h.RemoveLiquidity)
	mux.HandleFunc("/api/dex/impermanent-loss", h.CalculateIL)
	mux.HandleFunc("/api/dex/config", h.GetConfig)
	mux.HandleFunc("/api/dex/provider/switch", h.SwitchProvider)
	mux.HandleFunc("/api/dex/tx/", h.GetTxStatus)
}
