/**
 * Trading Pairs Configuration
 * Includes global and Thai-specific trading pairs
 */

export type ExchangeProvider =
  | 'binance'
  | 'binance_th'
  | 'bitkub'
  | 'satangpro'
  | 'ftx'
  | 'coinbase'
  | 'kraken';

export type AssetCategory = 'crypto' | 'forex' | 'commodity' | 'stock' | 'index';

export interface TradingPair {
  symbol: string;
  baseAsset: string;
  quoteAsset: string;
  category: AssetCategory;
  name: string;
  nameTH: string;
  exchanges: ExchangeProvider[];
  popular?: boolean;
  thaiPopular?: boolean;
}

// Popular trading pairs for Thai users
export const TRADING_PAIRS: TradingPair[] = [
  // === CRYPTO - THB Pairs (Most Popular in Thailand) ===
  {
    symbol: 'BTCUSDT',
    baseAsset: 'BTC',
    quoteAsset: 'USDT',
    category: 'crypto',
    name: 'Bitcoin / Tether',
    nameTH: 'บิตคอยน์ / เทเธอร์',
    exchanges: ['binance', 'bitkub', 'satangpro'],
    popular: true,
    thaiPopular: true,
  },
  {
    symbol: 'BTCTHB',
    baseAsset: 'BTC',
    quoteAsset: 'THB',
    category: 'crypto',
    name: 'Bitcoin / Thai Baht',
    nameTH: 'บิตคอยน์ / บาทไทย',
    exchanges: ['bitkub', 'satangpro'],
    popular: false,
    thaiPopular: true,
  },
  {
    symbol: 'ETHUSDT',
    baseAsset: 'ETH',
    quoteAsset: 'USDT',
    category: 'crypto',
    name: 'Ethereum / Tether',
    nameTH: 'อีเธอเรียม / เทเธอร์',
    exchanges: ['binance', 'bitkub', 'satangpro'],
    popular: true,
    thaiPopular: true,
  },
  {
    symbol: 'ETHTHB',
    baseAsset: 'ETH',
    quoteAsset: 'THB',
    category: 'crypto',
    name: 'Ethereum / Thai Baht',
    nameTH: 'อีเธอเรียม / บาทไทย',
    exchanges: ['bitkub', 'satangpro'],
    popular: false,
    thaiPopular: true,
  },
  {
    symbol: 'BNBUSDT',
    baseAsset: 'BNB',
    quoteAsset: 'USDT',
    category: 'crypto',
    name: 'Binance Coin / Tether',
    nameTH: 'ไบแนนซ์ คอยน์ / เทเธอร์',
    exchanges: ['binance'],
    popular: true,
    thaiPopular: true,
  },
  {
    symbol: 'XRPUSDT',
    baseAsset: 'XRP',
    quoteAsset: 'USDT',
    category: 'crypto',
    name: 'Ripple / Tether',
    nameTH: 'ริปเปิล / เทเธอร์',
    exchanges: ['binance', 'bitkub'],
    popular: true,
    thaiPopular: true,
  },
  {
    symbol: 'DOGEUSDT',
    baseAsset: 'DOGE',
    quoteAsset: 'USDT',
    category: 'crypto',
    name: 'Dogecoin / Tether',
    nameTH: 'โดจคอยน์ / เทเธอร์',
    exchanges: ['binance', 'bitkub'],
    popular: true,
    thaiPopular: true,
  },
  {
    symbol: 'ADAUSDT',
    baseAsset: 'ADA',
    quoteAsset: 'USDT',
    category: 'crypto',
    name: 'Cardano / Tether',
    nameTH: 'คาร์ดาโน / เทเธอร์',
    exchanges: ['binance', 'bitkub'],
    popular: true,
    thaiPopular: true,
  },
  {
    symbol: 'SOLUSDT',
    baseAsset: 'SOL',
    quoteAsset: 'USDT',
    category: 'crypto',
    name: 'Solana / Tether',
    nameTH: 'โซลานา / เทเธอร์',
    exchanges: ['binance'],
    popular: true,
    thaiPopular: true,
  },
  {
    symbol: 'DOTUSDT',
    baseAsset: 'DOT',
    quoteAsset: 'USDT',
    category: 'crypto',
    name: 'Polkadot / Tether',
    nameTH: 'โพลคาดอท / เทเธอร์',
    exchanges: ['binance', 'bitkub'],
    popular: true,
    thaiPopular: true,
  },
  {
    symbol: 'MATICUSDT',
    baseAsset: 'MATIC',
    quoteAsset: 'USDT',
    category: 'crypto',
    name: 'Polygon / Tether',
    nameTH: 'โพลีกอน / เทเธอร์',
    exchanges: ['binance', 'bitkub'],
    popular: true,
    thaiPopular: true,
  },
  {
    symbol: 'LINKUSDT',
    baseAsset: 'LINK',
    quoteAsset: 'USDT',
    category: 'crypto',
    name: 'Chainlink / Tether',
    nameTH: 'เชนลิงค์ / เทเธอร์',
    exchanges: ['binance', 'bitkub'],
    popular: true,
    thaiPopular: true,
  },
  {
    symbol: 'AVAXUSDT',
    baseAsset: 'AVAX',
    quoteAsset: 'USDT',
    category: 'crypto',
    name: 'Avalanche / Tether',
    nameTH: 'อาวาแลนช์ / เทเธอร์',
    exchanges: ['binance'],
    popular: true,
    thaiPopular: true,
  },
  {
    symbol: 'LTCUSDT',
    baseAsset: 'LTC',
    quoteAsset: 'USDT',
    category: 'crypto',
    name: 'Litecoin / Tether',
    nameTH: 'ไลต์คอยน์ / เทเธอร์',
    exchanges: ['binance', 'bitkub'],
    popular: true,
    thaiPopular: true,
  },
  {
    symbol: 'UNIUSDT',
    baseAsset: 'UNI',
    quoteAsset: 'USDT',
    category: 'crypto',
    name: 'Uniswap / Tether',
    nameTH: 'ยูนิสว랩 / เทเธอร์',
    exchanges: ['binance'],
    popular: false,
    thaiPopular: true,
  },
  {
    symbol: 'ATOMUSDT',
    baseAsset: 'ATOM',
    quoteAsset: 'USDT',
    category: 'crypto',
    name: 'Cosmos / Tether',
    nameTH: 'คอสโมส / เทเธอร์',
    exchanges: ['binance', 'bitkub'],
    popular: false,
    thaiPopular: true,
  },
  {
    symbol: 'FILUSDT',
    baseAsset: 'FIL',
    quoteAsset: 'USDT',
    category: 'crypto',
    name: 'Filecoin / Tether',
    nameTH: 'ไฟล์คอยน์ / เทเธอร์',
    exchanges: ['binance', 'bitkub'],
    popular: false,
    thaiPopular: true,
  },
  {
    symbol: 'MANAUSDT',
    baseAsset: 'MANA',
    quoteAsset: 'USDT',
    category: 'crypto',
    name: 'Decentraland / Tether',
    nameTH: 'ดีเซนทราแลนด์ / เทเธอร์',
    exchanges: ['binance', 'bitkub'],
    popular: false,
    thaiPopular: true,
  },
  {
    symbol: 'SANDUSDT',
    baseAsset: 'SAND',
    quoteAsset: 'USDT',
    category: 'crypto',
    name: 'The Sandbox / Tether',
    nameTH: 'เดอะ แซนด์บ็อกซ์ / เทเธอร์',
    exchanges: ['binance', 'bitkub'],
    popular: false,
    thaiPopular: true,
  },
  {
    symbol: 'THETAUSDT',
    baseAsset: 'THETA',
    quoteAsset: 'USDT',
    category: 'crypto',
    name: 'Theta Network / Tether',
    nameTH: 'ธีตา เน็ตเวิร์ก / เทเธอร์',
    exchanges: ['binance'],
    popular: false,
    thaiPopular: true,
  },
  
  // === FOREX - Major Pairs ===
  {
    symbol: 'EURUSD',
    baseAsset: 'EUR',
    quoteAsset: 'USD',
    category: 'forex',
    name: 'Euro / US Dollar',
    nameTH: 'ยูโร / ดอลลาร์สหรัฐ',
    exchanges: ['binance'],
    popular: true,
    thaiPopular: true,
  },
  {
    symbol: 'GBPUSD',
    baseAsset: 'GBP',
    quoteAsset: 'USD',
    category: 'forex',
    name: 'British Pound / US Dollar',
    nameTH: 'ปอนด์อังกฤษ / ดอลลาร์สหรัฐ',
    exchanges: ['binance'],
    popular: true,
    thaiPopular: true,
  },
  {
    symbol: 'USDJPY',
    baseAsset: 'USD',
    quoteAsset: 'JPY',
    category: 'forex',
    name: 'US Dollar / Japanese Yen',
    nameTH: 'ดอลลาร์สหรัฐ / เยนญี่ปุ่น',
    exchanges: ['binance'],
    popular: true,
    thaiPopular: true,
  },
  {
    symbol: 'USDCHF',
    baseAsset: 'USD',
    quoteAsset: 'CHF',
    category: 'forex',
    name: 'US Dollar / Swiss Franc',
    nameTH: 'ดอลลาร์สหรัฐ / ฟรังก์สวิส',
    exchanges: ['binance'],
    popular: true,
    thaiPopular: false,
  },
  {
    symbol: 'AUDUSD',
    baseAsset: 'AUD',
    quoteAsset: 'USD',
    category: 'forex',
    name: 'Australian Dollar / US Dollar',
    nameTH: 'ดอลลาร์ออสเตรเลีย / ดอลลาร์สหรัฐ',
    exchanges: ['binance'],
    popular: true,
    thaiPopular: true,
  },
  {
    symbol: 'USDCAD',
    baseAsset: 'USD',
    quoteAsset: 'CAD',
    category: 'forex',
    name: 'US Dollar / Canadian Dollar',
    nameTH: 'ดอลลาร์สหรัฐ / ดอลลาร์แคนาดา',
    exchanges: ['binance'],
    popular: true,
    thaiPopular: false,
  },
  {
    symbol: 'NZDUSD',
    baseAsset: 'NZD',
    quoteAsset: 'USD',
    category: 'forex',
    name: 'New Zealand Dollar / US Dollar',
    nameTH: 'ดอลลาร์นิวซีแลนด์ / ดอลลาร์สหรัฐ',
    exchanges: ['binance'],
    popular: false,
    thaiPopular: false,
  },
  {
    symbol: 'USDTHB',
    baseAsset: 'USD',
    quoteAsset: 'THB',
    category: 'forex',
    name: 'US Dollar / Thai Baht',
    nameTH: 'ดอลลาร์สหรัฐ / บาทไทย',
    exchanges: ['binance'],
    popular: false,
    thaiPopular: true,
  },
  
  // === COMMODITIES ===
  {
    symbol: 'XAUUSD',
    baseAsset: 'XAU',
    quoteAsset: 'USD',
    category: 'commodity',
    name: 'Gold / US Dollar',
    nameTH: 'ทองคำ / ดอลลาร์สหรัฐ',
    exchanges: ['binance'],
    popular: true,
    thaiPopular: true,
  },
  {
    symbol: 'XAGUSD',
    baseAsset: 'XAG',
    quoteAsset: 'USD',
    category: 'commodity',
    name: 'Silver / US Dollar',
    nameTH: 'เงิน / ดอลลาร์สหรัฐ',
    exchanges: ['binance'],
    popular: true,
    thaiPopular: true,
  },
  {
    symbol: 'USOIL',
    baseAsset: 'USOIL',
    quoteAsset: 'USD',
    category: 'commodity',
    name: 'US Crude Oil / WTI',
    nameTH: 'น้ำมันดิบสหรัฐ / WTI',
    exchanges: ['binance'],
    popular: true,
    thaiPopular: true,
  },
  {
    symbol: 'UKOIL',
    baseAsset: 'UKOIL',
    quoteAsset: 'USD',
    category: 'commodity',
    name: 'UK Crude Oil / Brent',
    nameTH: 'น้ำมันดิบอังกฤษ / Brent',
    exchanges: ['binance'],
    popular: true,
    thaiPopular: false,
  },
  {
    symbol: 'NATGAS',
    baseAsset: 'NATGAS',
    quoteAsset: 'USD',
    category: 'commodity',
    name: 'Natural Gas',
    nameTH: 'ก๊าซธรรมชาติ',
    exchanges: ['binance'],
    popular: false,
    thaiPopular: false,
  },
  {
    symbol: 'COPPER',
    baseAsset: 'COPPER',
    quoteAsset: 'USD',
    category: 'commodity',
    name: 'Copper',
    nameTH: 'ทองแดง',
    exchanges: ['binance'],
    popular: false,
    thaiPopular: false,
  },
  
  // === INDICES ===
  {
    symbol: 'SPX',
    baseAsset: 'SPX',
    quoteAsset: 'USD',
    category: 'index',
    name: 'S&P 500 Index',
    nameTH: 'ดัชนี S&P 500',
    exchanges: ['binance'],
    popular: true,
    thaiPopular: true,
  },
  {
    symbol: 'NDX',
    baseAsset: 'NDX',
    quoteAsset: 'USD',
    category: 'index',
    name: 'NASDAQ 100 Index',
    nameTH: 'ดัชนี NASDAQ 100',
    exchanges: ['binance'],
    popular: true,
    thaiPopular: true,
  },
  {
    symbol: 'DJI',
    baseAsset: 'DJI',
    quoteAsset: 'USD',
    category: 'index',
    name: 'Dow Jones Industrial Average',
    nameTH: 'ดาวโจนส์',
    exchanges: ['binance'],
    popular: true,
    thaiPopular: true,
  },
  {
    symbol: 'FTSE',
    baseAsset: 'FTSE',
    quoteAsset: 'GBP',
    category: 'index',
    name: 'FTSE 100 Index',
    nameTH: 'ดัชนี FTSE 100',
    exchanges: ['binance'],
    popular: false,
    thaiPopular: false,
  },
  {
    symbol: 'DAX',
    baseAsset: 'DAX',
    quoteAsset: 'EUR',
    category: 'index',
    name: 'DAX Index',
    nameTH: 'ดัชนี DAX',
    exchanges: ['binance'],
    popular: false,
    thaiPopular: false,
  },
  {
    symbol: 'N225',
    baseAsset: 'N225',
    quoteAsset: 'JPY',
    category: 'index',
    name: 'Nikkei 225 Index',
    nameTH: 'ดัชนี Nikkei 225',
    exchanges: ['binance'],
    popular: false,
    thaiPopular: true,
  },
  {
    symbol: 'HSI',
    baseAsset: 'HSI',
    quoteAsset: 'HKD',
    category: 'index',
    name: 'Hang Seng Index',
    nameTH: 'ดัชนี Hang Seng',
    exchanges: ['binance'],
    popular: false,
    thaiPopular: true,
  },
  
  // === STOCKS - US Tech Giants ===
  {
    symbol: 'AAPL',
    baseAsset: 'AAPL',
    quoteAsset: 'USD',
    category: 'stock',
    name: 'Apple Inc.',
    nameTH: 'แอปเปิล',
    exchanges: ['binance'],
    popular: true,
    thaiPopular: true,
  },
  {
    symbol: 'GOOGL',
    baseAsset: 'GOOGL',
    quoteAsset: 'USD',
    category: 'stock',
    name: 'Alphabet Inc. (Google)',
    nameTH: 'กูเกิล',
    exchanges: ['binance'],
    popular: true,
    thaiPopular: true,
  },
  {
    symbol: 'MSFT',
    baseAsset: 'MSFT',
    quoteAsset: 'USD',
    category: 'stock',
    name: 'Microsoft Corporation',
    nameTH: 'ไมโครซอฟท์',
    exchanges: ['binance'],
    popular: true,
    thaiPopular: true,
  },
  {
    symbol: 'AMZN',
    baseAsset: 'AMZN',
    quoteAsset: 'USD',
    category: 'stock',
    name: 'Amazon.com Inc.',
    nameTH: 'แอมะซอน',
    exchanges: ['binance'],
    popular: true,
    thaiPopular: true,
  },
  {
    symbol: 'TSLA',
    baseAsset: 'TSLA',
    quoteAsset: 'USD',
    category: 'stock',
    name: 'Tesla Inc.',
    nameTH: 'เทสลา',
    exchanges: ['binance'],
    popular: true,
    thaiPopular: true,
  },
  {
    symbol: 'META',
    baseAsset: 'META',
    quoteAsset: 'USD',
    category: 'stock',
    name: 'Meta Platforms (Facebook)',
    nameTH: 'เมตา (เฟสบุ๊ก)',
    exchanges: ['binance'],
    popular: true,
    thaiPopular: true,
  },
  {
    symbol: 'NVDA',
    baseAsset: 'NVDA',
    quoteAsset: 'USD',
    category: 'stock',
    name: 'NVIDIA Corporation',
    nameTH: 'เอ็นวิเดีย',
    exchanges: ['binance'],
    popular: true,
    thaiPopular: true,
  },
  {
    symbol: 'NFLX',
    baseAsset: 'NFLX',
    quoteAsset: 'USD',
    category: 'stock',
    name: 'Netflix Inc.',
    nameTH: 'เน็ตฟลิกซ์',
    exchanges: ['binance'],
    popular: true,
    thaiPopular: true,
  },
];

// Exchange provider details
export const EXCHANGE_PROVIDERS: Record<ExchangeProvider, {
  name: string;
  nameTH: string;
  url: string;
  logo?: string;
  thaiExchange: boolean;
}> = {
  binance: {
    name: 'Binance (Global)',
    nameTH: 'ไบแนนซ์ (ทั่วโลก)',
    url: 'https://www.binance.com',
    thaiExchange: false,
  },
  binance_th: {
    name: 'Binance TH (Thailand)',
    nameTH: 'ไบแนนซ์ ไทยแลนด์',
    url: 'https://www.binance.th',
    thaiExchange: true,
  },
  bitkub: {
    name: 'Bitkub',
    nameTH: 'บิทคับ',
    url: 'https://www.bitkub.com',
    thaiExchange: true,
  },
  satangpro: {
    name: 'Satang Pro',
    nameTH: 'สะตางค์ โปร',
    url: 'https://satang.pro',
    thaiExchange: true,
  },
  ftx: {
    name: 'FTX',
    nameTH: 'เอฟทีเอ็กซ์',
    url: 'https://ftx.com',
    thaiExchange: false,
  },
  coinbase: {
    name: 'Coinbase',
    nameTH: 'คอยน์เบส',
    url: 'https://www.coinbase.com',
    thaiExchange: false,
  },
  kraken: {
    name: 'Kraken',
    nameTH: 'คราเคน',
    url: 'https://www.kraken.com',
    thaiExchange: false,
  },
};

// Helper functions
export function getTradingPairsByCategory(category: AssetCategory): TradingPair[] {
  return TRADING_PAIRS.filter(pair => pair.category === category);
}

export function getPopularTradingPairs(): TradingPair[] {
  return TRADING_PAIRS.filter(pair => pair.popular);
}

export function getThaiPopularTradingPairs(): TradingPair[] {
  return TRADING_PAIRS.filter(pair => pair.thaiPopular);
}

export function getTradingPairsByExchange(exchange: ExchangeProvider): TradingPair[] {
  return TRADING_PAIRS.filter(pair => pair.exchanges.includes(exchange));
}

export function getThaiExchangePairs(): TradingPair[] {
  return TRADING_PAIRS.filter(pair => 
    pair.exchanges.some(ex => EXCHANGE_PROVIDERS[ex].thaiExchange)
  );
}

export function searchTradingPairs(query: string): TradingPair[] {
  const lowerQuery = query.toLowerCase();
  return TRADING_PAIRS.filter(pair => 
    pair.symbol.toLowerCase().includes(lowerQuery) ||
    pair.name.toLowerCase().includes(lowerQuery) ||
    pair.nameTH.includes(query) ||
    pair.baseAsset.toLowerCase().includes(lowerQuery)
  );
}

export function getTradingPairBySymbol(symbol: string): TradingPair | undefined {
  return TRADING_PAIRS.find(pair => pair.symbol === symbol);
}
