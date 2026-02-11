import json
import sys
import argparse
from pathlib import Path

CONFIG_PATH = Path.home() / ".kabot" / "config.json"

def load_config():
    if not CONFIG_PATH.exists():
        return {}
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_config(config):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

def get_value(key):
    data = load_config()
    for k in key.split("."):
        if isinstance(data, dict):
            data = data.get(k)
        else:
            return None
    return data

def set_value(key, value):
    config = load_config()
    keys = key.split(".")
    current = config
    for k in keys[:-1]:
        if k not in current or not isinstance(current[k], dict):
            current[k] = {}
            current = current[k]
        else:
            current = current[k]
    
    try:
        val = json.loads(value)
    except:
        val = value
    
    current[keys[-1]] = val
    save_config(config)
    print(f"Updated {key}")

def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    
    p_get = subparsers.add_parser("get")
    p_get.add_argument("key")
    
    p_set = subparsers.add_parser("set")
    p_set.add_argument("key")
    p_set.add_argument("value")
    
    subparsers.add_parser("list")
    
    args = parser.parse_args()
    
    if args.command == "get":
        val = get_value(args.key)
        print(json.dumps(val, indent=2) if val is not None else "null")
    elif args.command == "set":
        set_value(args.key, args.value)
    elif args.command == "list":
        print(json.dumps(load_config(), indent=2))

if __name__ == "__main__":
    main()
