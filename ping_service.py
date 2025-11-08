import asyncio
import time
import platform
import subprocess
import socket
import statistics
import logging
from typing import Tuple, Dict
from collections import deque, defaultdict


class PingService:
    def __init__(self, anomaly_threshold: float = 30.0, anomaly_count: int = 5):
        self.anomaly_threshold = anomaly_threshold
        self.anomaly_count = anomaly_count
        self.logger = logging.getLogger("AuroraMonitor.Ping")
        
        # Store ping history for anomaly detection (last 100 pings per target)
        self.ping_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.anomaly_counters: Dict[str, int] = defaultdict(int)
    
    def icmp_ping(self, host: str, timeout: int = 2) -> Tuple[bool, float]:
        """
        Perform ICMP ping to host
        Returns: (success, latency_ms)
        """
        try:
            # Determine ping command based on OS
            param = '-n' if platform.system().lower() == 'windows' else '-c'
            timeout_param = '-w' if platform.system().lower() == 'windows' else '-W'
            timeout_value = str(timeout * 1000 if platform.system().lower() == 'windows' else timeout)
            
            command = ['ping', param, '1', timeout_param, timeout_value, host]
            
            start_time = time.time()
            result = subprocess.run(
                command, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                timeout=timeout + 1
            )
            end_time = time.time()
            
            if result.returncode == 0:
                latency = (end_time - start_time) * 1000
                return True, latency
            else:
                return False, 0.0
        except Exception as e:
            self.logger.debug(f"ICMP ping error for {host}: {e}")
            return False, 0.0
    
    def dns_ping(self, host: str, timeout: int = 2) -> Tuple[bool, float]:
        """
        Perform DNS query (UDP) to host
        Returns: (success, latency_ms)
        """
        try:
            start_time = time.time()
            socket.setdefaulttimeout(timeout)
            socket.gethostbyname(host)
            end_time = time.time()
            
            latency = (end_time - start_time) * 1000
            return True, latency
        except Exception as e:
            self.logger.debug(f"DNS ping error for {host}: {e}")
            return False, 0.0
    
    async def ping_with_retry(
        self, 
        target: str, 
        is_dns: bool = False, 
        retry_attempts: int = 3
    ) -> Tuple[bool, float, int]:
        """
        Ping target with retry logic
        Returns: (overall_success, average_latency, failed_attempts)
        """
        failed_attempts = 0
        total_latency = 0
        successful_pings = 0
        
        for attempt in range(retry_attempts):
            if is_dns:
                success, latency = self.dns_ping(target)
            else:
                success, latency = self.icmp_ping(target)
            
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
