# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
API Rate Limiting Middleware
Protects against API abuse - completely free and open source
"""

import time
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from collections import defaultdict
from typing import Dict
import asyncio
import logging

logger = logging.getLogger(__name__)


class RateLimiter(BaseHTTPMiddleware):
    """
    Rate limiting middleware to prevent API abuse
    Free and open source - no external services required
    """
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_counts: Dict[str, list] = defaultdict(list)
        self.cleanup_interval = 60  # seconds
        
        # Start cleanup task
        asyncio.create_task(self.cleanup_old_requests())
        
        logger.info(f"Rate limiter initialized: {requests_per_minute} requests/minute")
    
    async def dispatch(self, request: Request, call_next):
        """Process each request with rate limiting"""
        
        # Get client identifier (IP address)
        client_ip = request.client.host
        
        # Get current timestamp
        now = time.time()
        
        # Clean old requests for this client
        self.request_counts[client_ip] = [
            timestamp for timestamp in self.request_counts[client_ip]
            if now - timestamp < 60
        ]
        
        # Check rate limit
        if len(self.request_counts[client_ip]) >= self.requests_per_minute:
            logger.warning(f"Rate limit exceeded for {client_ip}")
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please try again later.",
                headers={"Retry-After": "60"}
            )
        
        # Add current request
        self.request_counts[client_ip].append(now)
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(
            self.requests_per_minute - len(self.request_counts[client_ip])
        )
        
        return response
    
    async def cleanup_old_requests(self):
        """Periodically clean up old request records"""
        while True:
            await asyncio.sleep(self.cleanup_interval)
            
            now = time.time()
            
            # Clean up old records
            clients_to_remove = []
            for client_ip, timestamps in self.request_counts.items():
                # Remove timestamps older than 1 minute
                self.request_counts[client_ip] = [
                    t for t in timestamps if now - t < 60
                ]
                
                # If no recent requests, remove client entry
                if not self.request_counts[client_ip]:
                    clients_to_remove.append(client_ip)
            
            for client_ip in clients_to_remove:
                del self.request_counts[client_ip]
