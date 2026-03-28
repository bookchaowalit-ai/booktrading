/**
 * Zustand store for application state management.
 */
import { create } from 'zustand';
import { BotStatus, MarketData, Order, Portfolio, TechnicalIndicators, TradeHistory } from '@/types';
import { api } from '@/services/api';
import { wsService } from '@/services/websocket';

interface AppState {
  // Bot State
  botStatus: BotStatus | null;
  isBotLoading: boolean;

  // Market Data
  marketData: Record<string, MarketData>;
  
  // Portfolio
  portfolio: Portfolio[];
  
  // Orders
  orders: Order[];
  
  // Trade History
  tradeHistory: TradeHistory[];
  
  // Technical Indicators
  indicators: Record<string, TechnicalIndicators>;

  // Actions
  setBotStatus: (status: BotStatus) => void;
  updateMarketData: (data: MarketData) => void;
  setPortfolio: (portfolio: Portfolio[]) => void;
  setOrders: (orders: Order[]) => void;
  addOrder: (order: Order) => void;
  setTradeHistory: (trades: TradeHistory[]) => void;
  setIndicators: (indicators: Record<string, TechnicalIndicators>) => void;
  
  // Bot Control Actions
  startBot: () => Promise<void>;
  stopBot: () => Promise<void>;
  refreshBotStatus: () => Promise<void>;
  
  // Data Refresh Actions
  refreshPortfolio: () => Promise<void>;
  refreshOrders: () => Promise<void>;
  refreshTradeHistory: () => Promise<void>;
  refreshIndicators: () => Promise<void>;
  
  // WebSocket
  connectWebSocket: () => void;
  disconnectWebSocket: () => void;
}

export const useAppStore = create<AppState>((set, get) => ({
  // Initial State
  botStatus: null,
  isBotLoading: false,
  marketData: {},
  portfolio: [],
  orders: [],
  tradeHistory: [],
  indicators: {},

  // Actions
  setBotStatus: (status) => set({ botStatus: status }),
  
  updateMarketData: (data) => set((state) => ({
    marketData: {
      ...state.marketData,
      [data.symbol]: data,
    },
  })),
  
  setPortfolio: (portfolio) => set({ portfolio }),
  
  setOrders: (orders) => set({ orders }),
  
  addOrder: (order) => set((state) => ({
    orders: [order, ...state.orders],
  })),
  
  setTradeHistory: (trades) => set({ tradeHistory: trades }),
  
  setIndicators: (indicators) => set({ indicators }),

  // Bot Control
  startBot: async () => {
    set({ isBotLoading: true });
    try {
      await api.startBot();
      await get().refreshBotStatus();
    } finally {
      set({ isBotLoading: false });
    }
  },

  stopBot: async () => {
    set({ isBotLoading: true });
    try {
      await api.stopBot();
      await get().refreshBotStatus();
    } finally {
      set({ isBotLoading: false });
    }
  },
  
  refreshBotStatus: async () => {
    try {
      const status = await api.getBotStatus();
      set({ botStatus: status });
    } catch {
      // silently ignore - UI will show last known state
    }
  },

  // Data Refresh
  refreshPortfolio: async () => {
    try {
      const portfolio = await api.getPortfolio();
      set({ portfolio });
    } catch {
      // silently ignore
    }
  },
  
  refreshOrders: async () => {
    try {
      const orders = await api.getOrders();
      set({ orders });
    } catch {
      // silently ignore
    }
  },
  
  refreshTradeHistory: async () => {
    try {
      const trades = await api.getTradeHistory();
      set({ tradeHistory: trades });
    } catch {
      // silently ignore
    }
  },
  
  refreshIndicators: async () => {
    try {
      const indicators = await api.getIndicators();
      set({ indicators });
    } catch {
      // silently ignore
    }
  },

  // WebSocket
  connectWebSocket: () => {
    wsService.connect();
    
    // Subscribe to real-time updates
    wsService.onMarketData((data) => {
      get().updateMarketData(data);
    });
    
    wsService.onBotStatus((status) => {
      get().setBotStatus(status);
    });
    
    wsService.onOrderUpdate((order) => {
      get().addOrder(order);
    });
  },
  
  disconnectWebSocket: () => {
    wsService.disconnect();
  },
}));
