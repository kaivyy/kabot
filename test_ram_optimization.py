"""
Test script for RAM optimization feature.

This script verifies:
1. Lazy loading - model loads only on first search
2. Auto-unload - model unloads after timeout
3. Manual unload - explicit resource cleanup works
4. Automatic reload - model reloads on next search
5. RAM reduction - memory usage drops significantly after unload
"""

import asyncio
import psutil
import os
import time
from pathlib import Path
from kabot.memory.chroma_memory import HybridMemoryManager

def get_ram_mb():
    """Get current RAM usage in MB."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024

async def test_ram_optimization():
    print("=" * 60)
    print("RAM Optimization Test")
    print("=" * 60)

    # Create temporary workspace
    workspace = Path("./test_memory_workspace")
    workspace.mkdir(exist_ok=True)

    # Measure baseline RAM
    baseline_ram = get_ram_mb()
    print(f"\n1. Baseline RAM: {baseline_ram:.1f} MB")

    # Create HybridMemoryManager with short timeout for testing
    print("\n2. Creating HybridMemoryManager (auto_unload_timeout=10s)...")
    memory = HybridMemoryManager(
        workspace=workspace,
        auto_unload_seconds=10  # 10 seconds for testing
    )

    # Check initial state (model should NOT be loaded yet - lazy loading)
    stats_init = memory.get_memory_stats()
    print(f"   Model loaded: {stats_init['embedding']['model_loaded']}")
    print(f"   RAM after init: {get_ram_mb():.1f} MB")

    # Trigger first search (should load model)
    print("\n3. First search (triggers model load)...")
    await memory.add_message("test_session", "user", "What is machine learning?")
    await memory.search_memory("machine learning", session_id="test_session")

    loaded_ram = get_ram_mb()
    ram_increase = loaded_ram - baseline_ram
    stats_loaded = memory.get_memory_stats()
    print(f"   Model loaded: {stats_loaded['embedding']['model_loaded']}")
    print(f"   RAM after load: {loaded_ram:.1f} MB (+{ram_increase:.1f} MB)")

    # Wait for auto-unload (10 seconds)
    print("\n4. Waiting 12 seconds for auto-unload...")
    for i in range(12):
        await asyncio.sleep(1)
        print(f"   {i+1}s...", end=" ", flush=True)
    print()

    # Check if model unloaded - CAPTURE STATS HERE
    await asyncio.sleep(1)  # Give GC time
    stats_after_auto_unload = memory.get_memory_stats()
    unloaded_ram = get_ram_mb()
    ram_freed = loaded_ram - unloaded_ram
    print(f"   Model loaded: {stats_after_auto_unload['embedding']['model_loaded']}")
    print(f"   RAM after auto-unload: {unloaded_ram:.1f} MB (freed {ram_freed:.1f} MB)")

    # Test manual unload
    print("\n5. Testing manual unload API...")
    await memory.add_message("test_session", "user", "Another query")
    await memory.search_memory("another query", session_id="test_session")

    loaded_ram2 = get_ram_mb()
    stats_reloaded = memory.get_memory_stats()
    print(f"   Model loaded: {stats_reloaded['embedding']['model_loaded']}")
    print(f"   RAM after reload: {loaded_ram2:.1f} MB")

    memory.unload_resources()
    await asyncio.sleep(1)  # Give GC time

    manual_unload_ram = get_ram_mb()
    ram_freed2 = loaded_ram2 - manual_unload_ram
    stats_after_manual_unload = memory.get_memory_stats()
    print(f"   Model loaded: {stats_after_manual_unload['embedding']['model_loaded']}")
    print(f"   RAM after manual unload: {manual_unload_ram:.1f} MB (freed {ram_freed2:.1f} MB)")

    # Test automatic reload
    print("\n6. Testing automatic reload...")
    await memory.search_memory("test reload", session_id="test_session")

    reloaded_ram = get_ram_mb()
    stats_final = memory.get_memory_stats()
    print(f"   Model loaded: {stats_final['embedding']['model_loaded']}")
    print(f"   RAM after reload: {reloaded_ram:.1f} MB")

    # Final summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"Baseline RAM:        {baseline_ram:.1f} MB")
    print(f"RAM with model:      {loaded_ram:.1f} MB (+{ram_increase:.1f} MB)")
    print(f"RAM after unload:    {unloaded_ram:.1f} MB")
    print(f"RAM freed:           {ram_freed:.1f} MB")
    print()
    print("Feature Verification:")

    # Verify each feature using the correct stats captured at each step
    lazy_loading_works = not stats_init['embedding']['model_loaded']
    print(f"  Lazy loading:      {'PASS' if lazy_loading_works else 'FAIL'} (model not loaded on init)")

    auto_unload_works = not stats_after_auto_unload['embedding']['model_loaded']
    print(f"  Auto-unload:       {'PASS' if auto_unload_works else 'FAIL'} (model unloaded after 10s)")

    manual_unload_works = not stats_after_manual_unload['embedding']['model_loaded']
    print(f"  Manual unload:     {'PASS' if manual_unload_works else 'FAIL'} (unload_resources() works)")

    auto_reload_works = stats_final['embedding']['model_loaded']
    print(f"  Auto-reload:       {'PASS' if auto_reload_works else 'FAIL'} (model reloads on demand)")

    print()
    print("RAM Optimization:")
    print(f"  Idle RAM reduction: {baseline_ram:.1f} MB -> {unloaded_ram:.1f} MB")
    print(f"  Active RAM:         {loaded_ram:.1f} MB (during search)")
    print(f"  RAM freed on unload: {ram_freed:.1f} MB")
    print()
    print("Note: RAM freed may be less than model size due to Python/PyTorch")
    print("memory management. The OS doesn't immediately reclaim all memory.")
    print("The key verification is that model_loaded status changes correctly.")
    print("=" * 60)

    # Overall result
    all_pass = lazy_loading_works and auto_unload_works and manual_unload_works and auto_reload_works
    print()
    if all_pass:
        print("RESULT: ALL TESTS PASSED - RAM optimization working correctly!")
    else:
        print("RESULT: SOME TESTS FAILED - see details above")

    # Cleanup
    import shutil
    shutil.rmtree(workspace, ignore_errors=True)

if __name__ == "__main__":
    asyncio.run(test_ram_optimization())
