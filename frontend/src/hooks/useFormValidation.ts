/**
 * Form Validation Hook
 * Provides validation functions for trading forms
 */
import { useCallback } from 'react';
import { useTranslation } from '@/i18n/translations';

export interface ValidationError {
  field: string;
  message: string;
}

export interface ValidationResult {
  isValid: boolean;
  errors: ValidationError[];
}

export interface GridConfigValidation {
  symbol: string;
  lowerPrice: number;
  upperPrice: number;
  gridLevels: number;
  investmentAmount: number;
}

export function useFormValidation() {
  const { t } = useTranslation();

  const required = useCallback(
    (value: string | number | undefined | null, fieldName: string): ValidationError | null => {
      if (value === undefined || value === null || value === '') {
        return { field: fieldName, message: t('validation.required') };
      }
      return null;
    },
    [t]
  );

  const minNumber = useCallback(
    (value: number, min: number, fieldName: string): ValidationError | null => {
      if (value < min) {
        return { field: fieldName, message: t('validation.min-value', { min }) };
      }
      return null;
    },
    [t]
  );

  const maxNumber = useCallback(
    (value: number, max: number, fieldName: string): ValidationError | null => {
      if (value > max) {
        return { field: fieldName, message: t('validation.max-value', { max }) };
      }
      return null;
    },
    [t]
  );

  const positiveNumber = useCallback(
    (value: number, fieldName: string): ValidationError | null => {
      if (value <= 0) {
        return { field: fieldName, message: t('validation.negative-not-allowed') };
      }
      return null;
    },
    [t]
  );

  const priceRange = useCallback(
    (lowerPrice: number, upperPrice: number): ValidationError | null => {
      if (upperPrice <= lowerPrice) {
        return { field: 'upperPrice', message: t('validation.price-range') };
      }
      return null;
    },
    [t]
  );

  const gridLevelsRange = useCallback(
    (levels: number): ValidationError | null => {
      if (levels < 2 || levels > 50) {
        return { field: 'gridLevels', message: t('validation.grid-levels') };
      }
      return null;
    },
    [t]
  );

  const sufficientBalance = useCallback(
    (investmentAmount: number, availableBalance: number, currency: string): ValidationError | null => {
      if (investmentAmount > availableBalance) {
        return {
          field: 'investmentAmount',
          message: t('validation.insufficient-balance', {
            balance: availableBalance.toLocaleString(undefined, { maximumFractionDigits: 2 }),
            currency,
          }),
        };
      }
      return null;
    },
    [t]
  );

  // Validate complete grid configuration
  const validateGridConfig = useCallback(
    (config: GridConfigValidation, availableBalance?: number, currency?: string): ValidationResult => {
      const errors: ValidationError[] = [];

      // Required fields
      const symbolError = required(config.symbol, 'symbol');
      if (symbolError) errors.push(symbolError);

      // Positive numbers
      const lowerPriceError = positiveNumber(config.lowerPrice, 'lowerPrice');
      if (lowerPriceError) errors.push(lowerPriceError);

      const upperPriceError = positiveNumber(config.upperPrice, 'upperPrice');
      if (upperPriceError) errors.push(upperPriceError);

      const investmentError = positiveNumber(config.investmentAmount, 'investmentAmount');
      if (investmentError) errors.push(investmentError);

      // Price range validation
      if (!lowerPriceError && !upperPriceError) {
        const rangeError = priceRange(config.lowerPrice, config.upperPrice);
        if (rangeError) errors.push(rangeError);
      }

      // Grid levels validation
      const levelsError = gridLevelsRange(config.gridLevels);
      if (levelsError) errors.push(levelsError);

      // Balance check
      if (availableBalance !== undefined && currency) {
        const balanceError = sufficientBalance(config.investmentAmount, availableBalance, currency);
        if (balanceError) errors.push(balanceError);
      }

      return { isValid: errors.length === 0, errors };
    },
    [required, positiveNumber, priceRange, gridLevelsRange, sufficientBalance]
  );

  return {
    required,
    minNumber,
    maxNumber,
    positiveNumber,
    priceRange,
    gridLevelsRange,
    sufficientBalance,
    validateGridConfig,
  };
}

// Field-specific validation hooks
export function useFieldValidation(fieldName: string) {
  const { t } = useTranslation();

  const validateRequired = useCallback(
    (value: string | number | undefined | null): string | null => {
      if (!value && value !== 0) {
        return t('validation.required');
      }
      return null;
    },
    [t]
  );

  const validateMin = useCallback(
    (value: number, min: number): string | null => {
      if (value < min) {
        return t('validation.min-value', { min });
      }
      return null;
    },
    [t]
  );

  const validateMax = useCallback(
    (value: number, max: number): string | null => {
      if (value > max) {
        return t('validation.max-value', { max });
      }
      return null;
    },
    [t]
  );

  return {
    validateRequired,
    validateMin,
    validateMax,
  };
}

export default useFormValidation;
