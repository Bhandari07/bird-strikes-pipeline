# Assumptions and decision register

These decisions remain pending until the assessor or supplier confirms them. Record the reply, owner and decision date before changing the corresponding rule.

| Question | Current implementation | Validation needed |
|---|---|---|
| Is Record ID stable and unique? | Match incident state on Record ID | Supplier identity contract |
| What is the airport role? | Label as reported airport | Departure versus incident location |
| Does omission differ from blank? | Missing column preserves; blank clears | Supplier update semantics |
| Is Final complete for the same scope? | Missing IDs are deletes, protected by manifest and 5% threshold | Scope and snapshot cutoff |
| Are all wildlife types in scope? | Include all supplied incidents | Birds-only population, if requested |
| What does cost mean? | Original dollar value, assumed USD | Currency, zero meaning and inflation basis |
| How should AUD be reported? | Nullable until an explicit rate/date/source is supplied | Agreed FX policy and source-currency confirmation |
| Where does exactly 1,000 feet belong? | Separate boundary category and warning | Inclusive boundary definition |
| What does engine code C mean? | Numeric null and quality issue | Supplier code definition |

The 5% deletion limit is an engineering guard, not a verified business requirement. The observed weekly deletion fraction is 40/22,655 = 0.177%, safely below it. The candidate manifest verifies the bytes and counts of the provided inputs but cannot prove the supplier's data is complete.
