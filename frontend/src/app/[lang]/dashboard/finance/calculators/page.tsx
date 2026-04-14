/**
 * Finance Calculators Page - Real Working Calculators
 * Compound Interest, Loan, Savings Goal, ROI calculators
 */
'use client';

import { useState } from 'react';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { Calculator, TrendingUp, DollarSign, Percent } from 'lucide-react';

export default function FinanceCalculatorsPage() {
  const [activeCalc, setActiveCalc] = useState<'compound' | 'loan' | 'savings' | 'roi'>('compound');

  // Compound Interest
  const [compound, setCompound] = useState({ principal: 10000, rate: 5, years: 10, compoundFreq: 12 });
  const compoundResult = compound.principal * Math.pow((1 + compound.rate / 100 / compound.compoundFreq), compound.compoundFreq * compound.years);

  // Loan
  const [loan, setLoan] = useState({ amount: 1000000, rate: 5, years: 30 });
  const monthlyRate = loan.rate / 100 / 12;
  const numPayments = loan.years * 12;
  const monthlyPayment = monthlyRate > 0 ? loan.amount * (monthlyRate * Math.pow(1 + monthlyRate, numPayments)) / (Math.pow(1 + monthlyRate, numPayments) - 1) : loan.amount / numPayments;
  const totalPayment = monthlyPayment * numPayments;
  const totalInterest = totalPayment - loan.amount;

  // Savings Goal
  const [savings, setSavings] = useState({ goal: 1000000, monthly: 10000, current: 0, rate: 3 });
  const monthsToGoal = savings.rate > 0
    ? Math.log((savings.goal * savings.rate / 100 / 12 + savings.monthly) / (savings.monthly)) / Math.log(1 + savings.rate / 100 / 12)
    : (savings.goal - savings.current) / savings.monthly;

  // ROI
  const [roi, setRoi] = useState({ invested: 10000, returned: 15000 });
  const roiPercent = ((roi.returned - roi.invested) / roi.invested) * 100;

  const formatCurrency = (n: number) => new Intl.NumberFormat('th-TH', { style: 'currency', currency: 'THB', minimumFractionDigits: 0 }).format(n);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Financial Calculators</h1>
        <p className="text-gray-500 dark:text-gray-400">Calculate compound interest, loans, savings goals, and ROI</p>
      </div>

      {/* Calculator Tabs */}
      <div className="flex gap-2 border-b border-gray-200 dark:border-gray-700">
        {[
          { id: 'compound', label: 'Compound Interest', icon: <TrendingUp className="w-4 h-4" /> },
          { id: 'loan', label: 'Loan Calculator', icon: <DollarSign className="w-4 h-4" /> },
          { id: 'savings', label: 'Savings Goal', icon: <Percent className="w-4 h-4" /> },
          { id: 'roi', label: 'ROI Calculator', icon: <Calculator className="w-4 h-4" /> },
        ].map((tab) => (
          <button key={tab.id} onClick={() => setActiveCalc(tab.id as any)}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${activeCalc === tab.id ? 'border-purple-600 text-purple-600 dark:text-purple-400' : 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'}`}>
            {tab.icon}{tab.label}
          </button>
        ))}
      </div>

      {/* Compound Interest */}
      {activeCalc === 'compound' && (
        <Card variant="elevated" className="p-6">
          <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-4">Compound Interest Calculator</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Principal (฿)</label>
              <input type="number" className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white" value={compound.principal} onChange={(e) => setCompound({ ...compound, principal: parseFloat(e.target.value) || 0 })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Annual Rate (%)</label>
              <input type="number" step="0.1" className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white" value={compound.rate} onChange={(e) => setCompound({ ...compound, rate: parseFloat(e.target.value) || 0 })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Years</label>
              <input type="number" className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white" value={compound.years} onChange={(e) => setCompound({ ...compound, years: parseInt(e.target.value) || 0 })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Compounds/Year</label>
              <select className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white" value={compound.compoundFreq} onChange={(e) => setCompound({ ...compound, compoundFreq: parseInt(e.target.value) })}>
                <option value={1}>Annually</option>
                <option value={4}>Quarterly</option>
                <option value={12}>Monthly</option>
                <option value={365}>Daily</option>
              </select>
            </div>
          </div>
          <div className="p-6 bg-purple-50 dark:bg-purple-900/20 rounded-xl">
            <p className="text-sm text-gray-500 dark:text-gray-400">Future Value</p>
            <p className="text-3xl font-bold text-purple-600">{formatCurrency(compoundResult)}</p>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">Interest Earned: {formatCurrency(compoundResult - compound.principal)}</p>
          </div>
        </Card>
      )}

      {/* Loan Calculator */}
      {activeCalc === 'loan' && (
        <Card variant="elevated" className="p-6">
          <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-4">Loan Calculator</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Loan Amount (฿)</label>
              <input type="number" className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white" value={loan.amount} onChange={(e) => setLoan({ ...loan, amount: parseFloat(e.target.value) || 0 })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Annual Rate (%)</label>
              <input type="number" step="0.1" className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white" value={loan.rate} onChange={(e) => setLoan({ ...loan, rate: parseFloat(e.target.value) || 0 })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Years</label>
              <input type="number" className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white" value={loan.years} onChange={(e) => setLoan({ ...loan, years: parseInt(e.target.value) || 0 })} />
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-6 bg-blue-50 dark:bg-blue-900/20 rounded-xl">
              <p className="text-sm text-gray-500 dark:text-gray-400">Monthly Payment</p>
              <p className="text-2xl font-bold text-blue-600">{formatCurrency(monthlyPayment)}</p>
            </div>
            <div className="p-6 bg-green-50 dark:bg-green-900/20 rounded-xl">
              <p className="text-sm text-gray-500 dark:text-gray-400">Total Payment</p>
              <p className="text-2xl font-bold text-green-600">{formatCurrency(totalPayment)}</p>
            </div>
            <div className="p-6 bg-red-50 dark:bg-red-900/20 rounded-xl">
              <p className="text-sm text-gray-500 dark:text-gray-400">Total Interest</p>
              <p className="text-2xl font-bold text-red-600">{formatCurrency(totalInterest)}</p>
            </div>
          </div>
        </Card>
      )}

      {/* Savings Goal */}
      {activeCalc === 'savings' && (
        <Card variant="elevated" className="p-6">
          <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-4">Savings Goal Calculator</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Goal (฿)</label>
              <input type="number" className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white" value={savings.goal} onChange={(e) => setSavings({ ...savings, goal: parseFloat(e.target.value) || 0 })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Current Savings (฿)</label>
              <input type="number" className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white" value={savings.current} onChange={(e) => setSavings({ ...savings, current: parseFloat(e.target.value) || 0 })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Monthly Savings (฿)</label>
              <input type="number" className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white" value={savings.monthly} onChange={(e) => setSavings({ ...savings, monthly: parseFloat(e.target.value) || 0 })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Annual Rate (%)</label>
              <input type="number" step="0.1" className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white" value={savings.rate} onChange={(e) => setSavings({ ...savings, rate: parseFloat(e.target.value) || 0 })} />
            </div>
          </div>
          <div className="p-6 bg-green-50 dark:bg-green-900/20 rounded-xl">
            <p className="text-sm text-gray-500 dark:text-gray-400">Time to Goal</p>
            <p className="text-3xl font-bold text-green-600">
              {isFinite(monthsToGoal) && monthsToGoal > 0 ? `${Math.ceil(monthsToGoal)} months (${(monthsToGoal / 12).toFixed(1)} years)` : 'Not achievable with current savings rate'}
            </p>
          </div>
        </Card>
      )}

      {/* ROI Calculator */}
      {activeCalc === 'roi' && (
        <Card variant="elevated" className="p-6">
          <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-4">ROI Calculator</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Amount Invested (฿)</label>
              <input type="number" className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white" value={roi.invested} onChange={(e) => setRoi({ ...roi, invested: parseFloat(e.target.value) || 0 })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Amount Returned (฿)</label>
              <input type="number" className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white" value={roi.returned} onChange={(e) => setRoi({ ...roi, returned: parseFloat(e.target.value) || 0 })} />
            </div>
          </div>
          <div className={`p-6 rounded-xl ${roiPercent >= 0 ? 'bg-green-50 dark:bg-green-900/20' : 'bg-red-50 dark:bg-red-900/20'}`}>
            <p className="text-sm text-gray-500 dark:text-gray-400">Return on Investment</p>
            <p className={`text-3xl font-bold ${roiPercent >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {roiPercent >= 0 ? '+' : ''}{roiPercent.toFixed(2)}%
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
              Profit/Loss: {formatCurrency(roi.returned - roi.invested)}
            </p>
          </div>
        </Card>
      )}
    </div>
  );
}
