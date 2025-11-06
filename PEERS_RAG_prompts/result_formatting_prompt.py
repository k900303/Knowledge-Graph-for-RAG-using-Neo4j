"""
Result Formatting Instructions
Instructions for formatting query results to include unit information
"""

RESULT_FORMATTING_PROMPT = """
RESULT FORMATTING INSTRUCTIONS:

When Cypher query results are returned, format them to include unit information:

1. **For Financial Metrics (Revenue, Profit, etc.):**
   - Format: VALUE + RESULT_UNIT + CURRENCY
   - Example: "1,250 Million INR" (value=1250, result_unit="M", currency="INR")
   - Example: "15.5 Billion USD" (value=15.5, result_unit="B", currency="USD")

2. **For Percentage/Margin Values:**
   - Format: VALUE + PARAMETER_UNIT
   - Example: "15.40%" (value=15.40, parameter_unit="%")
   - Example: "23.5 Percent" (value=23.5, parameter_unit_name="Percent")

3. **For Ratio Values:**
   - Format: VALUE + PARAMETER_UNIT
   - Example: "2.5x" (value=2.5, parameter_unit="x")
   - Example: "1.8 Ratio" (value=1.8, parameter_unit_name="Ratio")

4. **For Count/Number Values:**
   - Format: VALUE + PARAMETER_UNIT
   - Example: "450 #" or "450 units" (value=450, parameter_unit="#")

5. **For Area/Volume/Physical Measurements:**
   - Format: VALUE + PARAMETER_UNIT
   - Example: "1,200 sq mt" (value=1200, parameter_unit="sq mt")
   - Example: "500 cubic metres" (value=500, parameter_unit="cubic metres")

DISPLAY FORMAT PRIORITY:
1. Use result_unit (short_name) for scale/magnitude display
2. Use parameter_unit (short_name) for measurement type display  
3. Combine both when appropriate: "15.40% of 1,250 Million"

FIELD MAPPING:
- parameter_unit_name: Full name (e.g., "Percent", "Amount", "Ratio")
- parameter_unit: Short form (e.g., "%", "Amount", "x")
- parameter_shortcode: Type identifier (e.g., "u")
- result_unit_name: Full scale name (e.g., "Million", "Billion", "Absolute")
- result_unit: Short scale (e.g., "M", "B", "Abs")
- result_shortcode: Scale identifier (e.g., "scid")

SUMMARY FORMAT:
Always present data as: **VALUE + UNIT** so users can understand the scale and measurement type.

Example Good Summary:
"Kajaria Ceramics' EBITDA margin for 1QFY-2025 is 15.60%, showing a YoY decline of -29.55%"

Example Bad Summary (missing units):
"Kajaria Ceramics' EBITDA margin for 1QFY-2025 is 15.60, showing a YoY decline of -29.55"
"""


