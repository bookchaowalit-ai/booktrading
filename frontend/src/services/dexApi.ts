/**
 * DEX API Service
 * Client for backend DEX/AMM endpoints
 */

import { getAuthToken } from './auth';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const token = getAuthToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

async function apiFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const response = await fetch(url, {
    ...options,
    headers: { ...authHeaders(), ...options.headers },
  });
  return response;
}

// ── Types ──────────────────────────────────────────────────────────────────────

export interface DexConfig {
  enabled: boolean;
  supportedChains: ChainInfo[];
  defaultChain: string;
  slippagePresets: number[];
}

export interface ChainInfo {
  id: string;
  name: string;
  nativeSymbol: string;
  blockExplorer: string;
}

export interface WalletInfo {
  id: string;
  address: string;
  chain: string;
  label?: string;
  createdAt: string;
  isLoaded: boolean;
}

export interface CreateWalletRequest {
  chain: string;
  label?: string;
}

export interface ImportWalletRequest {
  chain: string;
  privateKey: string;
  label?: string;
}

export interface BalanceInfo {
  address: string;
  native_balance: string;
  native_symbol: string;
  token_balances: Record<string, string>;
}

export interface TokenBalance {
  symbol: string;
  address: string;
  balance: string;
  decimals: number;
  priceUSD?: number;
}

export interface QuoteRequest {
  tokenIn: string;
  tokenOut: string;
  amountIn: string;
  slippage: number;
  bestRoute?: boolean;
}

export interface QuoteResponse {
  token_in: { address: string; symbol: string; name: string; decimals: number };
  token_out: { address: string; symbol: string; name: string; decimals: number };
  amount_in: string;
  amount_out: string;
  amount_out_min: string;
  price_impact: number;
  minimum_received: string;
  gas_estimate: number;
  route: string[];
  dex_provider: string;
}

export interface SwapRequest {
  walletId: string;
  tokenIn: string;
  tokenOut: string;
  amountIn: string;
  slippage: number;
  bestRoute?: boolean;
}

export interface SwapResponse {
  tx_hash: string;
  amount_in: string;
  amount_out: string;
  gas_used: number;
  gas_price: string;
  status: string;
  dex_provider: string;
  block_number: number;
}

export interface LiquidityPosition {
  id: string;
  pool: string;
  token0: string;
  token1: string;
  amount0: string;
  amount1: string;
  valueUSD: number;
  feesEarned: number;
  impermanentLoss: number;
  share: number;
}

export interface AddLiquidityRequest {
  walletId: string;
  token0: string;
  token1: string;
  amount0: string;
  amount1: string;
}

export interface RemoveLiquidityRequest {
  walletId: string;
  pool: string;
  lpAmount: string;
}

export interface ImpermanentLossResult {
  il_percentage: number;
  current_value_usd: number;
  hold_value_usd: number;
  loss_usd: number;
  token0_ratio: number;
  fees_earned_usd: number;
  net_result_usd: number;
  is_profitable: boolean;
}

// ── API Methods ────────────────────────────────────────────────────────────────

export const dexApi = {
  // Get DEX configuration
  async getConfig(): Promise<DexConfig> {
    const response = await apiFetch(`${API_BASE_URL}/api/dex/config`);
    if (!response.ok) throw new Error('Failed to fetch DEX config');
    return response.json();
  },

  // ── Wallet Endpoints ─────────────────────────────────────────────────────

  async createWallet(req: CreateWalletRequest): Promise<WalletInfo> {
    const response = await apiFetch(`${API_BASE_URL}/api/dex/wallets/create`, {
      method: 'POST',
      body: JSON.stringify(req),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ error: 'Failed to create wallet' }));
      throw new Error(err.error || 'Failed to create wallet');
    }
    return response.json();
  },

  async importWallet(req: ImportWalletRequest): Promise<WalletInfo> {
    const response = await apiFetch(`${API_BASE_URL}/api/dex/wallets/import`, {
      method: 'POST',
      body: JSON.stringify(req),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ error: 'Failed to import wallet' }));
      throw new Error(err.error || 'Failed to import wallet');
    }
    return response.json();
  },

  async getWallets(): Promise<WalletInfo[]> {
    const response = await apiFetch(`${API_BASE_URL}/api/dex/wallets`);
    if (!response.ok) throw new Error('Failed to fetch wallets');
    return response.json();
  },

  async loadWallet(walletId: string): Promise<{ walletId: string; address: string }> {
    const response = await apiFetch(`${API_BASE_URL}/api/dex/wallets/load`, {
      method: 'POST',
      body: JSON.stringify({ walletId }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ error: 'Failed to load wallet' }));
      throw new Error(err.error || 'Failed to load wallet');
    }
    return response.json();
  },

  async exportWallet(walletId: string): Promise<{ privateKey: string; address: string }> {
    const response = await apiFetch(`${API_BASE_URL}/api/dex/wallets/${encodeURIComponent(walletId)}/export`);
    if (!response.ok) {
      const err = await response.json().catch(() => ({ error: 'Failed to export wallet' }));
      throw new Error(err.error || 'Failed to export wallet');
    }
    return response.json();
  },

  async getBalance(address: string): Promise<BalanceInfo> {
    const response = await apiFetch(`${API_BASE_URL}/api/dex/balance?address=${encodeURIComponent(address)}`);
    if (!response.ok) throw new Error('Failed to fetch balance');
    return response.json();
  },

  // ── Swap Endpoints ───────────────────────────────────────────────────────

  async getQuote(req: QuoteRequest): Promise<QuoteResponse> {
    const params = new URLSearchParams({
      token_in: req.tokenIn,
      token_out: req.tokenOut,
      amount_in: req.amountIn,
      slippage: String(req.slippage),
      best_route: String(req.bestRoute ?? false),
    });
    const response = await apiFetch(`${API_BASE_URL}/api/dex/quote?${params}`);
    if (!response.ok) {
      const err = await response.json().catch(() => ({ error: 'Failed to get quote' }));
      throw new Error(err.error || 'Failed to get quote');
    }
    return response.json();
  },

  async swap(req: SwapRequest): Promise<SwapResponse> {
    const response = await apiFetch(`${API_BASE_URL}/api/dex/swap`, {
      method: 'POST',
      body: JSON.stringify({ token_in: req.tokenIn, token_out: req.tokenOut, amount_in: req.amountIn, slippage_pct: req.slippage }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ error: 'Swap failed' }));
      throw new Error(err.error || 'Swap failed');
    }
    return response.json();
  },

  // ── Transaction Status ─────────────────────────────────────────────────

  async getTransactionStatus(txHash: string): Promise<{ status: 'pending' | 'confirmed' | 'failed'; blockNumber?: number; confirmations?: number }> {
    const response = await apiFetch(`${API_BASE_URL}/api/dex/tx/${encodeURIComponent(txHash)}/status`);
    if (!response.ok) return { status: 'pending' };
    return response.json();
  },

  // ── Token Approval ───────────────────────────────────────────────────────

  async approveToken(req: { walletId: string; tokenAddress: string; amount: string }): Promise<{ txHash: string }> {
    const response = await apiFetch(`${API_BASE_URL}/api/dex/approve`, {
      method: 'POST',
      body: JSON.stringify({ token_address: req.tokenAddress, amount: req.amount }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ error: 'Approval failed' }));
      throw new Error(err.error || 'Approval failed');
    }
    return response.json();
  },

  // ── Liquidity Endpoints ──────────────────────────────────────────────────

  async getLiquidity(address: string): Promise<LiquidityPosition[]> {
    const response = await apiFetch(`${API_BASE_URL}/api/dex/liquidity?address=${encodeURIComponent(address)}`);
    if (!response.ok) throw new Error('Failed to fetch liquidity positions');
    return response.json();
  },

  async addLiquidity(req: AddLiquidityRequest): Promise<{ txHash: string; lpTokens: string }> {
    const response = await apiFetch(`${API_BASE_URL}/api/dex/liquidity/add`, {
      method: 'POST',
      body: JSON.stringify(req),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ error: 'Failed to add liquidity' }));
      throw new Error(err.error || 'Failed to add liquidity');
    }
    return response.json();
  },

  async removeLiquidity(req: RemoveLiquidityRequest): Promise<{ txHash: string; amount0: string; amount1: string }> {
    const response = await apiFetch(`${API_BASE_URL}/api/dex/liquidity/remove`, {
      method: 'POST',
      body: JSON.stringify({ pool_address: req.pool, lp_amount: req.lpAmount }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ error: 'Failed to remove liquidity' }));
      throw new Error(err.error || 'Failed to remove liquidity');
    }
    return response.json();
  },

  async calculateImpermanentLoss(
    priceRatio: number,
    initialDeposit: number,
    feeAPR: number,
    daysHeld: number
  ): Promise<ImpermanentLossResult> {
    const response = await apiFetch(`${API_BASE_URL}/api/dex/impermanent-loss`, {
      method: 'POST',
      body: JSON.stringify({ price_ratio: priceRatio, initial_deposit_usd: initialDeposit, fee_apr: feeAPR, days_held: daysHeld }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ error: 'Failed to calculate IL' }));
      throw new Error(err.error || 'Failed to calculate impermanent loss');
    }
    return response.json();
  },

  // ── Token Info ───────────────────────────────────────────────────────────

  async getTokenInfo(address: string): Promise<{ address: string; symbol: string; name: string; decimals: number }> {
    const response = await apiFetch(`${API_BASE_URL}/api/dex/token?address=${encodeURIComponent(address)}`);
    if (!response.ok) {
      throw new Error('Failed to fetch token info');
    }
    return response.json();
  },
};

export default dexApi;
