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
  chain: string;
  nativeBalance: string;
  nativeSymbol: string;
  tokens: TokenBalance[];
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
  amountOut: string;
  priceImpact: number;
  minimumReceived: string;
  gasEstimate: string;
  route: RouteHop[];
  dexProvider: string;
  exchangeRate: string;
}

export interface RouteHop {
  dex: string;
  tokenIn: string;
  tokenOut: string;
  amountIn: string;
  amountOut: string;
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
  txHash: string;
  amountOut: string;
  route: RouteHop[];
  dexProvider: string;
  gasUsed: string;
  timestamp: string;
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
  token0: string;
  token1: string;
  priceRatioChange: number;
  impermanentLoss: number;
  valueIfHeld: number;
  valueInPool: number;
  loss: number;
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
      body: JSON.stringify(req),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ error: 'Swap failed' }));
      throw new Error(err.error || 'Swap failed');
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
      body: JSON.stringify(req),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ error: 'Failed to remove liquidity' }));
      throw new Error(err.error || 'Failed to remove liquidity');
    }
    return response.json();
  },

  async calculateImpermanentLoss(
    token0: string,
    token1: string,
    initialPriceRatio: number,
    currentPriceRatio: number
  ): Promise<ImpermanentLossResult> {
    const response = await apiFetch(`${API_BASE_URL}/api/dex/impermanent-loss`, {
      method: 'POST',
      body: JSON.stringify({ token0, token1, initialPriceRatio, currentPriceRatio }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ error: 'Failed to calculate IL' }));
      throw new Error(err.error || 'Failed to calculate impermanent loss');
    }
    return response.json();
  },
};

export default dexApi;
