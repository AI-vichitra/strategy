"""Test blueprint service"""
import sys
sys.path.insert(0, '.')

from services.blueprint_service import load_blueprints, get_blueprint_for_agent, build_section_prompt

# Test 1: load
bp = load_blueprints()
assert "common_sections" in bp
assert "agent_blueprints" in bp
assert "default_blueprint" in bp
print(f"✓ Loaded: {len(bp['agent_blueprints'])} agent blueprints")

# Test 2: brand-positioning sections (hyphenated key)
sections = get_blueprint_for_agent("brand-positioning")
print(f"✓ brand-positioning: {len(sections)} sections")
for s in sections:
    print(f"  {s['order']}. {s['title']}")
assert sections[0]['title'] == "Executive Summary"
assert sections[-1]['title'] == "Measurement & Roadmap"

# Test 3: title format lookup (what build_system_prompt passes)
sections_title = get_blueprint_for_agent("Brand Positioning")
assert len(sections_title) == len(sections)
print(f"✓ 'Brand Positioning' (title format) lookup works: {len(sections_title)} sections")

# Test 4: snake_case fallback
sections_snake = get_blueprint_for_agent("brand_positioning")
assert len(sections_snake) == len(sections)
print(f"✓ 'brand_positioning' (snake_case) lookup works: {len(sections_snake)} sections")

# Test 5: unknown falls back to default
default_sections = get_blueprint_for_agent("some_unknown_type")
common_count = len(bp['common_sections'])
default_specific = len(bp['default_blueprint']['type_specific_sections'])
assert len(default_sections) == common_count + default_specific
print(f"✓ default fallback: {len(default_sections)} sections ({common_count} common + {default_specific} default)")

# Test 6: prompt output
prompt = build_section_prompt("brand-positioning")
assert "Executive Summary" in prompt
assert "Positioning Map" in prompt
assert "### Executive Summary" in prompt
assert "CRITICAL FORMATTING RULES" in prompt
print(f"✓ prompt length: {len(prompt)} chars")
print(f"\n--- First 500 chars of prompt ---\n{prompt[:500]}")

# Test 7: all blueprints reachable
for key in bp['agent_blueprints']:
    s = get_blueprint_for_agent(key)
    print(f"✓ {key}: {len(s)} sections")

print("\n✅ All tests passed")
