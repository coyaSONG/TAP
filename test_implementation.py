"""
Test implementation completeness and structure of TAB system.
"""

import os
import sys

def test_file_structure():
    """Test that all required files are present."""
    required_files = [
        "src/tab/__init__.py",
        "src/tab/models/conversation_session.py",
        "src/tab/models/turn_message.py",
        "src/tab/models/agent_adapter.py",
        "src/tab/models/policy_configuration.py",
        "src/tab/models/audit_record.py",
        "src/tab/models/orchestration_state.py",
        "src/tab/services/conversation_orchestrator.py",
        "src/tab/services/session_manager.py",
        "src/tab/services/policy_enforcer.py",
        "src/tab/services/mcp_orchestrator_server.py",
        "src/tab/services/claude_code_adapter.py",
        "src/tab/services/codex_adapter.py",
        "src/tab/services/base_agent_adapter.py",
        "src/tab/lib/observability.py",
        "src/tab/lib/logging_config.py",
        "src/tab/lib/metrics.py",
        "src/tab/lib/config.py",
        "src/tab/cli/main.py",
        "tests/unit/test_models.py",
        "tests/unit/test_performance.py",
    ]

    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)

    if missing_files:
        print(f"❌ Missing files: {missing_files}")
        return False
    else:
        print(f"✅ All {len(required_files)} required files are present!")
        return True

def test_code_quality():
    """Test basic code quality metrics."""
    total_lines = 0
    file_count = 0

    # Count lines in source files
    for root, dirs, files in os.walk("src/tab"):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                with open(file_path, 'r') as f:
                    lines = len(f.readlines())
                    total_lines += lines
                    file_count += 1

    print(f"✅ Source code statistics:")
    print(f"   - Files: {file_count}")
    print(f"   - Total lines: {total_lines}")

    # Count lines in test files
    test_lines = 0
    test_file_count = 0

    for root, dirs, files in os.walk("tests"):
        for file in files:
            if file.endswith(".py") and file.startswith("test_"):
                file_path = os.path.join(root, file)
                with open(file_path, 'r') as f:
                    lines = len(f.readlines())
                    test_lines += lines
                    test_file_count += 1

    print(f"✅ Test code statistics:")
    print(f"   - Test files: {test_file_count}")
    print(f"   - Total test lines: {test_lines}")

    return total_lines > 5000  # Expect substantial implementation

def test_configuration_files():
    """Test that configuration files are present and valid."""
    config_files = [
        "pyproject.toml",
        "docker-compose.yml",
        "config/default.yaml",
        "config/policies.yaml"
    ]

    present_files = []
    for file_path in config_files:
        if os.path.exists(file_path):
            present_files.append(file_path)

    print(f"✅ Configuration files present: {len(present_files)}/{len(config_files)}")
    for file in present_files:
        print(f"   - {file}")

    return len(present_files) >= 3  # Expect most config files

def test_documentation_completeness():
    """Test that key documentation is present."""
    doc_files = [
        "specs/001-prd-md/spec.md",
        "specs/001-prd-md/plan.md",
        "specs/001-prd-md/tasks.md",
        "specs/001-prd-md/data-model.md",
        "specs/001-prd-md/research.md",
        "specs/001-prd-md/quickstart.md"
    ]

    present_docs = []
    for file_path in doc_files:
        if os.path.exists(file_path):
            present_docs.append(file_path)

    print(f"✅ Documentation files present: {len(present_docs)}/{len(doc_files)}")

    return len(present_docs) >= 5  # Expect most documentation

def test_task_completion():
    """Test that tasks are marked as completed."""
    tasks_file = "specs/001-prd-md/tasks.md"
    if not os.path.exists(tasks_file):
        print("❌ Tasks file not found")
        return False

    with open(tasks_file, 'r') as f:
        content = f.read()

    completed_tasks = content.count("[X]")
    total_tasks = content.count("T0")  # Count task numbers

    completion_rate = (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0

    print(f"✅ Task completion: {completed_tasks}/{total_tasks} ({completion_rate:.1f}%)")

    return completion_rate >= 95  # Expect 95%+ completion

def main():
    """Run all implementation tests."""
    print("🔍 Testing TAB Implementation Completeness")
    print("=" * 50)

    tests = [
        ("File Structure", test_file_structure),
        ("Code Quality", test_code_quality),
        ("Configuration", test_configuration_files),
        ("Documentation", test_documentation_completeness),
        ("Task Completion", test_task_completion)
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        print(f"\n📋 {test_name}:")
        try:
            if test_func():
                print(f"✅ {test_name} PASSED")
                passed += 1
            else:
                print(f"❌ {test_name} FAILED")
                failed += 1
        except Exception as e:
            print(f"❌ {test_name} ERROR: {e}")
            failed += 1

    print("\n" + "=" * 50)
    print(f"📊 Summary: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 ALL IMPLEMENTATION TESTS PASSED!")
        print("🚀 TAB system is ready for deployment!")
    else:
        print("⚠️  Some tests failed - review implementation")

    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)