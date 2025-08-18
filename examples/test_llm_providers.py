#!/usr/bin/env python3
"""
Test script for different LLM providers
"""
import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from strategy_agent.llm_client import LLMConfig, test_llm_client


async def test_provider(provider_name: str, model: str, api_key: str):
    """Test a specific LLM provider"""
    print(f"\n🧪 Testing {provider_name}...")
    print(f"Model: {model}")
    
    try:
        config = LLMConfig(
            model=model,
            api_key=api_key,
            temperature=0.7,
            timeout=30
        )
        
        success = await test_llm_client(config)
        return success
        
    except Exception as e:
        print(f"❌ {provider_name} test failed: {e}")
        return False


async def main():
    """Test multiple LLM providers"""
    print("🚀 LLM Provider Test Suite")
    print("=" * 50)
    
    tests = []
    
    # Test via LLM_* environment variables (primary method)
    llm_model = os.getenv("LLM_MODEL")
    llm_key = os.getenv("LLM_API_KEY")
    llm_base_url = os.getenv("LLM_BASE_URL")
    
    if llm_model and llm_key:
        provider_name = llm_model.split("/")[0] if "/" in llm_model else "OpenAI"
        tests.append((f"Configured ({provider_name})", llm_model, llm_key, llm_base_url))
    
    if not tests:
        print("❌ No LLM providers configured!")
        print("\nTo test providers, set the required environment variables:")
        print("  export LLM_MODEL='provider/model'  # e.g., 'deepseek/deepseek-chat', 'openai/gpt-4o-mini'")
        print("  export LLM_API_KEY='sk-...'")
        print("\nExamples:")
        print("  export LLM_MODEL='deepseek/deepseek-chat' LLM_API_KEY='sk-...'")
        print("  export LLM_MODEL='openai/gpt-4o-mini' LLM_API_KEY='sk-...'")
        return 1
    
    # Run tests
    results = []
    for test_args in tests:
        success = await test_provider(*test_args)
        results.append((test_args[0], success))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    
    passed = 0
    for provider, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {provider}: {status}")
        if success:
            passed += 1
    
    print(f"\nTotal: {passed}/{len(results)} providers working")
    
    return 0 if passed > 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)