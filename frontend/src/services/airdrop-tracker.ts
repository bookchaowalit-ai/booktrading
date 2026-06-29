/**
 * Airdrop Task Tracker Service
 * API client for tracking airdrop tasks and completion status
 */

const STRATEGY_URL = process.env.NEXT_PUBLIC_STRATEGY_URL || 'http://localhost:8001';

export interface AirdropSubtask {
  title: string;
  completed: boolean;
}

export interface AirdropTask {
  task_id: string;
  name: string;
  chain: string;
  task_description: string;
  estimated_value: string;
  difficulty: string;
  cost: string;
  url: string;
  deadline: string;
  status: 'not_started' | 'in_progress' | 'completed' | 'expired';
  subtasks: AirdropSubtask[];
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface AirdropTrackerStats {
  total: number;
  by_status: Record<string, number>;
  total_estimated_low: number;
}

export const airdropTrackerService = {
  /**
   * List all tracked airdrop tasks
   */
  async getTasks(): Promise<{ tasks: AirdropTask[]; stats: AirdropTrackerStats }> {
    const res = await fetch(`${STRATEGY_URL}/api/airdrop-tracker/tasks`);
    if (!res.ok) throw new Error('Failed to fetch airdrop tasks');
    return res.json();
  },

  /**
   * Add a new airdrop task
   */
  async addTask(task: Partial<AirdropTask>): Promise<{ task: AirdropTask }> {
    const res = await fetch(`${STRATEGY_URL}/api/airdrop-tracker/tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(task),
    });
    if (!res.ok) throw new Error('Failed to add airdrop task');
    return res.json();
  },

  /**
   * Update an existing airdrop task
   */
  async updateTask(taskId: string, updates: Partial<AirdropTask>): Promise<{ task: AirdropTask }> {
    const res = await fetch(`${STRATEGY_URL}/api/airdrop-tracker/tasks/${taskId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    });
    if (!res.ok) throw new Error('Failed to update airdrop task');
    return res.json();
  },

  /**
   * Toggle a subtask completion
   */
  async toggleSubtask(taskId: string, subtaskIdx: number, completed: boolean): Promise<{ task: AirdropTask }> {
    const res = await fetch(`${STRATEGY_URL}/api/airdrop-tracker/tasks/${taskId}/subtasks/${subtaskIdx}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ completed }),
    });
    if (!res.ok) throw new Error('Failed to update subtask');
    return res.json();
  },

  /**
   * Delete an airdrop task
   */
  async deleteTask(taskId: string): Promise<{ deleted: boolean }> {
    const res = await fetch(`${STRATEGY_URL}/api/airdrop-tracker/tasks/${taskId}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error('Failed to delete airdrop task');
    return res.json();
  },

  /**
   * Get tracker statistics
   */
  async getStats(): Promise<AirdropTrackerStats> {
    const res = await fetch(`${STRATEGY_URL}/api/airdrop-tracker/stats`);
    if (!res.ok) throw new Error('Failed to fetch stats');
    return res.json();
  },
};
