# Plan: Refine Law Changes Report to Professional Format

## Goal
Update the law changes report generation (skill file + Python script) to produce a professional, Gmail-compatible HTML report matching the format shown in the reference image.

## Reference Structure from Image
The desired report includes:
1. Hero header with dark navy/purple background and orange count badge
2. Summary cards for Amendments (orange), New Laws (pink/red), Updates & Reg Changes (green)
3. Jurisdiction breakdown grid section
4. Categorized law changes tables by topic areas (Non-Compete, Minimum Wage, OSHA, etc.)
5. Action items grouped by urgency with colored left borders (red/orange/green/blue)
6. Professional footer with data source information

---

## Phase 1: Skill File Updates (`law_changes_report.md`)

### Task 1.1: Update Hero Header Section
- **File**: `orca/skills/law_changes_report.md`
- **Changes**:
  - Add orange badge with "X CHANGES" format (e.g., "34 CHANGES")
  - Badge styling: `background-color:#ea580c; color:#ffffff; padding:6px 16px; border-radius:20px`
  - Header background: dark navy/purple (`#1e3a8a` or `#312e81`)
  - Title: "Labor & Employment Law Changes" with date range subtitle
  - Generation date in smaller text below

### Task 1.2: Update Summary Cards Section
- **File**: `orca/skills/law_changes_report.md`
- **Changes**:
  - Card 1: Amendments — Orange theme (`#fff7ed` bg, `#ea580c` text, `font-size:32px`)
  - Card 2: New Laws — Pink theme (`#fef2f2` bg, `#dc2626` text)
  - Card 3: Updates & Reg Changes — Green theme (`#f0fdf4` bg, `#16a34a` text)
  - Each card shows extra-large numeric count and uppercase category label
  - Fix change type counting logic (actual values are "New Law", "Amendment", "Update")

### Task 1.3: Add Jurisdiction Breakdown Section
- **File**: `orca/skills/law_changes_report.md`
- **Changes**:
  - Add new section for jurisdiction breakdown grid
  - Container: `background-color:#f8fafc; border-left:3px solid #3b82f6; padding:16px 20px`
  - Grid format showing jurisdiction names with counts
  - Example: Federal (US): 18, Virginia: 7, Oregon: 3, etc.
  - Font size: 12px with muted text colors

### Task 1.4: Update Categorized Tables Section
- **File**: `orca/skills/law_changes_report.md`
- **Changes**:
  - Add specific topic categories: Non-Compete, Minimum Wage, Anti-Retaliation, OSHA, Court Decisions, Federal Proposals
  - Category header: Blue bar (`background-color:#e0e7ff; border-bottom:2px solid #3b82f6`)
  - Table columns: #, Jurisdiction, Bill, Effective, Summary
  - Alternate row backgrounds: `#ffffff` and `#fefce8` (light yellow)
  - Compact row height with `line-height:1.4`
  - Cell padding: `10px 16px`

### Task 1.5: Add Action Items Section
- **File**: `orca/skills/law_changes_report.md`
- **Changes**:
  - 4 urgency groups with colored left borders:
    - Immediate (Red): `border-left:4px solid #dc2626; background:#fef2f2`
    - Upcoming (Orange): `border-left:4px solid #ea580c; background:#fff7ed`
    - Ongoing (Green): `border-left:4px solid #16a34a; background:#f0fdf4`
    - Monitor (Blue): `border-left:4px solid #3b82f6; background:#eff6ff`
  - Headers with urgency label and date/topic
  - Content styling: 13px text, 1.6 line height

### Task 1.6: Update Footer Section
- **File**: `orca/skills/law_changes_report.md`
- **Changes**:
  - Left side: Data source info ("Data sourced from Orca law change trackers as of [DATE]")
  - Right side: Company name and date ("DoubleFin • [DATE]")
  - Font: 10px, muted colors
  - Background: `#f8fafc` with top border

### Task 1.7: Fix Change Type Values
- **File**: `orca/skills/law_changes_report.md`
- **Changes**:
  - Update all references from "NEW"/"AMENDMENT"/"REPEAL" to actual API values
  - Actual values: "New Law", "Amendment", "Update"
  - Update example summary statistics to reflect real values
  - Update priority categorization logic to use correct change type strings

### Task 1.8: Fix Field Name References
- **File**: `orca/skills/law_changes_report.md`
- **Changes**:
  - Ensure all references use `changes` array (not `lawChanges`)
  - Update field names: `billNumber`, `changeType`, `detailedDescription`, `effectiveDate`, `enactmentDate`, `jurisdiction`, `notes`, `researchContent`, `revisedEffectiveDate`, `revisedEnactmentDate`, `status`, `summary`, `trackerStem`, `uploadDate`
  - Remove non-existent fields like `workspaceId`, `regulationId`

---

## Phase 2: Python Script Updates (`generate_law_changes_report.py`)

### Task 2.1: Update Hero Header HTML Generation
- **File**: `orca/scripts/generate_law_changes_report.py`
- **Changes**:
  - Generate dark navy/purple header with orange "X CHANGES" badge
  - Add proper title "Labor & Employment Law Changes"
  - Add date range subtitle and generation timestamp
  - Fix orange badge styling

### Task 2.2: Update Summary Cards HTML Generation
- **File**: `orca/scripts/generate_law_changes_report.py`
- **Changes**:
  - Generate 3 cards: Amendments (orange), New Laws (pink), Updates (green)
  - Large numeric counts (32px font)
  - Proper background colors and text colors per card
  - Fix change type counting logic (remove hardcoded "0" for repeals)

### Task 2.3: Add Jurisdiction Breakdown HTML Generation
- **File**: `orca/scripts/generate_law_changes_report.py`
- **Changes**:
  - Count changes per jurisdiction from data
  - Generate grid layout showing jurisdiction names and counts
  - Blue left border styling
  - Sort by count descending

### Task 2.4: Add Categorized Tables HTML Generation
- **File**: `orca/scripts/generate_law_changes_report.py`
- **Changes**:
  - Implement topic categorization logic based on `trackerStem` and summary content
  - Categories: Non-Compete, Minimum Wage, Anti-Retaliation, OSHA, Court Decisions, Federal Proposals
  - Generate separate table for each category with blue header
  - Alternate row colors (white/light yellow)
  - Compact styling

### Task 2.5: Add Action Items HTML Generation
- **File**: `orca/scripts/generate_law_changes_report.py`
- **Changes**:
  - Generate action items from high-priority changes
  - Group by urgency: Immediate, Upcoming, Ongoing, Monitor
  - Apply colored left borders per urgency group
  - Generate specific action text from change summaries

### Task 2.6: Update Footer HTML Generation
- **File**: `orca/scripts/generate_law_changes_report.py`
- **Changes**:
  - Generate professional footer with data source info
  - Add "DoubleFin" branding and generation date
  - Proper muted color styling

### Task 2.7: Fix Date Parsing Logic
- **File**: `orca/scripts/generate_law_changes_report.py`
- **Changes**:
  - Ensure proper handling of YYYY-MM-DD format (no timezone issues)
  - Handle both date-only and datetime formats consistently
  - Fix any remaining timezone-aware vs naive comparison issues

### Task 2.8: Fix Change Type and Field Mappings
- **File**: `orca/scripts/generate_law_changes_report.py`
- **Changes**:
  - Update all change type references to use "New Law", "Amendment", "Update"
  - Remove references to non-existent "REPEAL" type
  - Ensure all field names match actual API response structure
  - Remove references to `workspaceId`, `regulationId`

---

## Phase 3: Testing and Validation

### Task 3.1: Test Script with Cached Data
- Run the updated script against existing cached data
- Verify HTML output renders correctly
- Check for any JavaScript errors or broken styling

### Task 3.2: Verify Gmail Compatibility
- Ensure all CSS is inline (no `<style>` tags)
- Verify table-based layout works correctly
- Check that colors and borders render properly

### Task 3.3: Validate Data Accuracy
- Verify counts match actual data (total, by type, by jurisdiction)
- Check that all law changes are included
- Verify date formatting is correct

---

## Phase 4: Skill File Finalization

### Task 4.1: Update Example Output Summary
- Update the example summary at the end of skill file
- Ensure example statistics reflect realistic distributions
- Update category and action item examples

### Task 4.2: Update Automated Script Section
- Update script usage examples if needed
- Ensure file paths are correct
- Update end-to-end workflow example

### Task 4.3: Final Review and Cleanup
- Review entire skill file for consistency
- Ensure all formatting specifications are accurate
- Remove any outdated or incorrect information

---

## Execution Order

1. **Phase 1** (Tasks 1.1-1.8): Update skill file documentation
2. **Phase 2** (Tasks 2.1-2.8): Update Python script implementation
3. **Phase 3** (Tasks 3.1-3.3): Test and validate
4. **Phase 4** (Tasks 4.1-4.3): Finalize and cleanup

## Notes
- Always use table-based layouts with inline CSS for Gmail compatibility
- The actual API returns `changes` array with fields: `billNumber`, `changeType`, `detailedDescription`, `effectiveDate`, `enactmentDate`, `jurisdiction`, `notes`, `researchContent`, `revisedEffectiveDate`, `revisedEnactmentDate`, `status`, `summary`, `trackerStem`, `uploadDate`
- Change types are: "New Law", "Amendment", "Update" (not "NEW", "AMENDMENT", "REPEAL")
- Dates may be in YYYY-MM-DD format without time components
