"""Tests for SubagentRegistry persistence."""

import json
import time
from pathlib import Path

import pytest

from kabot.agent.subagent_registry import SubagentRegistry, SubagentRunRecord


@pytest.fixture
def registry_path(tmp_path):
    """Provide a temporary registry file path."""
    return tmp_path / "runs.json"


@pytest.fixture
def registry(registry_path):
    """Provide a SubagentRegistry instance."""
    return SubagentRegistry(registry_path)


class TestSubagentRegistryBasic:
    """Test basic registry functionality."""

    def test_initialization(self, registry_path):
        """Test registry initialization creates parent directory."""
        registry = SubagentRegistry(registry_path)
        assert registry.registry_path == registry_path
        assert registry_path.parent.exists()

    def test_register_subagent(self, registry, registry_path):
        """Test registering a subagent creates persistent record."""
        registry.register(
            run_id="test-run-123",
            task="Test task",
            label="Test Label",
            parent_session_key="parent:session:key",
            origin_channel="telegram",
            origin_chat_id="123456"
        )

        # Verify in-memory state
        assert "test-run-123" in registry._runs
        record = registry._runs["test-run-123"]
        assert record.task == "Test task"
        assert record.label == "Test Label"
        assert record.status == "running"

        # Verify persistence
        assert registry_path.exists()
        with open(registry_path) as f:
            data = json.load(f)
        assert "test-run-123" in data["runs"]
        assert data["runs"]["test-run-123"]["task"] == "Test task"

    def test_complete_subagent(self, registry, registry_path):
        """Test completing a subagent updates status."""
        registry.register(
            run_id="test-run-123",
            task="Test task",
            label="Test",
            parent_session_key="parent",
            origin_channel="telegram",
            origin_chat_id="123"
        )

        registry.complete(
            run_id="test-run-123",
            result="Task completed successfully",
            status="completed"
        )

        # Verify status updated
        record = registry._runs["test-run-123"]
        assert record.status == "completed"
        assert record.result == "Task completed successfully"
        assert record.completed_at is not None

        # Verify persistence
        with open(registry_path) as f:
            data = json.load(f)
        assert data["runs"]["test-run-123"]["status"] == "completed"

    def test_complete_with_error(self, registry):
        """Test completing a subagent with error status."""
        registry.register(
            run_id="test-run-123",
            task="Test task",
            label="Test",
            parent_session_key="parent",
            origin_channel="telegram",
            origin_chat_id="123"
        )

        registry.complete(
            run_id="test-run-123",
            result=None,
            status="failed",
            error="Something went wrong"
        )

        record = registry._runs["test-run-123"]
        assert record.status == "failed"
        assert record.error == "Something went wrong"
        assert record.result is None


class TestSubagentRegistryQuery:
    """Test registry query functionality."""

    def test_get_run(self, registry):
        """Test getting a run by ID."""
        registry.register(
            run_id="test-run-123",
            task="Test task",
            label="Test",
            parent_session_key="parent",
            origin_channel="telegram",
            origin_chat_id="123"
        )

        record = registry.get("test-run-123")
        assert record is not None
        assert record.run_id == "test-run-123"
        assert record.task == "Test task"

    def test_get_nonexistent_run(self, registry):
        """Test getting a nonexistent run returns None."""
        record = registry.get("nonexistent")
        assert record is None

    def test_list_runs(self, registry):
        """Test listing all runs."""
        registry.register("run1", "Task 1", "Label 1", "parent", "telegram", "123")
        registry.register("run2", "Task 2", "Label 2", "parent", "telegram", "123")
        registry.register("run3", "Task 3", "Label 3", "parent", "telegram", "123")

        runs = registry.list_all()
        assert len(runs) == 3
        assert all(isinstance(r, SubagentRunRecord) for r in runs)

    def test_list_runs_by_status(self, registry):
        """Test listing runs filtered by status."""
        registry.register("run1", "Task 1", "Label 1", "parent", "telegram", "123")
        registry.register("run2", "Task 2", "Label 2", "parent", "telegram", "123")
        registry.complete("run1", "Done", "completed")

        running = registry.list_running()
        all_runs = registry.list_all()

        assert len(running) == 1
        assert running[0].run_id == "run2"
        assert len(all_runs) == 2

    def test_list_runs_by_parent(self, registry):
        """Test listing runs filtered by parent session."""
        registry.register("run1", "Task 1", "Label 1", "parent1", "telegram", "123")
        registry.register("run2", "Task 2", "Label 2", "parent2", "telegram", "123")
        registry.register("run3", "Task 3", "Label 3", "parent1", "telegram", "123")

        all_runs = registry.list_all()
        parent1_runs = [r for r in all_runs if r.parent_session_key == "parent1"]
        assert len(parent1_runs) == 2
        assert all(r.parent_session_key == "parent1" for r in parent1_runs)


class TestSubagentRegistryPersistence:
    """Test registry persistence across restarts."""

    def test_load_existing_registry(self, registry_path):
        """Test loading existing registry from disk."""
        # Create registry and add runs
        registry1 = SubagentRegistry(registry_path)
        registry1.register("run1", "Task 1", "Label 1", "parent", "telegram", "123")
        registry1.register("run2", "Task 2", "Label 2", "parent", "telegram", "123")

        # Create new registry instance (simulates restart)
        registry2 = SubagentRegistry(registry_path)

        # Verify runs were loaded
        assert len(registry2._runs) == 2
        assert "run1" in registry2._runs
        assert "run2" in registry2._runs

    def test_corrupted_registry_recovery(self, registry_path):
        """Test recovery from corrupted registry file."""
        # Create corrupted registry
        with open(registry_path, 'w') as f:
            f.write("not valid json{{{")

        # Should create new empty registry
        registry = SubagentRegistry(registry_path)
        assert len(registry._runs) == 0

    def test_empty_registry_file(self, registry_path):
        """Test handling empty registry file."""
        # Create empty file
        registry_path.touch()

        # Should create new empty registry
        registry = SubagentRegistry(registry_path)
        assert len(registry._runs) == 0


class TestSubagentRegistryCleanup:
    """Test registry cleanup functionality."""

    def test_cleanup_old_runs(self, registry):
        """Test cleanup of old completed runs."""
        # Create old completed run
        registry.register("old-run", "Old task", "Old", "parent", "telegram", "123")
        registry.complete("old-run", "Done", "completed")
        # Manually set old completed_at time
        registry._runs["old-run"].completed_at = time.time() - 90000  # 25 hours ago
        registry._save_registry()

        # Create recent run
        registry.register("new-run", "New task", "New", "parent", "telegram", "123")

        # Cleanup runs older than 24 hours
        registry.cleanup_old_runs(max_age_seconds=86400)

        # Old run should be removed, new run should remain
        assert "old-run" not in registry._runs
        assert "new-run" in registry._runs

    def test_cleanup_preserves_running(self, registry):
        """Test cleanup preserves running tasks regardless of age."""
        # Create old running task
        registry.register("old-running", "Old task", "Old", "parent", "telegram", "123")
        registry._runs["old-running"].created_at = time.time() - 90000

        # Cleanup
        registry.cleanup_old_runs(max_age_seconds=86400)

        # Running task should be preserved
        assert "old-running" in registry._runs


class TestSubagentRegistryConcurrency:
    """Test registry concurrency safety."""

    def test_concurrent_register(self, registry_path):
        """Test concurrent registration from multiple instances."""
        registry1 = SubagentRegistry(registry_path)
        registry2 = SubagentRegistry(registry_path)

        # Register from first instance
        registry1.register("run1", "Task 1", "Label 1", "parent", "telegram", "123")

        # Reload registry2 to get latest state
        registry2._load_registry()

        # Register from second instance
        registry2.register("run2", "Task 2", "Label 2", "parent", "telegram", "123")

        # Both should be persisted
        registry3 = SubagentRegistry(registry_path)
        assert len(registry3._runs) == 2
        assert "run1" in registry3._runs
        assert "run2" in registry3._runs
