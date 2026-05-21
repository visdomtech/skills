# Display Strategies for Large Response Data

When Orca MCP tools return large amounts of data (e.g., thousands of jurisdictions, regulations, or documents), displaying all results at once can overwhelm users and degrade performance.

## When to Apply

- Response size exceeds 50 records
- Response data size exceeds 10KB
- User query doesn't specify pagination parameters
- Performance impact is noticeable

## Strategies

### 1. Display First 10 Items

Show the first 10 records to give users immediate context about the data structure and initial content.

```
Showing first 10 of 1,250 jurisdictions:
1. United States of America (US)
2. Alabama (US-AL)
3. Alaska (US-AK)
4. Arizona (US-AZ)
5. Arkansas (US-AR)
6. California (US-CA)
7. Colorado (US-CO)
8. Connecticut (US-CT)
9. Delaware (US-DE)
10. Florida (US-FL)
```

### 2. Display Last 10 Items

Show the last 10 records to provide insight into how the data concludes.

```
Showing last 10 of 1,250 jurisdictions:
1,241. Wyoming (US-WY)
1,242. Puerto Rico (US-PR)
...
1,250. Palau (PW)
```

### 3. Display Random Middle 10 Items

Sample 10 random records from the middle portion to show diversity.

```
Showing 10 random sample items from middle of 1,250 jurisdictions:
- Texas (US-TX)
- Ontario (CA-ON)
- Bavaria (DE-BY)
...
```

### 4. Provide Summary Statistics

Give comprehensive summary information about the complete dataset:

```
Dataset Summary:
- Total records: 1,250 jurisdictions
- Data types: Federal (50), State/Province (1,200)
- Geographic coverage: 195 countries
- Most common jurisdiction type: State/Province (96%)
```

## Implementation Steps

1. **Count total records** before processing display logic
2. **Apply sampling strategy** based on data characteristics:
   - Sequential data: Use first/last approach
   - Categorical data: Use random sampling
   - Time-series data: Use first/last + middle samples
3. **Generate meaningful summary** with relevant statistics
4. **Provide navigation options** for users who want more details:
   - "Show all" (with warning about size)
   - "Show specific page/range"
   - "Filter by criteria"

## User Experience

- Always inform users about the total dataset size
- Clearly indicate when showing partial results
- Offer clear paths to access complete data if needed
- Prioritize performance over completeness for initial display
