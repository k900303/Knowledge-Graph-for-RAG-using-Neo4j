# Sample Queries & System Capabilities

## ✅ Supported Query Patterns

### **Pattern: Single Company + Single Parameter + Single Period**

1. **"What is the EBITA margin of Kajaria Ceramics for Q1FY2025?"**
2. **"Show me the revenue of Reliance Industries for the latest quarter"**
3. **"What was the profit margin for Asian Paints in FY-2024?"**
4. **"Show me the EBITA margin of Kajaria for 2QFY-2025"**
5. **"What is the operating margin of Tata Motors for the most recent period?"**

---

### **Pattern: Single Company + Single Parameter + Multiple Periods**

6. **"Show me the revenue of Kajaria Ceramics for Q1, Q2, Q3, and Q4 of FY2025"**
7. **"What was the EBITA margin for Kajaria across all quarters of FY2025?"**
8. **"Compare revenue of Reliance for 1QFY2024, 2QFY2024, and 3QFY2024"**
9. **"Show me Kajaria's profit margin for last 4 quarters"**
10. **"What is the revenue trend for Asian Paints in FY2024 and FY2025?"**

---

### **Pattern: Single Company + Multiple Parameters + Single Period**

11. **"Show me revenue, profit, and EBITA margin of Kajaria for latest quarter"**
12. **"What are the revenue and profit margin of Reliance for Q1FY2025?"**
13. **"Compare revenue and operating costs for Asian Paints in FY-2024"**
14. **"Show me multiple financial metrics for Kajaria for the latest period"**

---

### **Pattern: Single Company + Multiple Parameters + Multiple Periods**

15. **"Show me revenue, profit, and EBITA margin of Kajaria for Q1, Q2, Q3, Q4 of FY2025"**
16. **"Compare revenue, profit, and operating costs for Reliance across last 4 quarters"**
17. **"What are the revenue, profit margin, and EBITA margin trends for Asian Paints in FY2024 and FY2025?"**

---

### **Pattern: Multiple Companies + Single Parameter + Single Period**

18. **"Compare the EBITA margin of Kajaria Ceramics and Asian Paints for latest quarter"**
19. **"What is the revenue comparison between Reliance and Tata Motors in Q1FY2025?"**
20. **"Show me EBITA margin of Kajaria, Asian Paints, and Berger Paints for FY-2024"**
21. **"Compare profit margin of top 3 companies in the sector for latest period"**

---

### **Pattern: Multiple Companies + Single Parameter + Multiple Periods**

22. **"Compare EBITA margin of Kajaria and Asian Paints across Q1, Q2, Q3, Q4 of FY2025"**
23. **"Show me revenue comparison between Reliance and Tata Motors for last 4 quarters"**
24. **"Compare profit margin trends of Kajaria vs Asian Paints in FY2024 and FY2025"**

---

### **Pattern: Multiple Companies + Multiple Parameters + Single Period**

25. **"Compare revenue and EBITA margin of Kajaria and Asian Paints for latest quarter"**
26. **"Show me revenue, profit, and EBITA margin comparison between Reliance and Tata Motors in Q1FY2025"**
27. **"Compare multiple financial metrics of top 3 companies for FY-2024"**

---

### **Pattern: Multiple Companies + Multiple Parameters + Multiple Periods**

28. **"Compare revenue and EBITA margin of Kajaria and Asian Paints across Q1, Q2, Q3, Q4 of FY2025"**
29. **"Show me revenue, profit, and operating costs comparison between Reliance and Tata Motors for last 4 quarters"**
30. **"Compare multiple financial metrics of Kajaria, Asian Paints, and Berger Paints across FY2024 and FY2025"**

---

## 🔍 Period Variations Supported

All queries support flexible period formats:

- **"latest"** / **"most recent"** / **"recent quarter"**
- **"Q1FY2025"** / **"FY2025Q1"** / **"1QFY2025"** / **"1QFY-2025"**
- **"quarter 1"** / **"Q1"** (interprets as most recent Q1)
- **"FY2025"** / **"FY-2025"** / **"full year 2025"**
- **"2QFY2025"** / **"Q2FY2025"** / **"quarter 2 of 2025"**
- **"last 4 quarters"** / **"last year"**
- **"2025 quarter 1"** / **"Q1 2025"**

---

## 🎯 Key Capabilities Summary

| Capability | Supported? | Examples |
|-----------|-----------|----------|
| **Single Company** | ✅ Yes | Queries 1-17 |
| **Multiple Companies** | ✅ Yes | Queries 18-30 |
| **Single Parameter** | ✅ Yes | Queries 1-10, 18-24 |
| **Multiple Parameters** | ✅ Yes | Queries 11-17, 25-30 |
| **Single Period** | ✅ Yes | Queries 1-5, 11-14, 18-21, 25-27 |
| **Multiple Periods** | ✅ Yes | Queries 6-10, 15-17, 22-24, 28-30 |
| **Period Normalization** | ✅ Yes | All period formats supported |
| **Latest Period Detection** | ✅ Yes | Auto-detects most recent |
| **Parameter Validation** | ✅ Yes | Verifies existence before query |
| **Comparison Queries** | ✅ Yes | Multi-company, multi-parameter |
| **Trend Analysis** | ✅ Yes | Multiple periods = trend |

---

## 📊 Complex Query Examples

### Time-Series Analysis
- **"Show me EBITA margin trend for Kajaria over last 8 quarters"**
- **"Compare revenue growth of Kajaria vs Asian Paints for last 4 quarters"**
- **"What is the revenue trend for Reliance from Q1FY2024 to Q4FY2025?"**

### Year-over-Year Comparisons
- **"Compare Q1 2025 vs Q1 2024 revenue for Kajaria"**
- **"Show me YoY growth in EBITA margin for Asian Paints"**
- **"Compare FY2025 vs FY2024 profit margin for multiple companies"**

### Aggregations & Rankings
- **"Which company has the highest EBITA margin in latest quarter?"**
- **"Show me top 3 companies by revenue in FY2024"**
- **"Rank companies by profit margin for Q1FY2025"**

---

## 🚀 System Flow for Example Query

**Query: "Compare EBITA margin and revenue of Kajaria and Asian Paints for Q1, Q2, Q3 of FY2025"**

**Tool Calling Sequence:**
1. `verify_parameter_exists("EBITA margin")` → ✅ "EBITA margin"
2. `verify_parameter_exists("revenue")` → ✅ "Revenue" (or exact name)
3. `search_company("Kajaria")` → "Kajaria Ceramics Limited"
4. `search_company("Asian Paints")` → "Asian Paints Limited"
5. `normalize_period("Q1FY2025")` → "1QFY-2025"
6. `normalize_period("Q2FY2025")` → "2QFY-2025"
7. `normalize_period("Q3FY2025")` → "3QFY-2025"
8. `generate_comparison_query("EBITA margin", ["Kajaria", "Asian Paints"], ["1QFY-2025", "2QFY-2025", "3QFY-2025"])`
9. Execute query → Return structured comparison table

**Result Format:**
```
| Company            | Parameter     | Period     | Value      | Currency |
|-------------------|---------------|------------|------------|----------|
| Kajaria Ceramics  | EBITA margin  | 1QFY-2025  | 12.5%      | -        |
| Kajaria Ceramics  | EBITA margin  | 2QFY-2025  | 13.2%      | -        |
| Kajaria Ceramics  | EBITA margin  | 3QFY-2025  | 14.1%      | -        |
| Asian Paints      | EBITA margin  | 1QFY-2025  | 18.3%      | -        |
| Asian Paints      | EBITA margin  | 2QFY-2025  | 19.1%      | -        |
| Asian Paints      | EBITA margin  | 3QFY-2025  | 19.8%      | -        |
... (same for Revenue)
```

---

## ✅ All Combinations Supported

```
Companies:      [1] or [Multiple]
Parameters:     [1] or [Multiple]  
Periods:        [1] or [Multiple]
────────────────────────────────────
Total Patterns: 2 × 2 × 2 = 8 patterns
All 8 patterns: ✅ FULLY SUPPORTED
```

---

**Next**: Ready to discuss implementation plan for these capabilities!

