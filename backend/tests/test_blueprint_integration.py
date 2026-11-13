"""
Integration test — verify blueprint sections appear in
the actual system prompt that build_system_prompt() returns.
"""
import sys
sys.path.insert(0, '.')

from services.ai_service import build_system_prompt

# Test 1: Brand Positioning prompt contains blueprint sections
prompt = build_system_prompt("Test Brand", "Brand Positioning", None, "")
print(f"Total prompt length: {len(prompt)} chars")

# Check blueprint marker
assert "## REPORT STRUCTURE" in prompt, "❌ Blueprint marker missing from prompt"
print("✓ '## REPORT STRUCTURE' found in prompt")

# Check all 9 Brand Positioning sections are present
expected_sections = [
    "Executive Summary",
    "Market Context",
    "Consumer Landscape",
    "Competitive Landscape",
    "Key Insights",
    "Strategic Approach",
    "Positioning Map",
    "Strategy Build",
    "Measurement & Roadmap"
]

for section in expected_sections:
    assert section in prompt, f"❌ Missing section: {section}"
    print(f"✓ Found: {section}")

# Check formatting rules are present
assert "CRITICAL FORMATTING RULES" in prompt, "❌ Formatting rules missing"
print("✓ Formatting rules present")

# Check blueprint comes AFTER agent-specific content
bp_pos = prompt.index("## REPORT STRUCTURE")
# Brand Positioning should have its own prompt content before the blueprint
assert bp_pos > 500, f"❌ Blueprint too early in prompt (pos {bp_pos}), agent content may be missing"
print(f"✓ Blueprint positioned at char {bp_pos} (after agent-specific content)")

# Test 2: Competition Analysis
prompt2 = build_system_prompt("Test Brand", "Competition Analysis", None, "")
assert "Competitor Deep Dive" in prompt2, "❌ Competition Analysis sections missing"
print(f"\n✓ Competition Analysis prompt: {len(prompt2)} chars, has Competitor Deep Dive")

# Test 3: Unknown agent type falls back to default blueprint
prompt3 = build_system_prompt("Test Brand", "Some Random Agent", None, "")
assert "## REPORT STRUCTURE" in prompt3, "❌ Default blueprint not injected for unknown agent"
assert "Detailed Analysis" in prompt3, "❌ Default sections missing"
print(f"✓ Unknown agent fallback: {len(prompt3)} chars, has default sections")

# Print a snippet showing where blueprint lands in the prompt
print(f"\n--- Blueprint position in Brand Positioning prompt ---")
start = max(0, bp_pos - 200)
end = min(len(prompt), bp_pos + 300)
print(f"...{prompt[start:end]}...")

print("\n✅ All integration tests passed")
