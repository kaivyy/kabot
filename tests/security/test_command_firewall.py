"""Tests for command execution firewall."""


import pytest
import yaml

from kabot.security.command_firewall import ApprovalDecision, CommandFirewall, CommandPattern


@pytest.fixture
def temp_config_path(tmp_path):
    """Provide temporary config path."""
    return tmp_path / "command_approvals.yaml"


@pytest.fixture
def firewall(temp_config_path):
    """Provide CommandFirewall instance with default config."""
    return CommandFirewall(temp_config_path)


class TestCommandPattern:
    """Test CommandPattern matching."""

    def test_exact_match(self):
        """Test exact pattern matching."""
        pattern = CommandPattern("git status", "Test")
        assert pattern.matches("git status")
        assert not pattern.matches("git status --short")
        assert not pattern.matches("git log")

    def test_wildcard_match(self):
        """Test wildcard pattern matching."""
        pattern = CommandPattern("git *", "Test")
        assert pattern.matches("git status")
        assert pattern.matches("git log")
        assert pattern.matches("git diff --cached")
        assert not pattern.matches("ls")

    def test_complex_wildcard(self):
        """Test complex wildcard patterns."""
        pattern = CommandPattern("npm test*", "Test")
        assert pattern.matches("npm test")
        assert pattern.matches("npm test --coverage")
        assert pattern.matches("npm test unit")
        assert not pattern.matches("npm install")

    def test_invalid_regex(self):
        """Test that special characters are properly escaped."""
        # After escaping, [invalid( becomes a literal match pattern
        pattern = CommandPattern("[invalid(", "Test")
        assert pattern.compiled_regex is not None
        assert pattern.matches("[invalid(")
        assert not pattern.matches("invalid")


class TestCommandFirewallBasic:
    """Test basic firewall functionality."""

    def test_initialization_creates_default_config(self, temp_config_path):
        """Test that initialization creates default config."""
        assert not temp_config_path.exists()

        firewall = CommandFirewall(temp_config_path)

        assert temp_config_path.exists()
        assert firewall.hash_path.exists()

    def test_default_policy_is_ask(self, firewall):
        """Test that default policy is 'ask'."""
        info = firewall.get_policy_info()
        assert info['policy'] == 'ask'

    def test_default_config_has_allowlist(self, firewall):
        """Test that default config includes allowlist."""
        info = firewall.get_policy_info()
        assert info['allowlist_count'] > 0

    def test_default_config_has_denylist(self, firewall):
        """Test that default config includes denylist."""
        info = firewall.get_policy_info()
        assert info['denylist_count'] > 0


class TestPolicyModes:
    """Test different policy modes."""

    def test_ask_mode_returns_ask(self, temp_config_path):
        """Test that 'ask' mode returns ASK for all commands."""
        config = {
            'policy': 'ask',
            'allowlist': [],
            'denylist': []
        }
        with open(temp_config_path, 'w') as f:
            yaml.dump(config, f)

        firewall = CommandFirewall(temp_config_path)

        assert firewall.check_command("ls") == ApprovalDecision.ASK
        assert firewall.check_command("rm -rf /") == ApprovalDecision.ASK

    def test_deny_mode_returns_deny(self, temp_config_path):
        """Test that 'deny' mode returns DENY for all commands."""
        config = {
            'policy': 'deny',
            'allowlist': [],
            'denylist': []
        }
        with open(temp_config_path, 'w') as f:
            yaml.dump(config, f)

        firewall = CommandFirewall(temp_config_path)

        assert firewall.check_command("ls") == ApprovalDecision.DENY
        assert firewall.check_command("git status") == ApprovalDecision.DENY

    def test_allowlist_mode_allows_matching(self, temp_config_path):
        """Test that 'allowlist' mode allows matching commands."""
        config = {
            'policy': 'allowlist',
            'allowlist': [
                {'pattern': 'git status', 'description': 'Test'},
                {'pattern': 'ls*', 'description': 'Test'}
            ],
            'denylist': []
        }
        with open(temp_config_path, 'w') as f:
            yaml.dump(config, f)

        firewall = CommandFirewall(temp_config_path)

        assert firewall.check_command("git status") == ApprovalDecision.ALLOW
        assert firewall.check_command("ls") == ApprovalDecision.ALLOW
        assert firewall.check_command("ls -la") == ApprovalDecision.ALLOW

    def test_allowlist_mode_asks_for_non_matching(self, temp_config_path):
        """Test that 'allowlist' mode asks for non-matching commands."""
        config = {
            'policy': 'allowlist',
            'allowlist': [
                {'pattern': 'git status', 'description': 'Test'}
            ],
            'denylist': []
        }
        with open(temp_config_path, 'w') as f:
            yaml.dump(config, f)

        firewall = CommandFirewall(temp_config_path)

        assert firewall.check_command("rm -rf /") == ApprovalDecision.ASK


class TestDenylist:
    """Test denylist functionality."""

    def test_denylist_blocks_matching_commands(self, temp_config_path):
        """Test that denylist blocks matching commands."""
        config = {
            'policy': 'ask',
            'allowlist': [],
            'denylist': [
                {'pattern': 'rm -rf *', 'description': 'Dangerous'},
                {'pattern': 'dd if=*', 'description': 'Dangerous'}
            ]
        }
        with open(temp_config_path, 'w') as f:
            yaml.dump(config, f)

        firewall = CommandFirewall(temp_config_path)

        assert firewall.check_command("rm -rf /") == ApprovalDecision.DENY
        assert firewall.check_command("dd if=/dev/zero") == ApprovalDecision.DENY

    def test_denylist_has_priority_over_allowlist(self, temp_config_path):
        """Test that denylist takes priority over allowlist."""
        config = {
            'policy': 'allowlist',
            'allowlist': [
                {'pattern': 'rm *', 'description': 'Allow rm'}
            ],
            'denylist': [
                {'pattern': 'rm -rf *', 'description': 'Deny recursive rm'}
            ]
        }
        with open(temp_config_path, 'w') as f:
            yaml.dump(config, f)

        firewall = CommandFirewall(temp_config_path)

        # Denylist should win
        assert firewall.check_command("rm -rf /") == ApprovalDecision.DENY

        # But non-recursive rm should be allowed
        assert firewall.check_command("rm file.txt") == ApprovalDecision.ALLOW


class TestTamperDetection:
    """Test tamper detection functionality."""

    def test_integrity_check_passes_initially(self, firewall):
        """Test that integrity check passes on first load."""
        info = firewall.get_policy_info()
        assert info['integrity_verified'] is True

    def test_integrity_check_detects_modification(self, firewall, temp_config_path):
        """Test that integrity check detects config modification."""
        # Modify config file
        with open(temp_config_path, 'a') as f:
            f.write("\n# Tampered\n")

        # Integrity check should fail
        assert firewall._verify_integrity() is False

    def test_tampered_config_denies_all_commands(self, firewall, temp_config_path):
        """Test that tampered config causes all commands to be denied."""
        # Modify config file
        with open(temp_config_path, 'a') as f:
            f.write("\n# Tampered\n")

        # All commands should be denied
        assert firewall.check_command("ls") == ApprovalDecision.DENY
        assert firewall.check_command("git status") == ApprovalDecision.DENY

    def test_hash_file_created(self, firewall):
        """Test that hash file is created."""
        assert firewall.hash_path.exists()

    def test_hash_file_contains_valid_hash(self, firewall):
        """Test that hash file contains valid SHA256 hash."""
        with open(firewall.hash_path) as f:
            stored_hash = f.read().strip()

        # Should be 64 character hex string
        assert len(stored_hash) == 64
        assert all(c in '0123456789abcdef' for c in stored_hash)

    def test_reload_config_updates_hash(self, firewall, temp_config_path):
        """Test that reloading config updates hash."""
        original_hash = firewall.config_hash

        # Modify config legitimately
        config = {
            'policy': 'deny',
            'allowlist': [],
            'denylist': []
        }
        with open(temp_config_path, 'w') as f:
            yaml.dump(config, f)

        # Reload
        firewall.reload_config()

        # Hash should be different
        assert firewall.config_hash != original_hash


class TestAddToAllowlist:
    """Test adding patterns to allowlist."""

    def test_add_to_allowlist(self, firewall):
        """Test adding pattern to allowlist."""
        result = firewall.add_to_allowlist("echo *", "Print text")
        assert result is True

        # Reload to verify
        firewall.reload_config()
        info = firewall.get_policy_info()

        # Should have one more pattern
        assert info['allowlist_count'] > 0

    def test_added_pattern_works(self, firewall):
        """Test that added pattern actually allows commands."""
        firewall.add_to_allowlist("echo *", "Print text")
        firewall.reload_config()

        # Change to allowlist mode
        with open(firewall.config_path) as f:
            config = yaml.safe_load(f)
        config['policy'] = 'allowlist'
        with open(firewall.config_path, 'w') as f:
            yaml.dump(config, f)
        firewall.reload_config()

        assert firewall.check_command("echo hello") == ApprovalDecision.ALLOW


class TestDefaultConfig:
    """Test default configuration."""

    def test_default_allows_safe_git_commands(self, firewall):
        """Test that default config allows safe git commands."""
        # Change to allowlist mode
        with open(firewall.config_path) as f:
            config = yaml.safe_load(f)
        config['policy'] = 'allowlist'
        with open(firewall.config_path, 'w') as f:
            yaml.dump(config, f)
        firewall.reload_config()

        assert firewall.check_command("git status") == ApprovalDecision.ALLOW
        assert firewall.check_command("git diff") == ApprovalDecision.ALLOW
        assert firewall.check_command("git log") == ApprovalDecision.ALLOW

    def test_default_denies_dangerous_commands(self, firewall):
        """Test that default config denies dangerous commands."""
        assert firewall.check_command("rm -rf /") == ApprovalDecision.DENY
        assert firewall.check_command("dd if=/dev/zero") == ApprovalDecision.DENY
        assert firewall.check_command("mkfs.ext4") == ApprovalDecision.DENY

    def test_default_denies_fork_bomb(self, firewall):
        """Test that default config denies fork bomb."""
        assert firewall.check_command(":(){ :|:& };:") == ApprovalDecision.DENY


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_command(self, firewall):
        """Test handling of empty command."""
        decision = firewall.check_command("")
        assert decision in [ApprovalDecision.ASK, ApprovalDecision.DENY]

    def test_corrupted_config_file(self, temp_config_path):
        """Test handling of corrupted config file."""
        # Create corrupted config
        with open(temp_config_path, 'w') as f:
            f.write("not valid yaml: {{{")

        firewall = CommandFirewall(temp_config_path)

        # Should fail-safe to deny mode
        assert firewall.check_command("ls") == ApprovalDecision.DENY

    def test_missing_policy_key(self, temp_config_path):
        """Test handling of missing policy key."""
        config = {
            'allowlist': [],
            'denylist': []
        }
        with open(temp_config_path, 'w') as f:
            yaml.dump(config, f)

        firewall = CommandFirewall(temp_config_path)
        info = firewall.get_policy_info()

        # Should default to 'ask'
        assert info['policy'] == 'ask'

    def test_malformed_pattern(self, temp_config_path):
        """Test handling of malformed pattern."""
        config = {
            'policy': 'allowlist',
            'allowlist': [
                {'pattern': '[invalid(', 'description': 'Bad pattern'}
            ],
            'denylist': []
        }
        with open(temp_config_path, 'w') as f:
            yaml.dump(config, f)

        firewall = CommandFirewall(temp_config_path)

        # Should not crash, pattern just won't match
        decision = firewall.check_command("anything")
        assert decision == ApprovalDecision.ASK


class TestIntegration:
    """Integration tests."""

    def test_full_workflow(self, temp_config_path):
        """Test complete workflow from creation to usage."""
        # Create firewall
        firewall = CommandFirewall(temp_config_path)

        # Check default behavior
        assert firewall.check_command("ls") == ApprovalDecision.ASK

        # Add to allowlist
        firewall.add_to_allowlist("ls*", "List files")

        # Change to allowlist mode
        with open(temp_config_path) as f:
            config = yaml.safe_load(f)
        config['policy'] = 'allowlist'
        with open(temp_config_path, 'w') as f:
            yaml.dump(config, f)

        # Reload
        firewall.reload_config()

        # Now ls should be allowed
        assert firewall.check_command("ls") == ApprovalDecision.ALLOW
        assert firewall.check_command("ls -la") == ApprovalDecision.ALLOW

        # But other commands should ask
        assert firewall.check_command("rm file") == ApprovalDecision.ASK

    def test_multiple_firewalls_same_config(self, temp_config_path):
        """Test multiple firewall instances with same config."""
        firewall1 = CommandFirewall(temp_config_path)
        firewall2 = CommandFirewall(temp_config_path)

        # Both should have same behavior
        assert firewall1.check_command("ls") == firewall2.check_command("ls")

    def test_config_persistence(self, temp_config_path):
        """Test that config persists across instances."""
        # Create and modify
        firewall1 = CommandFirewall(temp_config_path)
        firewall1.add_to_allowlist("test*", "Test commands")

        # Create new instance
        firewall2 = CommandFirewall(temp_config_path)

        # Should have the added pattern
        info = firewall2.get_policy_info()
        assert info['allowlist_count'] > 0
