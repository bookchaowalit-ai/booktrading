const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

export interface DCABot {
  id: string;
  symbol: string;
  investment_amount: number;
  interval_minutes: number;
  take_profit_percent: number;
  safety_order_multiplier: number;
  max_safety_orders: number;
  price_deviation_percent: number;
  status: string;
  total_invested: number;
  total_sold: number;
  current_position_qty: number;
  avg_entry_price: number;
  created_at: string;
  started_at: string | null;
  stopped_at: string | null;
}

export interface DCAOrder {
  id: string;
  bot_id: string;
  order_type: string; // BASE, SAFETY, TAKE_PROFIT
  side: string;
  quantity: number;
  price: number;
  total: number;
  status: string;
  order_number: number;
  executed_at: string | null;
  created_at: string;
}

export interface DCACreateRequest {
  symbol: string;
  investment_amount: number;
  interval_minutes: number;
  take_profit_percent: number;
  safety_order_multiplier: number;
  max_safety_orders: number;
  price_deviation_percent: number;
}

function getAuthToken() {
  if (typeof window === 'undefined') return '';
  return localStorage.getItem('auth_token') || '';
}

export const dcaApi = {
  async createBot(bot: DCACreateRequest): Promise<DCABot> {
    const res = await fetch(`${API_BASE_URL}/api/dca/bots`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getAuthToken()}` },
      body: JSON.stringify(bot),
    });
    if (!res.ok) throw new Error('Failed to create DCA bot');
    return res.json();
  },

  async getBots(): Promise<DCABot[]> {
    const res = await fetch(`${API_BASE_URL}/api/dca/bots`, {
      headers: { Authorization: `Bearer ${getAuthToken()}` },
    });
    if (!res.ok) throw new Error('Failed to get DCA bots');
    return res.json();
  },

  async startBot(id: string): Promise<void> {
    const res = await fetch(`${API_BASE_URL}/api/dca/bots/${id}/start`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${getAuthToken()}` },
    });
    if (!res.ok) throw new Error('Failed to start DCA bot');
  },

  async stopBot(id: string): Promise<void> {
    const res = await fetch(`${API_BASE_URL}/api/dca/bots/${id}/stop`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${getAuthToken()}` },
    });
    if (!res.ok) throw new Error('Failed to stop DCA bot');
  },

  async deleteBot(id: string): Promise<void> {
    const res = await fetch(`${API_BASE_URL}/api/dca/bots/${id}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${getAuthToken()}` },
    });
    if (!res.ok) throw new Error('Failed to delete DCA bot');
  },

  async getBotOrders(id: string): Promise<DCAOrder[]> {
    const res = await fetch(`${API_BASE_URL}/api/dca/bots/${id}/orders`, {
      headers: { Authorization: `Bearer ${getAuthToken()}` },
    });
    if (!res.ok) throw new Error('Failed to get bot orders');
    return res.json();
  },
};
