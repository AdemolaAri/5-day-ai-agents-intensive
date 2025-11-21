#!/usr/bin/env python3
"""
Simple test script to verify integration modules work correctly.
"""

import sys
import os

# Add current directory to path
current_dir = os.path.dirname(__file__)
sys.path.insert(0, current_dir)

def test_imports():
    """Test that all integration modules can be imported."""
    print("Testing module imports...")
    
    try:
        from integration_pipeline import EventProcessingPipeline
        print('✅ EventProcessingPipeline imported successfully')
    except Exception as e:
        print(f'❌ EventProcessingPipeline import failed: {e}')
        return False

    try:
        from error_recovery import A2ARetryHandler, CircuitBreakerManager, DeadLetterQueue
        print('✅ Error recovery modules imported successfully')
    except Exception as e:
        print(f'❌ Error recovery import failed: {e}')
        return False

    try:
        from session_archival import SessionArchiver, SessionManager
        print('✅ Session archival modules imported successfully')
    except Exception as e:
        print(f'❌ Session archival import failed: {e}')
        return False

    try:
        from main_integration import AgentFleetIntegration
        print('✅ Main integration imported successfully')
    except Exception as e:
        print(f'❌ Main integration import failed: {e}')
        return False

    print('🎉 All imports successful!')
    return True

def test_basic_functionality():
    """Test basic functionality of integration components."""
    print("\nTesting basic functionality...")
    
    try:
        # Test EventProcessingPipeline creation
        from integration_pipeline import EventProcessingPipeline
        pipeline = EventProcessingPipeline()
        print('✅ EventProcessingPipeline created successfully')
        
        # Test SessionArchiver creation
        from session_archival import SessionArchiver
        archiver = SessionArchiver()
        print('✅ SessionArchiver created successfully')
        
        # Test A2ARetryHandler creation
        from error_recovery import A2ARetryHandler
        retry_handler = A2ARetryHandler()
        print('✅ A2ARetryHandler created successfully')
        
        # Test AgentFleetIntegration creation
        from main_integration import AgentFleetIntegration
        integration = AgentFleetIntegration()
        print('✅ AgentFleetIntegration created successfully')
        
        print('🎉 All basic functionality tests passed!')
        return True
        
    except Exception as e:
        print(f'❌ Basic functionality test failed: {e}')
        return False

if __name__ == "__main__":
    print("AgentFleet Integration Test")
    print("=" * 30)
    
    imports_ok = test_imports()
    functionality_ok = test_basic_functionality()
    
    if imports_ok and functionality_ok:
        print("\n✅ All tests passed! Integration modules are working correctly.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed.")
        sys.exit(1)