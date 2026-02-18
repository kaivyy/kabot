# Setup Wizard Comprehensive Fixes - Design Document

**Date:** 2026-02-18
**Status:** Approved
**Scope:** Critical + Core Features (Option B)

## Overview

This design addresses critical setup wizard issues and adds essential missing features to provide users with a complete, reliable onboarding experience. We'll use a Sequential Phase Approach to fix blocking issues first, then add core functionality.

## Problem Statement

The current setup wizard has several critical issues that prevent proper deployment and user onboarding:

1. **Broken service installers** - Windows PowerShell script corrupted, Linux script empty
2. **Code quality issues** - Duplicate methods, indentation problems
3. **Missing core features** - No uninstall scripts, no configuration backup, no state persistence
4. **Incomplete functionality** - Built-in skills not installed, no API key validation

## Design Approach

**Sequential Phase Approach**: Fix critical blocking issues first, then add essential features. This minimizes risk while ensuring the most impactful problems are resolved immediately.

## Phase 1: Critical Fixes

### Service Installers Reconstruction

**Windows Service Installer (`deployment/install-kabot-service.ps1`)**
- Complete rewrite with proper PowerShell syntax
- Fix all `$env:` variable references
- Add comprehensive error handling and validation
- Include service configuration templates
- Add service management utilities (start/stop/status/uninstall)
- Test with different Windows versions and permission levels

**Linux Service Installer (`deployment/install-linux-service.sh`)**
- Implement complete systemd service creation
- Add service file template generation
- Support both user and system service installation
- Include service management commands
- Add proper permission handling and validation
- Test across major Linux distributions

**Service Templates**
- Create systemd service file template
- Create Windows service configuration
- Include environment variable handling
- Add logging and restart policies

### Code Quality Fixes

**Remove Duplicate Method**
- Delete incomplete `_configure_skills` method at lines 362-379 in `kabot/cli/setup_wizard.py`
- Ensure complete method at lines 380-514 remains functional
- Add code comments to prevent future duplication

**Fix Indentation Issues**
- Correct WhatsApp configuration indentation at line 803
- Standardize code formatting throughout setup wizard
- Add linting validation to prevent future issues

**Error Handling Improvements**
- Add try-catch blocks around critical operations
- Provide clear, actionable error messages
- Include recovery suggestions for common failures
- Add logging for debugging setup issues

### API Key Validation

**Provider-Specific Validation**
- OpenAI: Test with simple completion call
- Anthropic: Validate with Claude API ping
- Groq: Test model availability
- Other providers: Basic connectivity tests

**Validation Framework**
- Create base validator class
- Implement provider-specific validators
- Add timeout handling for network calls
- Provide clear feedback on validation results
- Skip validation for empty/optional keys

## Phase 2: Core Features

### Uninstall Scripts

**Windows Uninstaller (`uninstall.ps1`)**
- Remove Windows service if installed
- Clean up PATH environment variable
- Remove installation directory
- Interactive prompt for configuration cleanup
- Registry cleanup for service entries
- Backup important data before removal

**Linux/Mac Uninstaller (`uninstall.sh`)**
- Remove systemd service files
- Clean up ~/.local/bin entries
- Remove installation directories
- Interactive configuration cleanup
- Preserve user data option
- Handle permission requirements

**Uninstall Features**
- Dry-run mode to show what would be removed
- Selective removal (keep configs, remove binaries)
- Backup creation before uninstall
- Rollback capability if uninstall fails

### Configuration Backup & Rollback

**Backup System**
- Automatic backup before any configuration changes
- Versioned backups in `~/.kabot/backups/` with timestamps
- Backup integrity validation using checksums
- Configurable retention policy (keep last N backups)

**Rollback Mechanism**
- List available backup versions
- Preview changes before rollback
- Atomic rollback operations
- Validation after rollback completion
- Emergency recovery mode for corrupted configs

**Backup Structure**
```
~/.kabot/backups/
├── 2026-02-18T14-30-00_pre-setup/
│   ├── config.json
│   ├── metadata.json
│   └── checksum.sha256
└── 2026-02-18T15-45-00_pre-channel-config/
    ├── config.json
    ├── metadata.json
    └── checksum.sha256
```

### Setup State Persistence

**State Tracking**
- JSON-based state file: `~/.kabot/setup-state.json`
- Track completion status of each setup section
- Store user preferences and selections
- Record timestamps and version information

**Resume Capability**
- Detect interrupted setup on restart
- Offer to resume from last completed section
- Validate partial configuration before resuming
- Clear state file on successful completion

**State File Structure**
```json
{
  "version": "1.0",
  "started_at": "2026-02-18T14:30:00Z",
  "last_updated": "2026-02-18T14:35:00Z",
  "sections": {
    "workspace": {"completed": true, "timestamp": "..."},
    "auth": {"completed": false, "in_progress": true},
    "channels": {"completed": false},
    "skills": {"completed": false}
  },
  "user_selections": {
    "workspace_path": "/home/user/.kabot/workspace",
    "selected_providers": ["openai", "anthropic"]
  }
}
```

### Built-in Skills Installation Fix

**Integration with Setup Flow**
- Modify setup wizard to call `_install_builtin_skills()` method
- Add skills installation as a setup section
- Provide progress indicators during installation
- Handle installation failures gracefully

**Skills Installation Improvements**
- Dependency validation before installation
- Version compatibility checking
- Installation success verification
- Error recovery and retry mechanisms
- Default skills configuration templates

**Skills Management**
- List available built-in skills
- Allow selective installation
- Provide skill descriptions and requirements
- Handle skill dependencies and conflicts

## Architecture Considerations

### Error Handling Strategy
- Fail-fast for critical errors (corrupted config, permission issues)
- Graceful degradation for non-critical features
- Clear error messages with suggested solutions
- Comprehensive logging for debugging

### Testing Strategy
- Unit tests for validation functions
- Integration tests for service installers
- End-to-end tests for complete setup flow
- Cross-platform testing (Windows, Linux, macOS)

### Backwards Compatibility
- Maintain compatibility with existing configurations
- Migrate old config formats automatically
- Preserve user customizations during upgrades
- Provide fallback options for deprecated features

## Success Criteria

### Phase 1 Success Metrics
- Windows service installer works on Windows 10/11
- Linux service installer works on Ubuntu, CentOS, Debian
- No duplicate code or indentation issues
- API key validation catches invalid keys before saving

### Phase 2 Success Metrics
- Uninstall scripts cleanly remove all components
- Configuration backup/rollback works reliably
- Setup can be resumed after interruption
- Built-in skills are properly installed and configured

## Risk Mitigation

### High-Risk Areas
- Service installer modifications (could break existing deployments)
- Configuration file changes (could corrupt user settings)
- Setup flow modifications (could break existing workflows)

### Mitigation Strategies
- Comprehensive testing before deployment
- Backup creation before any changes
- Rollback mechanisms for failed operations
- Gradual rollout with monitoring

## Implementation Notes

### Development Approach
- Create feature branches for each phase
- Implement comprehensive tests alongside features
- Use code review for all service installer changes
- Test on multiple platforms before merging

### Documentation Updates
- Update installation documentation
- Create troubleshooting guides
- Document new uninstall procedures
- Add setup state recovery instructions

---

**Next Steps:**
1. Create detailed implementation plan with specific tasks
2. Set up testing framework for setup process validation
3. Begin Phase 1 implementation with service installer fixes
4. Update CHANGELOG.md with planned improvements