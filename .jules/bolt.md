## 2025-05-14 - [Optimization of String Normalization]
**Learning:** Replacing nested  calls with a combination of pre-compiled regex and the  idiom significantly improves performance (approx. 50% faster). The  method without arguments is highly optimized for collapsing any whitespace and stripping ends, making it a superior alternative to .
**Action:** Use pre-compiled regex for frequently called patterns and prefer built-in string methods (like ) over complex regex for whitespace management.
## 2025-05-14 - [Optimization of String Normalization]
**Learning:** Replacing nested `re.sub` calls with a combination of pre-compiled regex and the `" ".join(val.split())` idiom significantly improves performance (approx. 50% faster). The `split()` method without arguments is highly optimized for collapsing any whitespace and stripping ends, making it a superior alternative to `re.sub(r"\s+", " ", ...).strip()`.
**Action:** Use pre-compiled regex for frequently called patterns and prefer built-in string methods (like `split/join`) over complex regex for whitespace management.
