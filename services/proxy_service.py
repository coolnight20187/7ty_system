"""
Proxy Pool Service for 7TY System
Manages rotating proxies for API requests
"""

import logging
import random
import re
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from config import settings

logger = logging.getLogger(__name__)


def parse_proxy_string(proxy_str: str) -> Optional[str]:
    """
    Parse various proxy formats and return standard http://user:pass@ip:port format
    
    Supported formats:
    - http://user:pass@ip:port (standard)
    - https://user:pass@ip:port
    - socks5://user:pass@ip:port
    - ip:port:user:pass (custom format)
    - ip:port (no auth)
    """
    proxy_str = proxy_str.strip()
    if not proxy_str:
        return None
    
    # Already in standard format
    if proxy_str.startswith(("http://", "https://", "socks5://")):
        return proxy_str
    
    # Try parsing ip:port:user:pass format
    parts = proxy_str.split(":")
    if len(parts) == 4:
        ip, port, user, password = parts
        return f"http://{user}:{password}@{ip}:{port}"
    elif len(parts) == 2:
        # ip:port format (no auth)
        ip, port = parts
        return f"http://{ip}:{port}"
    elif len(parts) == 3:
        # Could be ip:port:user (missing password) - invalid
        return None
    
    return None


class ProxyPool:
    """Manages a pool of proxies with rotation and health tracking"""
    
    def __init__(self):
        self.proxies: List[Dict] = []
        self.current_index: int = 0
        self.failed_proxies: Dict[str, datetime] = {}  # proxy -> last_fail_time
        self.cooldown_minutes: int = 5  # Time before retrying failed proxy
        self.enabled: bool = settings.PROXY_ENABLED  # Track enabled state
        self._load_proxies_from_config()
        self._load_proxies_from_db()
    
    def _load_proxies_from_config(self):
        """Load proxies from config file"""
        proxy_list = settings.PROXY_LIST.strip()
        if not proxy_list:
            return
        
        for proxy_str in proxy_list.split(","):
            proxy_url = parse_proxy_string(proxy_str)
            if proxy_url:
                self._add_proxy_internal(proxy_url)
        
        if self.proxies:
            logger.info(f"Loaded {len(self.proxies)} proxies from config")
    
    def _load_proxies_from_db(self):
        """Load proxies from database"""
        try:
            from database import SessionLocal
            from models import SystemConfig
            
            db = SessionLocal()
            try:
                config = db.query(SystemConfig).filter(SystemConfig.key == "proxy_list").first()
                if config and config.value:
                    count = 0
                    for proxy_str in config.value.split("\n"):
                        proxy_url = parse_proxy_string(proxy_str)
                        if proxy_url and not any(p["url"] == proxy_url for p in self.proxies):
                            self._add_proxy_internal(proxy_url)
                            count += 1
                    if count > 0:
                        logger.info(f"Loaded {count} proxies from database")
                
                # Load enabled state
                enabled_config = db.query(SystemConfig).filter(SystemConfig.key == "proxy_enabled").first()
                if enabled_config:
                    self.enabled = enabled_config.value.lower() == "true"
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Failed to load proxies from database: {e}")
    
    def _save_proxies_to_db(self):
        """Save proxies to database for persistence"""
        try:
            from database import SessionLocal
            from models import SystemConfig
            
            db = SessionLocal()
            try:
                # Save proxy list
                proxy_list_str = "\n".join([p["url"] for p in self.proxies])
                config = db.query(SystemConfig).filter(SystemConfig.key == "proxy_list").first()
                if config:
                    config.value = proxy_list_str
                    config.updated_at = datetime.now()
                else:
                    config = SystemConfig(
                        key="proxy_list",
                        value=proxy_list_str,
                        value_type="string",
                        category="proxy",
                        description="Proxy Pool List"
                    )
                    db.add(config)
                
                db.commit()
                logger.info(f"Saved {len(self.proxies)} proxies to database")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to save proxies to database: {e}")
    
    def _save_enabled_state_to_db(self):
        """Save enabled state to database"""
        try:
            from database import SessionLocal
            from models import SystemConfig
            
            db = SessionLocal()
            try:
                config = db.query(SystemConfig).filter(SystemConfig.key == "proxy_enabled").first()
                if config:
                    config.value = "true" if self.enabled else "false"
                    config.updated_at = datetime.now()
                else:
                    config = SystemConfig(
                        key="proxy_enabled",
                        value="true" if self.enabled else "false",
                        value_type="string",
                        category="proxy",
                        description="Proxy Pool Enabled State"
                    )
                    db.add(config)
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to save proxy enabled state: {e}")
    
    def _add_proxy_internal(self, proxy_url: str) -> bool:
        """Internal method to add proxy without saving to db"""
        if not proxy_url:
            return False
        
        # Check if already exists
        for p in self.proxies:
            if p["url"] == proxy_url:
                return False
        
        self.proxies.append({
            "url": proxy_url,
            "success_count": 0,
            "fail_count": 0,
            "last_used": None
        })
        return True
    
    def add_proxy(self, proxy_str: str) -> bool:
        """Add a new proxy to the pool (with auto-format detection)"""
        proxy_url = parse_proxy_string(proxy_str)
        if not proxy_url:
            return False
        
        if self._add_proxy_internal(proxy_url):
            logger.info(f"Added proxy: {proxy_url[:40]}...")
            self._save_proxies_to_db()
            return True
        return False
    
    def add_proxies_batch(self, proxy_strings: List[str]) -> int:
        """Add multiple proxies at once"""
        added = 0
        for proxy_str in proxy_strings:
            proxy_url = parse_proxy_string(proxy_str)
            if proxy_url and self._add_proxy_internal(proxy_url):
                added += 1
        
        if added > 0:
            self._save_proxies_to_db()
            logger.info(f"Added {added} proxies in batch")
        return added
    
    def remove_proxy(self, proxy_url: str) -> bool:
        """Remove a proxy from the pool"""
        for i, p in enumerate(self.proxies):
            if p["url"] == proxy_url:
                del self.proxies[i]
                logger.info(f"Removed proxy: {proxy_url[:30]}...")
                self._save_proxies_to_db()
                return True
        return False
    
    def set_enabled(self, enabled: bool):
        """Set enabled state and save to database"""
        self.enabled = enabled
        self._save_enabled_state_to_db()
        logger.info(f"Proxy pool {'enabled' if enabled else 'disabled'}")
    
    def clear_all(self):
        """Clear all proxies"""
        self.proxies = []
        self.failed_proxies = {}
        self.current_index = 0
        self._save_proxies_to_db()
        logger.info("Cleared all proxies from pool")
    
    def get_next_proxy(self) -> Optional[str]:
        """Get the next available proxy using round-robin"""
        if not self.proxies or not self.enabled:
            return None
        
        now = datetime.now()
        attempts = 0
        max_attempts = len(self.proxies)
        
        while attempts < max_attempts:
            proxy = self.proxies[self.current_index]
            proxy_url = proxy["url"]
            
            # Check if proxy is in cooldown
            if proxy_url in self.failed_proxies:
                cooldown_until = self.failed_proxies[proxy_url] + timedelta(minutes=self.cooldown_minutes)
                if now < cooldown_until:
                    # Skip this proxy, still in cooldown
                    self.current_index = (self.current_index + 1) % len(self.proxies)
                    attempts += 1
                    continue
                else:
                    # Cooldown expired, remove from failed list
                    del self.failed_proxies[proxy_url]
            
            # Update index for next call
            self.current_index = (self.current_index + 1) % len(self.proxies)
            
            # Update last used time
            proxy["last_used"] = now
            
            logger.debug(f"Using proxy: {proxy_url[:30]}...")
            return proxy_url
        
        # All proxies in cooldown
        logger.warning("All proxies are in cooldown, returning None")
        return None
    
    def get_random_proxy(self) -> Optional[str]:
        """Get a random available proxy"""
        if not self.proxies or not settings.PROXY_ENABLED:
            return None
        
        now = datetime.now()
        available = []
        
        for proxy in self.proxies:
            proxy_url = proxy["url"]
            if proxy_url in self.failed_proxies:
                cooldown_until = self.failed_proxies[proxy_url] + timedelta(minutes=self.cooldown_minutes)
                if now >= cooldown_until:
                    del self.failed_proxies[proxy_url]
                    available.append(proxy)
            else:
                available.append(proxy)
        
        if not available:
            logger.warning("No available proxies")
            return None
        
        selected = random.choice(available)
        selected["last_used"] = now
        return selected["url"]
    
    def mark_success(self, proxy_url: str):
        """Mark a proxy as successful"""
        for proxy in self.proxies:
            if proxy["url"] == proxy_url:
                proxy["success_count"] += 1
                # Remove from failed list if was there
                if proxy_url in self.failed_proxies:
                    del self.failed_proxies[proxy_url]
                break
    
    def mark_failed(self, proxy_url: str):
        """Mark a proxy as failed, put it in cooldown"""
        for proxy in self.proxies:
            if proxy["url"] == proxy_url:
                proxy["fail_count"] += 1
                self.failed_proxies[proxy_url] = datetime.now()
                logger.warning(f"Proxy marked as failed: {proxy_url[:30]}... (cooldown {self.cooldown_minutes}m)")
                break
    
    def get_stats(self) -> Dict:
        """Get proxy pool statistics"""
        now = datetime.now()
        available_count = 0
        
        for proxy in self.proxies:
            if proxy["url"] not in self.failed_proxies:
                available_count += 1
            else:
                cooldown_until = self.failed_proxies[proxy["url"]] + timedelta(minutes=self.cooldown_minutes)
                if now >= cooldown_until:
                    available_count += 1
        
        return {
            "total": len(self.proxies),
            "available": available_count,
            "in_cooldown": len(self.failed_proxies),
            "enabled": self.enabled,
            "proxies": [
                {
                    "url": p["url"][:30] + "..." if len(p["url"]) > 30 else p["url"],
                    "success": p["success_count"],
                    "fail": p["fail_count"],
                    "status": "cooldown" if p["url"] in self.failed_proxies else "available"
                }
                for p in self.proxies
            ]
        }
    
    def list_proxies(self) -> List[str]:
        """Get list of all proxy URLs"""
        return [p["url"] for p in self.proxies]
    
    def get_first_proxy(self) -> Optional[str]:
        """Get first proxy for testing (ignores PROXY_ENABLED setting)"""
        if not self.proxies:
            return None
        return self.proxies[0]["url"]


# Singleton instance
proxy_pool = ProxyPool()


def get_proxy_for_request() -> Optional[str]:
    """Helper function to get a proxy for making requests"""
    return proxy_pool.get_next_proxy()


def get_proxy_for_test() -> Optional[str]:
    """Helper function to get a proxy for testing (ignores enabled setting)"""
    return proxy_pool.get_first_proxy()


def report_proxy_result(proxy_url: str, success: bool):
    """Report the result of using a proxy"""
    if success:
        proxy_pool.mark_success(proxy_url)
    else:
        proxy_pool.mark_failed(proxy_url)
