#!/usr/bin/env python3
"""
Autonomous Task Loop for Kabot.
Implements a simple ReAct loop: Thought -> Action -> Observation -> Correction.
"""
import argparse
import json
import os
import subprocess
import sys

# Try to import litellm
try:
    from litellm import completion
except ImportError:
    print("Error: 'litellm' package is required.")
    sys.exit(1)

def run_shell(command):
    """Run shell command and return stdout/stderr."""
    print(f"💻 Executing: {command}")
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return -1, "", str(e)

def get_next_action(history, goal, model):
    """Ask LLM what to do next based on history."""
    prompt = f"""
    GOAL: {goal}

    HISTORY:
    {json.dumps(history, indent=2)}

    You are an autonomous agent. Your job is to achieve the GOAL.
    Analyze the HISTORY. If the last command failed, analyze why and propose a fix.

    Return ONLY a JSON object with this format:
    {{
        "thought": "Reasoning about what to do next",
        "command": "The shell command to execute",
        "status": "CONTINUE" or "SUCCESS" or "GIVE_UP"
    }}
    """

    response = completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )

    try:
        return json.loads(response.choices[0].message.content)
    except Exception:
        # Fallback if valid JSON not returned
        return {"thought": "Error parsing LLM response", "status": "GIVE_UP"}

def run_loop(goal, max_retries=3, model="gpt-4o"):
    print(f"🔄 Starting Autonomous Loop for: '{goal}'")
    history = []

    for i in range(max_retries):
        print(f"\n--- Attempt {i+1}/{max_retries} ---")

        # 1. Plan
        plan = get_next_action(history, goal, model)
        print(f"🤔 Thought: {plan.get('thought')}")

        if plan.get("status") == "SUCCESS":
            print("✅ Task marked as SUCCESS by agent.")
            return True
        elif plan.get("status") == "GIVE_UP":
            print("❌ Agent gave up.")
            return False

        command = plan.get("command")
        if not command:
            print("❌ No command generated.")
            break

        # 2. Execute
        code, out, err = run_shell(command)

        # 3. Observe
        output = f"STDOUT: {out}\nSTDERR: {err}\nEXIT_CODE: {code}"
        print(f"👀 Result: Exit Code {code}")
        if code != 0:
            print("⚠️ Error detected in output.")

        history.append({
            "step": i+1,
            "command": command,
            "output": output
        })

        # If simple command succeeds and agent wasn't explicit about continuing,
        # we might want to check if goal is met. But for now, we rely on agent "SUCCESS" signal.

    print("\n❌ Max retries reached without SUCCESS signal.")
    return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Autonomous Task Loop")
    parser.add_argument("--goal", required=True, help="Task goal")
    parser.add_argument("--max-retries", type=int, default=3, help="Max retries")
    parser.add_argument("--model", default="gpt-4o", help="Model to use")

    args = parser.parse_args()

    # Auto-detect API Key for model default
    if not os.environ.get("OPENAI_API_KEY") and args.model == "gpt-4o":
        # Fallback to whatever key is available
        if os.environ.get("ANTHROPIC_API_KEY"):
            args.model = "claude-3-5-sonnet-20240620"

    run_loop(args.goal, args.max_retries, args.model)
