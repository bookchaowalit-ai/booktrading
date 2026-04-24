/**
 * Token icon registry using Trust Wallet Assets
 * Falls back to generated gradients for unknown tokens
 */

// Trust Wallet Assets CDN base URL
const TRUST_WALLET_ASSETS = 'https://raw.githubusercontent.com/trustwallet/assets/master/blockchains';

// Known token images (symbol -> icon URL)
export const TOKEN_ICONS: Record<string, { logoURI: string; color: string }> = {
  ETH: {
    logoURI: `${TRUST_WALLET_ASSETS}/ethereum/assets/0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2/logo.png`,
    color: '#627EEA',
  },
  USDC: {
    logoURI: `${TRUST_WALLET_ASSETS}/ethereum/assets/0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48/logo.png`,
    color: '#2775CA',
  },
  USDT: {
    logoURI: `${TRUST_WALLET_ASSETS}/ethereum/assets/0xdAC17F958D2ee523a2206206994597C13D831ec7/logo.png`,
    color: '#26A17B',
  },
  WBTC: {
    logoURI: `${TRUST_WALLET_ASSETS}/ethereum/assets/0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599/logo.png`,
    color: '#F09242',
  },
  DAI: {
    logoURI: `${TRUST_WALLET_ASSETS}/ethereum/assets/0x6B175474E89094C44Da98b954EedeAC495271d0F/logo.png`,
    color: '#F5AC37',
  },
  WETH: {
    logoURI: `${TRUST_WALLET_ASSETS}/ethereum/assets/0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2/logo.png`,
    color: '#627EEA',
  },
  ARB: {
    logoURI: `${TRUST_WALLET_ASSETS}/arbitrum/assets/0x912CE59144191C1204E64559FE8253a0e49E6548/logo.png`,
    color: '#28A0F0',
  },
  GMX: {
    logoURI: `${TRUST_WALLET_ASSETS}/arbitrum/assets/0xfc5A1A6EB076a2C7aD06eD22C90d7E710E35ad0a/logo.png`,
    color: '#3C50E0',
  },
  BNB: {
    logoURI: `${TRUST_WALLET_ASSETS}/binance/assets/BNB/logo.png`,
    color: '#F0B90B',
  },
  CAKE: {
    logoURI: `${TRUST_WALLET_ASSETS}/binance/assets/0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82/logo.png`,
    color: '#D1884F',
  },
  OP: {
    logoURI: `${TRUST_WALLET_ASSETS}/optimism/assets/0x4200000000000000000000000000000000000042/logo.png`,
    color: '#FF0420',
  },
  MATIC: {
    logoURI: `${TRUST_WALLET_ASSETS}/polygon/assets/0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270/logo.png`,
    color: '#8247E5',
  },
};

// Chain-specific token image URLs
const CHAIN_MAP: Record<string, string> = {
  ethereum: 'ethereum',
  arbitrum: 'arbitrum',
  base: 'ethereum', // Base tokens often use Ethereum images
  bsc: 'binance',
  optimism: 'optimism',
  polygon: 'polygon',
};

/**
 * Get token icon URL. Tries Trust Wallet first, falls back to generated gradient.
 */
export function getTokenIconUrl(symbol: string, chain: string = 'ethereum'): string | null {
  const known = TOKEN_ICONS[symbol.toUpperCase()];
  if (known?.logoURI) return known.logoURI;
  return null;
}

/**
 * Get the color for a token (used as fallback background)
 */
export function getTokenColor(symbol: string): string {
  return TOKEN_ICONS[symbol.toUpperCase()]?.color ?? '#6B7280';
}

/**
 * TokenIcon component - renders an image or fallback
 */
export function TokenIcon({ symbol, size = 24, chain = 'ethereum' }: { symbol: string; size?: number; chain?: string }) {
  const iconUrl = getTokenIconUrl(symbol, chain);
  const color = getTokenColor(symbol);

  if (iconUrl) {
    return (
      <img
        src={iconUrl}
        alt={symbol}
        width={size}
        height={size}
        className="rounded-full"
        style={{ width: size, height: size }}
        onError={(e) => {
          // Fallback to styled div on image error
          const target = e.target as HTMLImageElement;
          target.style.display = 'none';
          const fallback = document.createElement('div');
          fallback.className = 'rounded-full flex items-center justify-center text-white font-bold';
          fallback.style.cssText = `width:${size}px;height:${size}px;background:${color};font-size:${size * 0.4}px`;
          fallback.textContent = symbol.slice(0, 2);
          target.parentElement?.replaceChild(fallback, target);
        }}
      />
    );
  }

  return (
    <div
      className="rounded-full flex items-center justify-center text-white font-bold"
      style={{
        width: size,
        height: size,
        background: `linear-gradient(135deg, ${color}, ${color}dd)`,
        fontSize: size * 0.4,
      }}
    >
      {symbol.slice(0, 2)}
    </div>
  );
}
