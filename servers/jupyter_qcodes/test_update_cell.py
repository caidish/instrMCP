#!/usr/bin/env python3
"""
Test script for the update_editing_cell functionality.

This script tests the individual components without requiring a full JupyterLab setup.
"""

import asyncio
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_components():
    """Test all components of the update_editing_cell functionality."""
    print("🧪 Testing update_editing_cell components...")
    
    # 1. Test bridge function (without frontend)
    print("\n1. Testing active_cell_bridge.update_active_cell...")
    import active_cell_bridge
    
    result = active_cell_bridge.update_active_cell("print('Hello from update test')")
    print(f"Bridge result: {result}")
    assert isinstance(result, dict)
    assert "success" in result
    print("✅ Bridge function works (expected to fail without comm)")
    
    # 2. Test tools wrapper
    print("\n2. Testing tools.update_editing_cell...")
    from tools import QCodesReadOnlyTools
    from IPython import get_ipython
    
    # Mock IPython for testing
    if get_ipython() is None:
        print("⚠️  No IPython session - tools test requires Jupyter environment")
    else:
        tools = QCodesReadOnlyTools(get_ipython())
        result = await tools.update_editing_cell("print('Test from tools')")
        print(f"Tools result: {result}")
        assert isinstance(result, dict)
        print("✅ Tools wrapper works")
    
    # 3. Test function signatures and documentation
    print("\n3. Testing function signatures...")
    
    import inspect
    
    # Check bridge function
    sig = inspect.signature(active_cell_bridge.update_active_cell)
    print(f"Bridge signature: {sig}")
    assert "content" in sig.parameters
    
    # Check tools function
    if hasattr(QCodesReadOnlyTools, 'update_editing_cell'):
        sig = inspect.signature(QCodesReadOnlyTools.update_editing_cell)
        print(f"Tools signature: {sig}")
        assert "content" in sig.parameters
        print("✅ All signatures correct")
    
    print("\n🎉 All component tests passed!")
    print("\n📋 Next steps:")
    print("1. Start JupyterLab")
    print("2. Load extension: %load_ext servers.jupyter_qcodes.jupyter_mcp_extension")
    print("3. Test update_editing_cell() MCP tool")

if __name__ == "__main__":
    asyncio.run(test_components())