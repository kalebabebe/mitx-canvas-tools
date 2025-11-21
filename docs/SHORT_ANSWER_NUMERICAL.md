# Short Answer and Numerical Question Support

## New Question Types Added

### ✅ Short Answer / Fill-in-the-Blank
Canvas `cc.fib.v0p1` → Open edX `<stringresponse>`

### ✅ Numerical Questions  
Canvas `numerical_question` → Open edX `<numericalresponse>`

## Supported Question Types Summary

| Question Type | Status |
|--------------|---------|
| Multiple Choice | ✅ Full |
| True/False | ✅ Full |
| Multiple Response | ✅ Full |
| **Short Answer** | ✅ **NEW** |
| **Numerical** | ✅ **NEW** |
| Essay | ⚠️ Manual grading note |

## Usage

No changes needed - automatic during conversion:

```bash
python cli.py course.imscc output_dir --verbose
```

## Examples

### Short Answer
```xml
<problem>
  <p>What is the capital of France?</p>
  <stringresponse answer="Paris" type="ci">
    <textline size="20"/>
  </stringresponse>
</problem>
```

### Numerical
```xml
<problem>
  <p>What is 10 + 2?</p>
  <numericalresponse answer="12.0">
    <responseparam type="tolerance" default="5.0"/>
    <formulaequationinput/>
  </numericalresponse>
</problem>
```

## Implementation Notes

**Short Answer:**
- Case-insensitive by default
- Single correct answer
- Text input field

**Numerical:**
- Automatic tolerance calculation from Canvas range
- Formula input (allows arithmetic)
- Example: Canvas range [7, 17] with answer 12 → tolerance ±5

## Limitations

**Short Answer:**
- Single answer only (no multiple acceptable answers yet)
- No regex support

**Numerical:**
- Simple tolerance only (no percentage-based)
- No unit support
