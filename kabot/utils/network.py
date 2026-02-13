import socket

def probe_gateway(host="127.0.0.1", port=18790, timeout=0.5) -> bool:
    """Fast socket-based check for gateway reachability."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False
