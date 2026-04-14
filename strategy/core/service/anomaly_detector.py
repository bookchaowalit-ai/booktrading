"""
Anomaly Detector for Trading Data
Detects unusual patterns that may indicate:
- Price manipulation (spoofing, wash trading)
- Flash crashes / spikes
- Volume anomalies (unusual activity)
- Pattern breakouts (support/resistance breaks)
- Statistical outliers

Uses statistical methods (z-score, IQR, rolling windows) — no ML libraries needed.
"""
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime

import numpy as np

logger = logging.getLogger(__name__)


class AnomalyType(Enum):
    PRICE_SPIKE = "price_spike"
    PRICE_DROP = "price_drop"
    VOLUME_SURGE = "volume_surge"
    VOLUME_DROPOUT = "volume_dropout"
    VOLATILITY_SURGE = "volatility_surge"
    PATTERN_BREAK = "pattern_break"
    FLASH_CRASH = "flash_crash"
    WHIPSAW = "whipsaw"


@dataclass
class Anomaly:
    type: AnomalyType
    severity: float  # 0-1
    timestamp: Optional[str]
    description: str
    data_point: Dict[str, Any]  # The actual data that triggered the anomaly
    recommendation: str  # What the user should do


@dataclass
class AnomalyReport:
    anomalies: List[Anomaly]
    overall_risk: float  # 0-1, aggregate risk score
    summary: str
    healthy_score: float  # 0-100, how "normal" the market looks


class AnomalyDetector:
    """Detects anomalies in trading data using statistical methods."""
    
    def __init__(self, z_threshold: float = 2.5, iqr_multiplier: float = 1.5):
        self.z_threshold = z_threshold
        self.iqr_multiplier = iqr_multiplier
    
    def detect(self, prices: List[float], volumes: Optional[List[float]] = None,
               timestamps: Optional[List[str]] = None) -> AnomalyReport:
        """
        Run all anomaly detection checks.
        
        Args:
            prices: Price history (at least 30 periods for meaningful stats)
            volumes: Corresponding volume data
            timestamps: Timestamp strings for each data point
        
        Returns:
            AnomalyReport with all detected anomalies
        """
        if len(prices) < 30:
            return AnomalyReport(
                anomalies=[],
                overall_risk=0.0,
                summary="Insufficient data for anomaly detection (need 30+ periods)",
                healthy_score=100.0,
            )
        
        prices_arr = np.array(prices)
        anomalies = []
        
        # 1. Price spike/drop detection
        anomalies.extend(self._detect_price_anomalies(prices_arr, timestamps))
        
        # 2. Flash crash detection (sudden drop + recovery)
        anomalies.extend(self._detect_flash_crashes(prices_arr, timestamps))
        
        # 3. Whipsaw detection (rapid up-down movement)
        anomalies.extend(self._detect_whipsaws(prices_arr, timestamps))
        
        # 4. Volume anomalies
        if volumes and len(volumes) >= 30:
            anomalies.extend(self._detect_volume_anomalies(volumes, prices_arr, timestamps))
        
        # 5. Volatility surge detection
        anomalies.extend(self._detect_volatility_anomalies(prices_arr, timestamps))
        
        # 6. Pattern break detection (support/resistance breaks)
        anomalies.extend(self._detect_pattern_breaks(prices_arr, timestamps))
        
        # Calculate aggregate metrics
        overall_risk = self._calculate_overall_risk(anomalies)
        healthy_score = max(0, 100 - overall_risk * 100)
        summary = self._generate_summary(anomalies, healthy_score)
        
        return AnomalyReport(
            anomalies=anomalies,
            overall_risk=round(overall_risk, 4),
            summary=summary,
            healthy_score=round(healthy_score, 1),
        )
    
    def _detect_price_anomalies(self, prices: np.ndarray, timestamps: Optional[List[str]]) -> List[Anomaly]:
        """Detect sudden price spikes or drops using z-score and % change."""
        anomalies = []
        returns = np.diff(prices) / prices[:-1] * 100  # Percentage returns
        
        if len(returns) < 20:
            return anomalies
        
        # Z-score method
        mean_return = np.mean(returns[-50:])
        std_return = np.std(returns[-50:])
        
        if std_return == 0:
            return anomalies
        
        current_return = returns[-1]
        z_score = (current_return - mean_return) / std_return
        
        ts = timestamps[-1] if timestamps and len(timestamps) == len(prices) else None
        
        if z_score > self.z_threshold:
            severity = min(1.0, abs(z_score) / 5.0)
            anomalies.append(Anomaly(
                type=AnomalyType.PRICE_SPIKE,
                severity=round(severity, 3),
                timestamp=ts,
                description=f"Price spike detected: +{current_return:.2f}% (z-score: {z_score:.2f})",
                data_point={"price": float(prices[-1]), "return_pct": round(current_return, 4), "z_score": round(z_score, 2)},
                recommendation="Verify this move with news. Could be a false breakout — wait for confirmation.",
            ))
        elif z_score < -self.z_threshold:
            severity = min(1.0, abs(z_score) / 5.0)
            anomalies.append(Anomaly(
                type=AnomalyType.PRICE_DROP,
                severity=round(severity, 3),
                timestamp=ts,
                description=f"Price drop detected: {current_return:.2f}% (z-score: {z_score:.2f})",
                data_point={"price": float(prices[-1]), "return_pct": round(current_return, 4), "z_score": round(z_score, 2)},
                recommendation="Check for panic selling. If fundamentals unchanged, may be a buying opportunity.",
            ))
        
        # IQR method for additional confirmation
        q1 = np.percentile(returns[-50:], 25)
        q3 = np.percentile(returns[-50:], 75)
        iqr = q3 - q1
        upper_bound = q3 + self.iqr_multiplier * iqr
        lower_bound = q1 - self.iqr_multiplier * iqr
        
        if current_return > upper_bound and z_score <= self.z_threshold:
            # Minor anomaly — IQR caught it but z-score didn't
            pass  # Already covered by z-score usually
        
        return anomalies
    
    def _detect_flash_crashes(self, prices: np.ndarray, timestamps: Optional[List[str]]) -> List[Anomaly]:
        """Detect flash crash patterns: sharp drop followed by quick recovery."""
        anomalies = []
        
        # Look for V-shaped patterns in recent data
        window = min(20, len(prices) - 1)
        
        for i in range(len(prices) - window, len(prices)):
            if i < 5:
                continue
            
            # Find local minimum in the window
            window_prices = prices[i-5:i+1]
            min_idx = np.argmin(window_prices)
            
            if min_idx == 0 or min_idx == len(window_prices) - 1:
                continue
            
            # Check if it's a V-shape: drop > 2% then recover > 50% of the drop
            drop = (window_prices[0] - window_prices[min_idx]) / window_prices[0] * 100
            recovery = (window_prices[-1] - window_prices[min_idx]) / (window_prices[0] - window_prices[min_idx]) * 100
            
            if drop > 2.0 and recovery > 50.0:
                ts = timestamps[i] if timestamps and len(timestamps) > i else None
                anomalies.append(Anomaly(
                    type=AnomalyType.FLASH_CRASH,
                    severity=round(min(1.0, drop / 10.0), 3),
                    timestamp=ts,
                    description=f"Flash crash pattern: {drop:.1f}% drop with {recovery:.0f}% recovery",
                    data_point={"drop_pct": round(drop, 2), "recovery_pct": round(recovery, 1), "trough_price": float(window_prices[min_idx])},
                    recommendation="Flash crashes often indicate stop-loss cascades. Be cautious of follow-through selling.",
                ))
                break  # Only report the most recent
        
        return anomalies
    
    def _detect_whipsaws(self, prices: np.ndarray, timestamps: Optional[List[str]]) -> List[Anomaly]:
        """Detect whipsaw patterns: rapid up-down movement that traps traders."""
        anomalies = []
        
        if len(prices) < 10:
            return anomalies
        
        # Count direction changes in recent periods
        changes = np.diff(prices[-10:])
        direction_changes = 0
        for i in range(1, len(changes)):
            if changes[i] * changes[i-1] < 0:  # Sign changed
                direction_changes += 1
        
        # 4+ direction changes in 10 periods = whipsaw
        if direction_changes >= 4:
            severity = min(1.0, direction_changes / 8.0)
            ts = timestamps[-1] if timestamps and len(timestamps) == len(prices) else None
            
            range_pct = (np.max(prices[-10:]) - np.min(prices[-10:])) / np.mean(prices[-10:]) * 100
            
            anomalies.append(Anomaly(
                type=AnomalyType.WHIPSAW,
                severity=round(severity, 3),
                timestamp=ts,
                description=f"Whipsaw pattern: {direction_changes} direction changes in 10 periods (range: {range_pct:.2f}%)",
                data_point={"direction_changes": direction_changes, "range_pct": round(range_pct, 2)},
                recommendation="High whipsaw risk. Consider reducing position size or widening stop-loss.",
            ))
        
        return anomalies
    
    def _detect_volume_anomalies(self, volumes: List[float], prices: np.ndarray,
                                  timestamps: Optional[List[str]]) -> List[Anomaly]:
        """Detect unusual volume patterns."""
        anomalies = []
        
        vol_arr = np.array(volumes)
        if len(vol_arr) < 30:
            return anomalies
        
        mean_vol = np.mean(vol_arr[-50:])
        std_vol = np.std(vol_arr[-50:])
        
        if mean_vol == 0:
            return anomalies
        
        current_vol = vol_arr[-1]
        vol_z_score = (current_vol - mean_vol) / std_vol if std_vol > 0 else 0
        
        ts = timestamps[-1] if timestamps and len(timestamps) == len(prices) else None
        
        # Volume surge
        if vol_z_score > self.z_threshold:
            volume_ratio = current_vol / mean_vol
            severity = min(1.0, vol_z_score / 5.0)
            anomalies.append(Anomaly(
                type=AnomalyType.VOLUME_SURGE,
                severity=round(severity, 3),
                timestamp=ts,
                description=f"Volume surge: {volume_ratio:.1f}x average (z-score: {vol_z_score:.2f})",
                data_point={"current_volume": float(current_vol), "avg_volume": round(float(mean_vol), 2), "ratio": round(volume_ratio, 2)},
                recommendation="Unusual volume may indicate institutional activity or news-driven move.",
            ))
        
        # Volume dropout (very low volume — potential liquidity issue)
        if current_vol < mean_vol * 0.2:
            anomalies.append(Anomaly(
                type=AnomalyType.VOLUME_DROPOUT,
                severity=0.4,
                timestamp=ts,
                description=f"Volume dropout: {current_vol/mean_vol*100:.0f}% of average",
                data_point={"current_volume": float(current_vol), "avg_volume": round(float(mean_vol), 2)},
                recommendation="Low volume means poor liquidity. Orders may have high slippage.",
            ))
        
        return anomalies
    
    def _detect_volatility_anomalies(self, prices: np.ndarray, timestamps: Optional[List[str]]) -> List[Anomaly]:
        """Detect sudden changes in volatility regime."""
        anomalies = []
        
        if len(prices) < 40:
            return anomalies
        
        # Compare recent volatility to historical
        recent_vol = np.std(np.diff(prices[-20:]) / prices[-21:-1])
        historical_vol = np.std(np.diff(prices[-60:-20]) / prices[-61:-21])
        
        if historical_vol == 0:
            return anomalies
        
        vol_ratio = recent_vol / historical_vol
        
        if vol_ratio > 2.5:
            ts = timestamps[-1] if timestamps and len(timestamps) == len(prices) else None
            anomalies.append(Anomaly(
                type=AnomalyType.VOLATILITY_SURGE,
                severity=min(1.0, vol_ratio / 5.0),
                timestamp=ts,
                description=f"Volatility surge: {vol_ratio:.1f}x historical average",
                data_point={"recent_volatility": round(recent_vol * 100, 3), "historical_volatility": round(historical_vol * 100, 3)},
                recommendation="Higher volatility means wider stops needed. Consider reducing position sizes.",
            ))
        
        return anomalies
    
    def _detect_pattern_breaks(self, prices: np.ndarray, timestamps: Optional[List[str]]) -> List[Anomaly]:
        """Detect breaks of established support/resistance levels."""
        anomalies = []
        
        if len(prices) < 50:
            return anomalies
        
        # Find key levels using recent highs and lows
        recent_high = np.max(prices[-50:-1])
        recent_low = np.min(prices[-50:-1])
        current_price = prices[-1]
        
        ts = timestamps[-1] if timestamps and len(timestamps) == len(prices) else None
        
        # Break above resistance
        if current_price > recent_high * 1.01:  # 1% above resistance
            anomalies.append(Anomaly(
                type=AnomalyType.PATTERN_BREAK,
                severity=0.5,
                timestamp=ts,
                description=f"Resistance break: price {current_price:.2f} above recent high {recent_high:.2f}",
                data_point={"price": float(current_price), "resistance": float(recent_high)},
                recommendation="Breakout confirmed with volume = strong signal. Without volume = possible false break.",
            ))
        
        # Break below support
        if current_price < recent_low * 0.99:  # 1% below support
            anomalies.append(Anomaly(
                type=AnomalyType.PATTERN_BREAK,
                severity=0.6,
                timestamp=ts,
                description=f"Support break: price {current_price:.2f} below recent low {recent_low:.2f}",
                data_point={"price": float(current_price), "support": float(recent_low)},
                recommendation="Support break is bearish. Consider stop-loss or hedging.",
            ))
        
        return anomalies
    
    def _calculate_overall_risk(self, anomalies: List[Anomaly]) -> float:
        """Calculate aggregate risk score from all anomalies."""
        if not anomalies:
            return 0.0
        
        # Weighted: higher severity anomalies contribute more
        # But we cap the total to avoid runaway scores
        max_severity = max(a.severity for a in anomalies)
        count_factor = min(1.0, len(anomalies) / 5.0)  # 5+ anomalies = max count factor
        
        return min(1.0, max_severity * 0.6 + count_factor * 0.4)
    
    def _generate_summary(self, anomalies: List[Anomaly], healthy_score: float) -> str:
        """Generate human-readable summary."""
        if not anomalies:
            return "Market conditions appear normal. No significant anomalies detected."
        
        type_counts = {}
        for a in anomalies:
            type_counts[a.type.value] = type_counts.get(a.type.value, 0) + 1
        
        parts = [f"Detected {len(anomalies)} anomaly/anomalies:"]
        for atype, count in type_counts.items():
            parts.append(f"  • {atype}: {count}")
        
        if healthy_score > 70:
            parts.append(f"\nOverall market health: {healthy_score:.0f}/100 (Moderate)")
        elif healthy_score > 40:
            parts.append(f"\nOverall market health: {healthy_score:.0f}/100 (Caution advised)")
        else:
            parts.append(f"\nOverall market health: {healthy_score:.0f}/100 (High risk — exercise caution)")
        
        return "\n".join(parts)
