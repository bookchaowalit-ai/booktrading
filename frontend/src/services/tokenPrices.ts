/**
 * Token price service using CoinGecko free API
 * Maps token addresses to CoinGecko IDs and fetches USD prices
 */

// Token address → CoinGecko ID mapping
const TOKEN_TO_COINGECKO: Record<string, string> = {
  'NATIVE': 'ethereum',
  '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48': 'usd-coin',
  '0xdAC17F958D2ee523a2206206994597C13D831ec7': 'tether',
  '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599': 'wrapped-bitcoin',
  '0x6B175474E89094C44Da98b954EedeAC495271d0F': 'dai',
  '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2': 'weth',
  // Arbitrum
  '0x912CE59144191C1204E64559FE8253a0e49E6548': 'arbitrum',
  '0xfc5A1A6EB076a2C7aD06eD22C90d7E710E35ad0a': 'gmx',
  // BSC
  'BNB': 'binancecoin',
  '0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82': 'pancakeswap-token',
  // Optimism
  '0x4200000000000000000000000000000000000042': 'optimism',
  // Polygon
  '0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270': 'matic-network',
};

// Cache: address → { price, timestamp }
interface PriceCache {
  [address: string]: { price: number; timestamp: number };
}

const CACHE_DURATION = 60_000; // 1 minute
let priceCache: PriceCache = {};
let lastFetch = 0;
let fetchPromise: Promise<Record<string, number>> | null = null;

/**
 * Fetch USD prices for all tracked tokens from CoinGecko
 * Uses the /simple/price endpoint with contract addresses
 */
export async function fetchTokenPrices(): Promise<Record<string, number>> {
  const now = Date.now();

  // Return cached prices if fresh
  if (lastFetch > 0 && now - lastFetch < CACHE_DURATION) {
    const result: Record<string, number> = {};
    for (const [addr, entry] of Object.entries(priceCache)) {
      result[addr] = entry.price;
    }
    return result;
  }

  // Deduplicate concurrent fetches
  if (fetchPromise) return fetchPromise;

  fetchPromise = (async () => {
    const addresses = Object.keys(TOKEN_TO_COINGECKO).filter((a) => a !== 'NATIVE' && a !== 'BNB');
    const cgIds = Object.values(TOKEN_TO_COINGECKO);

    const result: Record<string, number> = {};

    try {
      // Fetch by contract addresses (Ethereum mainnet)
      const contractIds = addresses.join(',');
      const contractUrl = `https://api.coingecko.com/api/v3/simple/token_price/ethereum?contract_addresses=${contractIds}&vs_currencies=usd`;
      const response = await fetch(contractUrl);

      if (response.ok) {
        const data: Record<string, { usd: number }> = await response.json();
        for (const [addr, info] of Object.entries(data)) {
          result[addr] = info.usd;
        }
      }

      // Fetch native ETH and BNB by coin ID
      const idUrl = `https://api.coingecko.com/api/v3/simple/price?ids=${cgIds.join(',')}&vs_currencies=usd`;
      const idResponse = await fetch(idUrl);
      if (idResponse.ok) {
        const idData: Record<string, { usd: number }> = await idResponse.json();
        // Map coin IDs back to addresses
        for (const [addr, cgId] of Object.entries(TOKEN_TO_COINGECKO)) {
          if (idData[cgId]) {
            result[addr] = idData[cgId].usd;
          }
        }
      }
    } catch {
      // Return stale cache on error
      for (const [addr, entry] of Object.entries(priceCache)) {
        result[addr] = entry.price;
      }
    }

    // Update cache
    priceCache = {};
    for (const [addr, price] of Object.entries(result)) {
      if (price > 0) {
        priceCache[addr] = { price, timestamp: now };
      }
    }
    lastFetch = now;
    fetchPromise = null;
    return result;
  })();

  return fetchPromise;
}

/**
 * Get cached price for a single token address
 */
export function getTokenPrice(address: string): number | null {
  const entry = priceCache[address];
  if (entry && Date.now() - entry.timestamp < CACHE_DURATION * 5) {
    return entry.price;
  }
  return null;
}

/**
 * Format a token amount as USD value
 */
export function formatUSD(amount: number, price: number | null): string | null {
  if (!price || price <= 0) return null;
  const value = amount * price;
  if (value < 0.01) return '< $0.01';
  return `$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
