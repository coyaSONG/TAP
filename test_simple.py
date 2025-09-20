"""
Simple test to verify basic Python functionality without complex imports.
"""

def test_basic_functionality():
    """Test basic Python functionality."""
    # Test string operations
    assert "hello" + " world" == "hello world"

    # Test list operations
    test_list = [1, 2, 3]
    assert len(test_list) == 3

    # Test dictionary operations
    test_dict = {"key": "value"}
    assert test_dict["key"] == "value"

    print("✅ Basic functionality tests passed!")

def test_imports():
    """Test that we can import standard libraries."""
    import json
    import datetime
    import asyncio

    # Test JSON serialization
    data = {"test": "value"}
    json_str = json.dumps(data)
    parsed = json.loads(json_str)
    assert parsed == data

    # Test datetime
    now = datetime.datetime.now()
    assert isinstance(now, datetime.datetime)

    print("✅ Import tests passed!")

def test_async_functionality():
    """Test async functionality."""
    import asyncio

    async def async_function():
        await asyncio.sleep(0.01)
        return "async result"

    # Run async function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(async_function())
        assert result == "async result"
    finally:
        loop.close()

    print("✅ Async functionality tests passed!")

if __name__ == "__main__":
    test_basic_functionality()
    test_imports()
    test_async_functionality()
    print("\n🎉 All simple tests completed successfully!")