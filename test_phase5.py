#!/usr/bin/env python
"""Phase 5 Verification Script - Tests all new security and optimization components"""

import sys
import asyncio
from datetime import datetime

def test_auth_module():
    """Test authentication module"""
    print("[AUTH] Testing Authentication Module...")
    try:
        from backend.core.auth import (
            create_tokens, 
            decode_token, 
            hash_password,
            verify_password,
            Token
        )
        from backend.core.rbac import Role
        
        # Test password hashing
        pwd = "test123"
        hashed = hash_password(pwd)
        assert verify_password(pwd, hashed), "Password verification failed"
        print("  OK - Password hashing works")
        
        # Test token creation
        tokens = create_tokens(user_id=1, username="test", role=Role.STUDENT)
        # tokens is a Token object, so convert to check
        if isinstance(tokens, dict):
            assert "access_token" in tokens, "No access token"
            assert "refresh_token" in tokens, "No refresh token"
        else:
            assert hasattr(tokens, 'access_token'), "No access token"
            assert hasattr(tokens, 'refresh_token'), "No refresh token"
        print("  OK - Token creation works")
        
        # Test token decoding
        token_data = decode_token(tokens.access_token)
        assert token_data.user_id == 1, "Token data mismatch"
        print("  OK - Token decoding works")
        
        return True
    except Exception as e:
        print(f"  FAIL - Auth module test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_rbac_module():
    """Test RBAC module"""
    print("\n[RBAC] Testing RBAC Module...")
    try:
        from backend.core.rbac import Role, Permission, RoleHierarchy, ROLE_PERMISSIONS
        
        # Test role hierarchy
        hierarchy = RoleHierarchy()
        assert hierarchy.has_role(Role.ADMIN, Role.STAFF), "Admin should have Staff role"
        print("  OK - Role hierarchy works")
        
        # Test permissions
        admin_perms = ROLE_PERMISSIONS[Role.ADMIN]
        assert len(admin_perms) == len(Permission), "Admin should have all permissions"
        print(f"  OK - Permission mapping works ({len(admin_perms)} admin permissions)")
        
        return True
    except Exception as e:
        print(f"  FAIL - RBAC module test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config_module():
    """Test configuration module"""
    print("\n[CONFIG] Testing Configuration Module...")
    try:
        from backend.core.config import settings
        
        # Test basic config
        assert hasattr(settings, 'DEBUG'), "Missing DEBUG setting"
        assert hasattr(settings, 'DATABASE_URL'), "Missing DATABASE_URL setting"
        assert hasattr(settings, 'SECRET_KEY'), "Missing SECRET_KEY setting"
        print(f"  OK - Config loaded (ENV: {settings.ENV})")
        
        # Test environment methods
        assert hasattr(settings, 'is_production'), "Missing is_production method"
        assert hasattr(settings, 'is_development'), "Missing is_development method"
        print("  OK - Environment methods work")
        
        return True
    except Exception as e:
        print(f"  FAIL - Config module test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_logging_module():
    """Test logging module"""
    print("\n[LOGGING] Testing Logging Module...")
    try:
        from backend.core.logging import get_logger, StructuredLogger
        
        logger = get_logger("test_module")
        assert isinstance(logger, StructuredLogger), "Logger type mismatch"
        print("  OK - Logger creation works")
        
        # Test logging methods exist
        assert hasattr(logger, 'log_event'), "Missing log_event"
        assert hasattr(logger, 'log_error'), "Missing log_error"
        assert hasattr(logger, 'log_request'), "Missing log_request"
        print("  OK - Logging methods available")
        
        return True
    except Exception as e:
        print(f"  FAIL - Logging module test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_caching_module():
    """Test caching module"""
    print("\n[CACHE] Testing Caching Module...")
    try:
        from backend.core.caching import cache_manager, InMemoryCacheBackend
        from backend.core.config import settings
        
        # Test cache manager (enable caching temporarily)
        original_setting = settings.ENABLE_CACHING
        settings.ENABLE_CACHING = True
        
        await cache_manager.set("test_key", "test_value", ttl=300)
        value = await cache_manager.get("test_key")
        assert value == "test_value", f"Cache retrieval failed: got {value}"
        print("  OK - Cache operations work")
        
        # Test key generation
        key = cache_manager.generate_key("prefix", 1, 2, name="test")
        assert isinstance(key, str), "Key generation failed"
        print("  OK - Cache key generation works")
        
        # Restore setting
        settings.ENABLE_CACHING = original_setting
        return True
    except Exception as e:
        print(f"  FAIL - Caching module test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_background_tasks_module():
    """Test background tasks module"""
    print("\n[TASKS] Testing Background Tasks Module...")
    try:
        from backend.core.background_tasks import task_queue, TaskStatus
        
        # Test task queue
        async def dummy_task(x):
            return x * 2
        
        # Start queue
        await task_queue.start()
        print("  OK - Task queue started")
        
        # Submit task
        task_id = await task_queue.submit("test_task", dummy_task, 5)
        assert task_id, "Task submission failed"
        print(f"  OK - Task submitted (ID: {task_id})")
        
        # Wait a bit for task completion
        await asyncio.sleep(0.5)
        
        # Check task status
        task_status = task_queue.get_task_status(task_id)
        assert task_status, "Task status check failed"
        print(f"  OK - Task status: {task_status['status']}")
        
        # Stop queue
        await task_queue.stop()
        print("  OK - Task queue stopped")
        
        return True
    except Exception as e:
        print(f"  FAIL - Background tasks module test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_auth_routes():
    """Test auth routes module"""
    print("\n[ROUTES] Testing Auth Routes Module...")
    try:
        from backend.routes.auth import (
            LoginRequest,
            RegisterRequest,
            RefreshTokenRequest,
            get_user_by_username
        )
        
        # Test schema models
        login_req = LoginRequest(username="test", password="pass123")
        assert login_req.username == "test", "LoginRequest schema failed"
        print("  OK - Auth route schemas work")
        
        # Test user lookup
        user = get_user_by_username("admin")
        assert user and user["username"] == "admin", "User lookup failed"
        print("  OK - User lookup works")
        
        return True
    except Exception as e:
        print(f"  FAIL - Auth routes test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_all_tests():
    """Run all verification tests"""
    print("=" * 70)
    print("PHASE 5 - SCALING, SECURITY & OPTIMIZATION")
    print("Component Verification Tests")
    print("=" * 70)
    
    results = []
    
    # Sync tests
    results.append(("Auth Module", test_auth_module()))
    results.append(("RBAC Module", test_rbac_module()))
    results.append(("Config Module", test_config_module()))
    results.append(("Logging Module", test_logging_module()))
    results.append(("Auth Routes", test_auth_routes()))
    
    # Async tests
    results.append(("Caching Module", await test_caching_module()))
    results.append(("Background Tasks", await test_background_tasks_module()))
    
    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{name:.<40} {status}")
    
    print("-" * 70)
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\nAll Phase 5 components verified successfully!")
        return 0
    else:
        print(f"\n{total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
