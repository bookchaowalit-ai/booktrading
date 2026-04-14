package service

import (
	"math"

	"trading-bot-system/backend/internal/domain/model"
)

// FinancialCalculatorService provides financial engineering calculations
type FinancialCalculatorService struct{}

// NewFinancialCalculatorService creates a new financial calculator service
func NewFinancialCalculatorService() *FinancialCalculatorService {
	return &FinancialCalculatorService{}
}

// CalculateCompoundInterest calculates compound interest with optional monthly contributions
func (s *FinancialCalculatorService) CalculateCompoundInterest(input *model.CompoundInterestInput) *model.CompoundInterestResult {
	// A = P(1 + r/n)^(nt) + PMT * (((1 + r/n)^(nt) - 1) / (r/n))

	principal := input.Principal
	rate := input.AnnualRate / 100 // Convert percentage to decimal
	n := float64(input.CompoundsPerYear)
	t := float64(input.Years)
	pmt := input.MonthlyContribution

	// Calculate future value of principal
	fvPrincipal := principal * math.Pow(1+rate/n, n*t)

	// Calculate future value of monthly contributions
	var fvContributions float64
	if rate > 0 {
		fvContributions = pmt * 12 * ((math.Pow(1+rate/n, n*t) - 1) / rate)
	} else {
		fvContributions = pmt * 12 * t
	}

	futureValue := fvPrincipal + fvContributions
	totalContributions := principal + (pmt * 12 * t)
	totalInterest := futureValue - totalContributions

	// Calculate yearly breakdown
	yearlyBreakdown := make([]model.YearlyBreakdown, 0, input.Years)
	balance := principal

	for year := 1; year <= input.Years; year++ {
		startBalance := balance
		contributions := pmt * 12

		// Interest for this year
		interest := balance*math.Pow(1+rate/n, n) - balance +
			pmt*12*((math.Pow(1+rate/n, n)-1)/(rate/n)) - contributions

		balance = startBalance + contributions + interest

		yearlyBreakdown = append(yearlyBreakdown, model.YearlyBreakdown{
			Year:          year,
			StartBalance:  startBalance,
			Contributions: contributions,
			Interest:      interest,
			EndBalance:    balance,
		})
	}

	return &model.CompoundInterestResult{
		FutureValue:        futureValue,
		TotalContributions: totalContributions,
		TotalInterest:      totalInterest,
		YearlyBreakdown:    yearlyBreakdown,
	}
}

// CalculateLoan calculates loan payments and amortization schedule
func (s *FinancialCalculatorService) CalculateLoan(input *model.LoanCalculatorInput) *model.LoanCalculatorResult {
	// M = P * r * (1 + r)^n / ((1 + r)^n - 1)

	principal := input.Principal - input.DownPayment
	rate := input.AnnualRate / 100 / 12 // Monthly rate
	nMonths := input.Years * 12          // Total months

	if principal <= 0 {
		return &model.LoanCalculatorResult{
			MonthlyPayment: 0,
			TotalPayment:   0,
			TotalInterest:  0,
			LoanAmount:     0,
			Schedule:       []model.LoanPayment{},
		}
	}

	// Calculate monthly payment
	var monthlyPayment float64
	if rate > 0 {
		monthlyPayment = principal * rate * math.Pow(1+rate, float64(nMonths)) / (math.Pow(1+rate, float64(nMonths)) - 1)
	} else {
		monthlyPayment = principal / float64(nMonths)
	}

	totalPayment := monthlyPayment * float64(nMonths)
	totalInterest := totalPayment - principal

	// Generate amortization schedule
	schedule := make([]model.LoanPayment, 0, nMonths)
	balance := principal

	for month := 1; month <= nMonths; month++ {
		interestPayment := balance * rate
		principalPayment := monthlyPayment - interestPayment
		
		// Adjust for final payment
		if balance < monthlyPayment {
			principalPayment = balance
			interestPayment = balance * rate
		}
		
		balance -= principalPayment
		if balance < 0 {
			balance = 0
		}

		schedule = append(schedule, model.LoanPayment{
			Month:     month,
			Payment:   monthlyPayment,
			Principal: principalPayment,
			Interest:  interestPayment,
			Balance:   balance,
		})
	}

	return &model.LoanCalculatorResult{
		MonthlyPayment: monthlyPayment,
		TotalPayment:   totalPayment,
		TotalInterest:  totalInterest,
		LoanAmount:     principal,
		Schedule:       schedule,
	}
}

// CalculateTimeToGoal calculates how long it will take to reach a savings goal
func (s *FinancialCalculatorService) CalculateTimeToGoal(targetAmount, currentAmount, monthlyContribution, annualRate float64) int {
	if monthlyContribution <= 0 {
		return -1 // Never reachable
	}

	remaining := targetAmount - currentAmount
	if remaining <= 0 {
		return 0 // Already reached
	}

	rate := annualRate / 100 / 12 // Monthly rate

	if rate <= 0 {
		// No interest - simple division
		return int(math.Ceil(remaining / monthlyContribution))
	}

	// With compound interest: FV = PMT * ((1+r)^n - 1) / r
	// n = log(1 + FV * r / PMT) / log(1 + r)
	fvNeeded := remaining
	n := math.Log(1 + fvNeeded * rate / monthlyContribution) / math.Log(1 + rate)
	
	return int(math.Ceil(n))
}

// CalculateEmergencyFundTarget calculates recommended emergency fund based on expenses
func (s *FinancialCalculatorService) CalculateEmergencyFundTarget(monthlyExpenses float64, monthsCoverage int) float64 {
	return monthlyExpenses * float64(monthsCoverage)
}

// CalculateDebtToIncomeRatio calculates debt-to-income ratio
func (s *FinancialCalculatorService) CalculateDebtToIncomeRatio(totalMonthlyDebtPayments, grossMonthlyIncome float64) float64 {
	if grossMonthlyIncome <= 0 {
		return 0
	}
	return (totalMonthlyDebtPayments / grossMonthlyIncome) * 100
}

// CalculateSavingsRate calculates personal savings rate
func (s *FinancialCalculatorService) CalculateSavingsRate(income, expenses float64) float64 {
	if income <= 0 {
		return 0
	}
	savings := income - expenses
	return (savings / income) * 100
}

// CalculateNetWorthGrowth calculates percentage growth in net worth
func (s *FinancialCalculatorService) CalculateNetWorthGrowth(previousNetWorth, currentNetWorth float64) float64 {
	if previousNetWorth <= 0 {
		if currentNetWorth > 0 {
			return 100 // From zero to positive is 100% growth
		}
		return 0
	}
	return ((currentNetWorth - previousNetWorth) / previousNetWorth) * 100
}

// CalculateRuleOf72 calculates years to double investment using Rule of 72
func (s *FinancialCalculatorService) CalculateRuleOf72(annualRate float64) float64 {
	if annualRate <= 0 {
		return -1 // Never doubles
	}
	return 72 / annualRate
}

// CalculateInflationAdjustedReturn calculates real return after inflation
func (s *FinancialCalculatorService) CalculateInflationAdjustedReturn(nominalReturn, inflationRate float64) float64 {
	// Real return = ((1 + nominal) / (1 + inflation)) - 1
	nominal := nominalReturn / 100
	inflation := inflationRate / 100
	
	return ((1 + nominal) / (1 + inflation) - 1) * 100
}

// CalculatePresentValue calculates present value of future amount
func (s *FinancialCalculatorService) CalculatePresentValue(futureValue, annualRate, years float64) float64 {
	// PV = FV / (1 + r)^n
	rate := annualRate / 100
	return futureValue / math.Pow(1 + rate, years)
}

// CalculateFutureValue calculates future value of present amount
func (s *FinancialCalculatorService) CalculateFutureValue(presentValue, annualRate, years float64) float64 {
	// FV = PV * (1 + r)^n
	rate := annualRate / 100
	return presentValue * math.Pow(1 + rate, years)
}

// CalculateAnnuityPayment calculates payment from an annuity
func (s *FinancialCalculatorService) CalculateAnnuityPayment(principal, annualRate, years float64) float64 {
	// PMT = P * r / (1 - (1 + r)^-n)
	rate := annualRate / 100 / 12
	n := years * 12
	
	if rate <= 0 {
		return principal / n
	}
	
	return principal * rate / (1 - math.Pow(1 + rate, -n))
}

// CalculateBreakevenPoint calculates breakeven point for an investment
func (s *FinancialCalculatorService) CalculateBreakevenPoint(totalCost, revenuePerUnit, costPerUnit float64) int {
	if revenuePerUnit <= costPerUnit {
		return -1 // Never breakeven
	}
	contributionMargin := revenuePerUnit - costPerUnit
	return int(math.Ceil(totalCost / contributionMargin))
}

// CalculateROI calculates Return on Investment
func (s *FinancialCalculatorService) CalculateROI(initialInvestment, finalValue float64) float64 {
	if initialInvestment <= 0 {
		return 0
	}
	return ((finalValue - initialInvestment) / initialInvestment) * 100
}

// CalculateCAGR calculates Compound Annual Growth Rate
func (s *FinancialCalculatorService) CalculateCAGR(beginningValue, endingValue, years float64) float64 {
	if beginningValue <= 0 || years <= 0 {
		return 0
	}
	// CAGR = (Ending Value / Beginning Value)^(1/n) - 1
	return (math.Pow(endingValue/beginningValue, 1/years) - 1) * 100
}

// CalculateAffordableMortgage calculates maximum affordable mortgage payment
func (s *FinancialCalculatorService) CalculateAffordableMortgage(grossMonthlyIncome, otherDebts, maxDebtRatio float64) float64 {
	// Max total debt payment = income * maxDebtRatio
	maxTotalDebt := grossMonthlyIncome * (maxDebtRatio / 100)
	// Max mortgage = max total debt - other debts
	return maxTotalDebt - otherDebts
}

// CalculateCreditCardPayoff calculates time and cost to payoff credit card
func (s *FinancialCalculatorService) CalculateCreditCardPayoff(balance, annualRate, monthlyPayment float64) (months int, totalInterest float64) {
	rate := annualRate / 100 / 12
	
	remaining := balance
	months = 0
	totalInterest = 0
	
	for remaining > 0 {
		interest := remaining * rate
		principalPayment := monthlyPayment - interest
		
		if principalPayment <= 0 {
			// Payment too low - never pays off
			return -1, -1
		}
		
		remaining -= principalPayment
		totalInterest += interest
		months++
		
		if months > 600 { // 50 years cap
			break
		}
	}
	
	return months, totalInterest
}

// CalculateTaxBracket calculates effective tax rate based on progressive brackets
func (s *FinancialCalculatorService) CalculateTaxBracket(income float64, brackets []TaxBracket) (tax float64, effectiveRate float64) {
	tax = 0
	remainingIncome := income
	
	for _, bracket := range brackets {
		if remainingIncome <= 0 {
			break
		}
		
		taxableInBracket := math.Min(remainingIncome, bracket.Max-bracket.Min)
		tax += taxableInBracket * (bracket.Rate / 100)
		remainingIncome -= taxableInBracket
	}
	
	if income > 0 {
		effectiveRate = (tax / income) * 100
	}
	
	return tax, effectiveRate
}

// TaxBracket represents a tax bracket
type TaxBracket struct {
	Min   float64 // Lower bound
	Max   float64 // Upper bound (0 for highest bracket)
	Rate  float64 // Tax rate percentage
}

// AssetAllocationResult represents optimal asset allocation
type AssetAllocationResult struct {
	Stocks      float64 `json:"stocks"`
	Bonds       float64 `json:"bonds"`
	Cash        float64 `json:"cash"`
	RealEstate  float64 `json:"real_estate"`
	Alternative float64 `json:"alternative"`
}

// CalculateRuleOf110 calculates basic asset allocation based on age
// Rule: Stocks = 110 - Age, rest in bonds
func (s *FinancialCalculatorService) CalculateRuleOf110(age int, riskTolerance string) *AssetAllocationResult {
	// Base allocation
	stockPercent := 110 - age
	if stockPercent < 20 {
		stockPercent = 20 // Minimum 20% stocks
	}
	if stockPercent > 100 {
		stockPercent = 100
	}
	
	// Adjust based on risk tolerance
	switch riskTolerance {
	case "low":
		stockPercent -= 10
	case "high":
		stockPercent += 10
	}
	
	bondPercent := 100 - stockPercent
	
	return &AssetAllocationResult{
		Stocks: float64(stockPercent),
		Bonds:  float64(bondPercent),
		Cash:   5, // Always keep 5% cash
	}
}
