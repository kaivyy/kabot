from typing import Dict, Any
from kabot.auth.handlers.base import AuthHandler
from kabot.auth.utils import run_oauth_flow

class QwenOAuthHandler(AuthHandler):
    """Handler for Qwen Portal OAuth login."""

    def authenticate(self) -> Dict[str, Any]:
        # Qwen portal auth URL
        auth_url = "https://dashscope.aliyun.com/oauth/authorize"
        
        # Consistent behavior: Port detection, VPS aware, Smart URL parsing
        token = run_oauth_flow(auth_url)
        
        if not token:
            return {}

        return {
            "providers": {
                "dashscope": {
                    "oauth_token": token
                }
            }
        }
