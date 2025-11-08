import asyncio
import statistics
import logging
from typing import Tuple, Dict
from collections import deque, defaultdict
from icmplib import async_ping


class PingService:
    def __init__(self, anomaly_threshold: float = 30.0, anomaly_count: int = 5):
        self.anomaly_threshold = anomaly_threshold
        self.anomaly_count = anomaly_count
        self.logger = logging.getLogger("AuroraMonitor.Ping")
        
        # Store ping history for anomaly detection (last 100 pings per target)
        self.ping_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.anomaly_counters: Dict[str, int] = defaultdict(int)
    
    async def icmp_ping(self, host: str, timeout: int = 2) -> Tuple[bool, float]:
        """
        Perform ICMP ping to host using icmplib (pure Python implementation)
        Returns: (success, latency_ms)
        """
        try:
            # Use icmplib's async_ping which doesn't require system ping command
            result = await async_ping(host, count=1, timeout=timeout, privileged=False)
            
            if result.is_alive:
                # result.avg_rtt is in milliseconds
                return True, result.avg_rtt
            else:
                return False, 0.0
                
        except PermissionError:
            # If unprivileged mode fails, try privileged mode
            try:
                result = await async_ping(host, count=1, timeout=timeout, privileged=True)
                if result.is_alive:
                    return True, result.avg_rtt
                else:
                    return False, 0.0
            except Exception as e:
                self.logger.error(f"ICMP ping error for {host} (privileged mode): {type(e).__name__}: {e}")
                return False, 0.0
                
        except Exception as e:
            self.logger.error(f"ICMP ping error for {host}: {type(e).__name__}: {e}")
            return False, 0.0
    
    async def ping_with_retry(
        self, 
        target: str, 
        retry_attempts: int = 3
    ) -> Tuple[bool, float, int]:
        """
        Ping target with retry logic using ICMP
        Returns: (overall_success, average_latency, failed_attempts)
        """
        failed_attempts = 0
        total_latency = 0
        successful_pings = 0
        
        for attempt in range(retry_attempts):
            success, latency = await self.icmp_ping(target)
            
            if success:
                total_latency += latency
                successful_pings += 1
            else:
                failed_attempts += 1
            
            # Small delay between retries
            if attempt < retry_attempts - 1:
                await asyncio.sleep(0.5)
        
        overall_success = successful_pings > 0
        avg_latency = total_latency / successful_pings if successful_pings > 0 else 0
        
        return overall_success, avg_latency, failed_attempts
    
    def add_to_history(self, target: str, latency: float):
        """Add latency measurement to target's history"""
        self.ping_history[target].append(latency)
    
    def check_anomaly(self, target: str, current_latency: float) -> Tuple[bool, float]:
        """
        Check if current latency is anomalous compared to historical average
        Returns: (is_anomaly, average_latency)
        """
        history = self.ping_history[target]
        
        # Need at least 10 samples for meaningful average
        if len(history) < 10:
            return False, 0.0
        
        avg_latency = statistics.mean(history)
        threshold = avg_latency * (1 + self.anomaly_threshold / 100)
        
        if current_latency > threshold:
            self.anomaly_counters[target] += 1
            
            if self.anomaly_counters[target] >= self.anomaly_count:
                # Reset counter and return True
                consecutive = self.anomaly_counters[target]
                self.anomaly_counters[target] = 0
                return True, avg_latency
        else:
            # Reset counter if latency is normal
            self.anomaly_counters[target] = 0
        
        return False, avg_latency
    
    def get_average_latency(self, target: str) -> float:
        """Get average latency for a target"""
        history = self.ping_history[target]
        if len(history) == 0:
            return 0.0
        return statistics.mean(history)
    
    def reset_anomaly_counter(self, target: str):
        """Reset anomaly counter for a target"""
        self.anomaly_counters[target] = 0
